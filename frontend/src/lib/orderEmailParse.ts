import type { EmailDetail } from "./gmailScan";
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
}

// Lines that look like totals/fees rather than items.
const NON_ITEM_PATTERN =
  /\b(subtotal|sub-total|total|shipping|tax|discount|handling|balance|payment|order\s*(number|no|#)|invoice\s*(number|no|#)|tracking)\b/i;

function parseFromHeader(from: string): { displayName: string; email: string; domain: string } {
  const match = from.match(/^\s*"?([^"<]*)"?\s*<([^>]+)>\s*$/);
  const email = match ? match[2].trim() : from.trim();
  const displayName = match ? match[1].trim() : "";
  const domain = email.includes("@") ? email.split("@")[1].toLowerCase() : "";
  return { displayName, email, domain };
}

function matchVendor(email: EmailDetail, vendors: Vendor[]): Vendor | null {
  const haystack = `${email.from} ${email.subject} ${email.bodyText.slice(0, 2000)}`.toLowerCase();
  for (const vendor of vendors) {
    const name = vendor.name.trim().toLowerCase();
    if (name.length >= 4 && haystack.includes(name)) return vendor;
  }
  return null;
}

function suggestVendorName(from: string): string {
  const { displayName, domain } = parseFromHeader(from);
  if (displayName && !/no-?reply|notification|order|confirm/i.test(displayName)) {
    return displayName;
  }
  if (domain) {
    // "orders@firemountaingems.com" -> "Firemountaingems"
    const base = domain.split(".")[0];
    return base.charAt(0).toUpperCase() + base.slice(1);
  }
  return displayName || "Unknown Vendor";
}

function parseOrderDate(dateHeader: string): string | null {
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
 * Heuristic line-item extraction from order-confirmation body text. Looks for
 * common quantity patterns ("2 x Item", "Item x 2", "Qty: 2" following an
 * item line) and price-tagged lines. Best-effort — anything it can't read is
 * left for the user to fix on the created order.
 */
export function parseOrderLines(bodyText: string): ParsedOrderLine[] {
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

    // "2 x 8mm Round Turquoise Strand ($4.50)"
    let m = line.match(/^(\d{1,3})\s*[x×]\s+(.{4,})$/i);
    if (m) {
      push(m[2].replace(/\$.*$/, ""), Number(m[1]), parseMoney(line));
      continue;
    }

    // "8mm Round Turquoise Strand x 2"
    m = line.match(/^(.{4,}?)\s+[x×]\s*(\d{1,3})\b(.*)$/i);
    if (m) {
      push(m[1], Number(m[2]), parseMoney(line));
      continue;
    }

    // "Qty: 2" (or "Quantity: 2") — item description is the previous line.
    m = line.match(/^(?:qty|quantity)\s*[:.]?\s*(\d{1,3})\b/i);
    if (m && i > 0) {
      const prev = rawLines[i - 1];
      if (!NON_ITEM_PATTERN.test(prev)) {
        push(prev.replace(/\$.*$/, ""), Number(m[1]), parseMoney(line) ?? parseMoney(prev));
      }
      continue;
    }

    // "8mm Round Turquoise Strand ... $4.50" (price-tagged line, assume qty 1)
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

export function parseOrderEmail(email: EmailDetail, vendors: Vendor[]): ParsedOrder {
  return {
    vendorMatch: matchVendor(email, vendors),
    suggestedVendorName: suggestVendorName(email.from),
    orderDate: parseOrderDate(email.date),
    lines: parseOrderLines(email.bodyText),
  };
}
