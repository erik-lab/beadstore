import { api, ApiError } from "./apiClient";
import type { EmailDetail } from "./emailScanTypes";
import type { Vendor } from "./types";

export interface ParsedOrderLine {
  description: string;
  quantity: number | null;
  unitCost: number | null;
}

export interface ParsedOrder {
  vendorMatch: Vendor | null;
  suggestedVendorName: string;
  orderDate: string | null; // ISO yyyy-mm-dd
  lines: ParsedOrderLine[];
  parsedByAi: boolean;
}

interface AiParseResponse {
  vendor_name: string | null;
  order_number: string | null;
  order_date: string | null;
  lines: { description: string; quantity: number | null; unit: string | null; unit_cost: number | null }[];
}

// Lines that look like totals/fees rather than items (used by the regex fallback).
const NON_ITEM_PATTERN =
  /\b(subtotal|sub-total|total|shipping|tax|discount|handling|balance|payment|order\s*(number|no|#)|invoice\s*(number|no|#)|tracking)\b/i;

function parseFromHeader(from: string): { displayName: string; email: string; domain: string } {
  const match = from.match(/^\s*"?([^"<]*)"?\s*<([^>]+)>\s*$/);
  const email = match ? match[2].trim() : from.trim();
  const displayName = match ? match[1].trim() : "";
  const domain = email.includes("@") ? email.split("@")[1].toLowerCase() : "";
  return { displayName, email, domain };
}

function matchVendor(haystack: string, vendors: Vendor[]): Vendor | null {
  const lower = haystack.toLowerCase();
  for (const vendor of vendors) {
    const name = vendor.name.trim().toLowerCase();
    if (name.length >= 4 && lower.includes(name)) return vendor;
  }
  return null;
}

function suggestVendorName(from: string): string {
  const { displayName, domain } = parseFromHeader(from);
  if (displayName && !/no-?reply|notification|order|confirm/i.test(displayName)) {
    return displayName;
  }
  if (domain) {
    const base = domain.split(".")[0];
    return base.charAt(0).toUpperCase() + base.slice(1);
  }
  return displayName || "Unknown Vendor";
}

function parseHeaderDate(dateHeader: string): string | null {
  const parsed = new Date(dateHeader);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}

function cleanDescription(text: string): string {
  return text
    .replace(/^[\s\-*•·>|]+/, "")
    .replace(/[\s\-*•·|]+$/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function parseMoney(text: string): number | null {
  const match = text.match(/\$\s*(\d{1,5}(?:,\d{3})*(?:\.\d{2})?)/);
  if (!match) return null;
  return Number(match[1].replace(/,/g, ""));
}

/**
 * Regex-based fallback line-item extraction, used only when AI parsing isn't
 * configured or fails. Looks for common quantity patterns ("2 x Item",
 * "Item x 2", "Qty: 2" following an item line) and price-tagged lines.
 */
function parseOrderLinesWithRegex(bodyText: string): ParsedOrderLine[] {
  const rawLines = bodyText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  const items: ParsedOrderLine[] = [];
  const seen = new Set<string>();

  function push(description: string, quantity: number | null, unitCost: number | null) {
    const desc = cleanDescription(description).slice(0, 300);
    if (desc.length < 4) return;
    if (NON_ITEM_PATTERN.test(desc)) return;
    const key = desc.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    items.push({ description: desc, quantity, unitCost });
  }

  for (let i = 0; i < rawLines.length && items.length < 20; i++) {
    const line = rawLines[i];
    if (NON_ITEM_PATTERN.test(line)) continue;

    let m = line.match(/^(\d{1,3})\s*[x×]\s+(.{4,})$/i);
    if (m) {
      push(m[2].replace(/\$.*$/, ""), Number(m[1]), parseMoney(line));
      continue;
    }

    m = line.match(/^(.{4,}?)\s+[x×]\s*(\d{1,3})\b(.*)$/i);
    if (m) {
      push(m[1], Number(m[2]), parseMoney(line));
      continue;
    }

    m = line.match(/^(?:qty|quantity)\s*[:.]?\s*(\d{1,3})\b/i);
    if (m && i > 0) {
      const prev = rawLines[i - 1];
      if (!NON_ITEM_PATTERN.test(prev)) {
        push(prev.replace(/\$.*$/, ""), Number(m[1]), parseMoney(line) ?? parseMoney(prev));
      }
      continue;
    }

    const price = parseMoney(line);
    if (price != null) {
      const desc = line.replace(/\$\s*[\d,.]+/g, "").trim();
      if (desc.length >= 8 && /[a-zA-Z]{4,}/.test(desc)) {
        push(desc, 1, price);
      }
    }
  }

  return items;
}

function parseOrderEmailWithRegex(email: EmailDetail, vendors: Vendor[]): ParsedOrder {
  return {
    vendorMatch: matchVendor(`${email.from_address} ${email.subject} ${email.body_text.slice(0, 2000)}`, vendors),
    suggestedVendorName: suggestVendorName(email.from_address),
    orderDate: parseHeaderDate(email.date),
    lines: parseOrderLinesWithRegex(email.body_text),
    parsedByAi: false,
  };
}

/**
 * Parse an order email using the server-side AI extractor (Claude Haiku 4.5).
 * Falls back to regex-based parsing if the AI parser isn't configured (503)
 * or fails for any other reason, so Record Order still works either way.
 */
export async function parseOrderEmail(email: EmailDetail, vendors: Vendor[]): Promise<ParsedOrder> {
  try {
    const result = await api.post<AiParseResponse>("/order-email-parse", {
      subject: email.subject,
      from_header: email.from_address,
      date_header: email.date,
      body_text: email.body_text.slice(0, 50_000),
      attachments: email.attachments.map((a) => ({
        filename: a.filename,
        mime_type: a.mime_type,
        data_base64: a.base64_data,
      })),
    });

    const haystack = `${email.from_address} ${email.subject} ${result.vendor_name ?? ""}`;
    const vendorMatch = matchVendor(haystack, vendors);

    return {
      vendorMatch,
      suggestedVendorName: result.vendor_name?.trim() || suggestVendorName(email.from_address),
      orderDate: result.order_date || parseHeaderDate(email.date),
      lines: result.lines
        .filter((line) => line.description.trim().length > 0)
        .map((line) => ({
          description: line.description.trim().slice(0, 300),
          quantity: line.quantity,
          unitCost: line.unit_cost,
        })),
      parsedByAi: true,
    };
  } catch (err) {
    // 503 = AI parsing not configured; anything else = a parsing failure.
    // Either way, fall back to the regex parser so Record Order still works.
    if (!(err instanceof ApiError)) throw err;
    return parseOrderEmailWithRegex(email, vendors);
  }
}
