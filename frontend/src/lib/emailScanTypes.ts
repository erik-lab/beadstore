// Types shared by every email-provider adapter (Gmail, Outlook, ...) so the
// scan page and the AI order parser stay provider-agnostic.

export interface CandidateEmail {
  id: string;
  from: string;
  subject: string;
  date: string;
  snippet: string;
  matchReasons: string[];
}

export interface EmailAttachment {
  filename: string;
  mimeType: string;
  base64Data: string;
}

export interface EmailDetail {
  id: string;
  from: string;
  to: string;
  subject: string;
  date: string;
  bodyText: string;
  attachments: EmailAttachment[];
}

export type MoveEmailResult =
  | { moved: true }
  | { moved: false; reason: "permission" | "error"; message: string };

/**
 * Everything the Order Email Scan page needs from one email provider. Each
 * provider (Gmail, Outlook) implements this against its own API; the page
 * itself never talks to a provider API directly.
 */
export interface EmailProviderAdapter {
  id: string;
  label: string;
  configured: boolean;
  notConfiguredMessage: string;
  ordersFolderName: string;
  scanForOrderEmails(vendorNames: string[]): Promise<CandidateEmail[]>;
  fetchEmailDetail(messageId: string): Promise<EmailDetail>;
  moveEmailToOrdersFolder(messageId: string): Promise<MoveEmailResult>;
}

// Bead/jewelry-supply signals checked against sender/subject/snippet —
// shared across providers so "why it matched" stays consistent.
export const BEAD_KEYWORDS = [
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

export function matchReasons(from: string, subject: string, snippet: string, vendorNames: string[]): string[] {
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
