// Prototype Gmail scanning for supplier order-confirmation emails.
//
// Runs entirely in the browser with Google Identity Services: the user grants
// gmail.readonly in a popup, the access token lives only in this module's
// memory for the current page visit, and nothing is stored — every scan
// re-authorizes. Requires VITE_GOOGLE_CLIENT_ID (an OAuth Web client ID from
// Google Cloud Console with this app's URL as an authorized JavaScript origin).

const GSI_SRC = "https://accounts.google.com/gsi/client";
const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly";
const GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me";

// How far back to look, and how many matches of the broad search to inspect.
const SEARCH_WINDOW = "newer_than:180d";
const MAX_MESSAGES = 60;

// Broad "looks like an order email" Gmail search; refined client-side below.
const ORDER_QUERY = `${SEARCH_WINDOW} (subject:order OR subject:confirmation OR subject:shipped OR subject:shipment OR subject:receipt OR subject:invoice OR subject:"thank you for your purchase")`;

// Bead/jewelry-supply signals checked against sender and subject.
const BEAD_KEYWORDS = [
  "bead",
  "beads",
  "beading",
  "gem",
  "gems",
  "gemstone",
  "jewelry",
  "jewellery",
  "findings",
  "cabochon",
  "lampwork",
  "seed bead",
  "swarovski",
  "czech glass",
  "rhinestone",
  "charms",
  "pendants",
  "wire wrap",
  "fire mountain",
  "dakota stones",
  "beadaholique",
  "shipwreck beads",
  "rio grande",
  "halcraft",
  "john bead",
];

export interface CandidateEmail {
  id: string;
  from: string;
  subject: string;
  date: string;
  snippet: string;
  matchReasons: string[];
}

interface TokenClient {
  requestAccessToken: () => void;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (response: { access_token?: string; error?: string }) => void;
          }) => TokenClient;
        };
      };
    };
  }
}

let gsiLoaded: Promise<void> | null = null;

function loadGsi(): Promise<void> {
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  if (gsiLoaded) return gsiLoaded;
  gsiLoaded = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      gsiLoaded = null;
      reject(new Error("Could not load Google sign-in. Check your network and try again."));
    };
    document.head.appendChild(script);
  });
  return gsiLoaded;
}

// Access token for the current page visit only — module memory, never
// persisted. Reused so View/Record clicks after a scan don't re-prompt;
// cleared (and re-authorized) if Gmail rejects it as expired.
let currentToken: string | null = null;

async function requestAccessToken(clientId: string): Promise<string> {
  await loadGsi();
  return new Promise((resolve, reject) => {
    const client = window.google!.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: GMAIL_SCOPE,
      callback: (response) => {
        if (response.access_token) {
          currentToken = response.access_token;
          resolve(response.access_token);
        } else {
          reject(new Error(response.error ?? "Gmail authorization was cancelled."));
        }
      },
    });
    client.requestAccessToken();
  });
}

async function ensureToken(clientId: string): Promise<string> {
  return currentToken ?? requestAccessToken(clientId);
}

async function gmailGet(clientId: string, path: string): Promise<Record<string, unknown>> {
  let token = await ensureToken(clientId);
  let resp = await fetch(`${GMAIL_API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (resp.status === 401) {
    // Token expired mid-session — re-authorize once and retry.
    currentToken = null;
    token = await requestAccessToken(clientId);
    resp = await fetch(`${GMAIL_API}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  }
  if (!resp.ok) {
    throw new Error(`Gmail request failed (${resp.status}). Try scanning again.`);
  }
  return resp.json();
}

function headerValue(headers: { name: string; value: string }[], name: string): string {
  return headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? "";
}

function matchReasons(from: string, subject: string, snippet: string, vendorNames: string[]): string[] {
  const reasons: string[] = [];
  const haystack = `${from} ${subject} ${snippet}`.toLowerCase();

  for (const vendor of vendorNames) {
    const name = vendor.trim().toLowerCase();
    if (name.length >= 4 && haystack.includes(name)) {
      reasons.push(`Matches your vendor "${vendor}"`);
    }
  }

  const keywordHits = BEAD_KEYWORDS.filter((kw) => haystack.includes(kw));
  if (keywordHits.length > 0) {
    reasons.push(`Mentions: ${keywordHits.slice(0, 4).join(", ")}`);
  }

  return reasons;
}

/**
 * Authorize (popup) and scan the inbox. `vendorNames` come from the app's own
 * vendor list so emails from suppliers Patti already uses always match, even
 * without generic bead keywords.
 */
export async function scanGmailForOrderEmails(
  clientId: string,
  vendorNames: string[]
): Promise<CandidateEmail[]> {
  currentToken = null; // a fresh scan always re-authorizes
  await requestAccessToken(clientId);

  const list = (await gmailGet(
    clientId,
    `/messages?q=${encodeURIComponent(ORDER_QUERY)}&maxResults=${MAX_MESSAGES}`
  )) as { messages?: { id: string }[] };

  const ids = (list.messages ?? []).map((m) => m.id);
  const candidates: CandidateEmail[] = [];

  // Fetch metadata in small parallel chunks to stay well under rate limits.
  const CHUNK = 10;
  for (let i = 0; i < ids.length; i += CHUNK) {
    const chunk = ids.slice(i, i + CHUNK);
    const messages = await Promise.all(
      chunk.map(
        (id) =>
          gmailGet(
            clientId,
            `/messages/${id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date`
          ) as Promise<{
            id: string;
            snippet?: string;
            payload?: { headers?: { name: string; value: string }[] };
          }>
      )
    );
    for (const msg of messages) {
      const headers = msg.payload?.headers ?? [];
      const from = headerValue(headers, "From");
      const subject = headerValue(headers, "Subject");
      const date = headerValue(headers, "Date");
      const snippet = msg.snippet ?? "";
      const reasons = matchReasons(from, subject, snippet, vendorNames);
      if (reasons.length > 0) {
        candidates.push({ id: msg.id, from, subject, date, snippet, matchReasons: reasons });
      }
    }
  }

  return candidates;
}

export interface EmailDetail {
  id: string;
  from: string;
  to: string;
  subject: string;
  date: string;
  bodyText: string;
}

interface MessagePart {
  mimeType?: string;
  body?: { data?: string };
  parts?: MessagePart[];
}

function decodeBase64Url(data: string): string {
  const base64 = data.replace(/-/g, "+").replace(/_/g, "/");
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  return new TextDecoder("utf-8").decode(bytes);
}

function htmlToText(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("style, script, head").forEach((el) => el.remove());
  const text = doc.body?.innerText ?? doc.body?.textContent ?? "";
  return text.replace(/\n{3,}/g, "\n\n").trim();
}

function collectParts(part: MessagePart, mimeType: string, found: string[]): void {
  if (part.mimeType === mimeType && part.body?.data) {
    found.push(decodeBase64Url(part.body.data));
  }
  for (const child of part.parts ?? []) {
    collectParts(child, mimeType, found);
  }
}

function extractBodyText(payload: MessagePart): string {
  const plain: string[] = [];
  collectParts(payload, "text/plain", plain);
  if (plain.length > 0) return plain.join("\n").trim();

  const html: string[] = [];
  collectParts(payload, "text/html", html);
  if (html.length > 0) return htmlToText(html.join("\n"));

  return "";
}

/** Fetch one email's headers and readable body text (for View / Record Order). */
export async function fetchEmailDetail(clientId: string, messageId: string): Promise<EmailDetail> {
  const msg = (await gmailGet(clientId, `/messages/${messageId}?format=full`)) as {
    id: string;
    snippet?: string;
    payload?: MessagePart & { headers?: { name: string; value: string }[] };
  };
  const headers = msg.payload?.headers ?? [];
  return {
    id: msg.id,
    from: headerValue(headers, "From"),
    to: headerValue(headers, "To"),
    subject: headerValue(headers, "Subject"),
    date: headerValue(headers, "Date"),
    bodyText: (msg.payload ? extractBodyText(msg.payload) : "") || msg.snippet || "",
  };
}
