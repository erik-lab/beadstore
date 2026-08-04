// Prototype Outlook/Microsoft 365 scanning for supplier order-confirmation
// emails — mirrors gmailScan.ts against Microsoft Graph instead of Gmail.
//
// Runs entirely in the browser with MSAL.js (Microsoft's browser auth
// library, loaded from Microsoft's own CDN so no npm dependency is added):
// the user grants Mail.ReadWrite in a popup (read access, plus move access
// so a recorded order's email can be filed away), the access token lives
// only in this module's memory for the current page visit, and nothing is
// stored — every scan re-authorizes. Requires VITE_MICROSOFT_CLIENT_ID (an
// Azure App registration's Application (client) ID, registered as a "Single
// Page Application" with this site's URL as a redirect URI).

import { matchReasons, type CandidateEmail, type EmailAttachment, type EmailDetail, type EmailProviderAdapter, type MoveEmailResult } from "./emailScanTypes";
import { withTimeout } from "./promiseUtils";

// Two independent CDN sources for the same pinned msal-browser version —
// Microsoft's own CDN first, falling back to jsDelivr if that host is
// unreachable (blocked by a browser extension, network policy, etc.) so a
// single CDN hiccup doesn't take down the whole Outlook connect button.
const MSAL_VERSION = "3.30.0";
const MSAL_SOURCES = [
  `https://alcdn.msauth.net/browser/${MSAL_VERSION}/js/msal-browser.min.js`,
  `https://cdn.jsdelivr.net/npm/@azure/msal-browser@${MSAL_VERSION}/lib/msal-browser.min.js`,
];
const GRAPH_API = "https://graph.microsoft.com/v1.0";
const GRAPH_SCOPE = "Mail.ReadWrite";
const CLIENT_ID = (import.meta.env.VITE_MICROSOFT_CLIENT_ID as string | undefined) ?? "";

// The folder a recorded order's email is moved into. Configurable via
// VITE_OUTLOOK_ORDERS_LABEL until there's an in-app settings page for it.
export const OUTLOOK_ORDERS_FOLDER_NAME =
  (import.meta.env.VITE_OUTLOOK_ORDERS_LABEL as string | undefined)?.trim() || "Bead Store Orders";

// How far back to look, and how many messages to inspect per scan.
const SEARCH_WINDOW_DAYS = 180;
const MAX_MESSAGES = 60;

// Backstop in case the sign-in popup never settles (e.g. the browser blocks
// it silently), so a "Scanning..." button state can never hang indefinitely.
const AUTH_TIMEOUT_MS = 90_000;

interface MsalAccount {
  username: string;
}

interface MsalAuthResult {
  accessToken: string;
  account: MsalAccount;
}

interface MsalPublicClientApplication {
  initialize: () => Promise<void>;
  loginPopup: (request: { scopes: string[] }) => Promise<MsalAuthResult>;
  acquireTokenSilent: (request: { scopes: string[]; account: MsalAccount }) => Promise<MsalAuthResult>;
  getAllAccounts: () => MsalAccount[];
}

declare global {
  interface Window {
    msal?: {
      PublicClientApplication: new (config: {
        auth: { clientId: string; authority: string };
      }) => MsalPublicClientApplication;
    };
  }
}

let msalLoaded: Promise<void> | null = null;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

async function loadMsal(): Promise<void> {
  if (window.msal?.PublicClientApplication) return;
  if (msalLoaded) return msalLoaded;
  msalLoaded = (async () => {
    let lastError: unknown;
    for (const src of MSAL_SOURCES) {
      try {
        await loadScript(src);
        if (window.msal?.PublicClientApplication) return;
      } catch (err) {
        lastError = err;
      }
    }
    msalLoaded = null;
    throw new Error("Could not load Microsoft sign-in. Check your network and try again.", { cause: lastError });
  })();
  return msalLoaded;
}

let pca: MsalPublicClientApplication | null = null;

async function getPca(): Promise<MsalPublicClientApplication> {
  await loadMsal();
  if (!pca) {
    pca = new window.msal!.PublicClientApplication({
      // /organizations (not /common) — this is a work/school (business) email
      // connection only. Most Azure app registrations default to "single
      // tenant", which rejects /common's implied personal-account support
      // with "unauthorized_client ... not enabled for consumers".
      auth: { clientId: CLIENT_ID, authority: "https://login.microsoftonline.com/organizations" },
    });
    await pca.initialize();
  }
  return pca;
}

// Access token for the current page visit only — module memory, never
// persisted. Reused so View/Record clicks after a scan don't re-prompt;
// cleared (and re-authorized) if Graph rejects it as expired.
let currentToken: string | null = null;

async function requestAccessToken(): Promise<string> {
  const client = await getPca();
  const result = await withTimeout(
    client.loginPopup({ scopes: [GRAPH_SCOPE] }),
    AUTH_TIMEOUT_MS,
    "Outlook sign-in timed out or was cancelled. Please try again."
  );
  currentToken = result.accessToken;
  return result.accessToken;
}

async function ensureToken(): Promise<string> {
  return currentToken ?? requestAccessToken();
}

class GraphApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function graphRequest(path: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
  let token = await ensureToken();
  const doFetch = (t: string) =>
    fetch(`${GRAPH_API}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${t}`,
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });

  let resp = await doFetch(token);
  if (resp.status === 401) {
    // Token expired mid-session — re-authorize once and retry.
    currentToken = null;
    token = await requestAccessToken();
    resp = await doFetch(token);
  }
  if (!resp.ok) {
    throw new GraphApiError(resp.status, `Outlook request failed (${resp.status}).`);
  }
  if (resp.status === 204) return {};
  return resp.json();
}

async function graphGet(path: string): Promise<Record<string, unknown>> {
  return graphRequest(path);
}

async function graphPost(path: string, body: unknown): Promise<Record<string, unknown>> {
  return graphRequest(path, { method: "POST", body: JSON.stringify(body) });
}

interface GraphMessage {
  id: string;
  subject?: string;
  bodyPreview?: string;
  receivedDateTime?: string;
  from?: { emailAddress?: { name?: string; address?: string } };
  toRecipients?: { emailAddress?: { name?: string; address?: string } }[];
  hasAttachments?: boolean;
  body?: { contentType?: string; content?: string };
}

function formatFrom(from: GraphMessage["from"]): string {
  if (!from?.emailAddress) return "";
  const { name, address } = from.emailAddress;
  if (name && address && name !== address) return `${name} <${address}>`;
  return address ?? name ?? "";
}

/**
 * Authorize (popup) and scan the inbox. `vendorNames` come from the app's own
 * vendor list so emails from suppliers Patti already uses always match, even
 * without generic bead keywords. Restricted to the Inbox folder specifically
 * (Graph's /mailFolders('inbox')/messages), and matching (order-shaped
 * subject + bead keywords/vendor names) all happens client-side, same
 * heuristic as the Gmail scan.
 */
async function scanOutlookForOrderEmails(vendorNames: string[]): Promise<CandidateEmail[]> {
  currentToken = null; // a fresh scan always re-authorizes
  await requestAccessToken();

  const sinceIso = new Date(Date.now() - SEARCH_WINDOW_DAYS * 24 * 60 * 60 * 1000).toISOString();
  const params = new URLSearchParams({
    $filter: `receivedDateTime ge ${sinceIso}`,
    $orderby: "receivedDateTime desc",
    $top: String(MAX_MESSAGES),
    $select: "id,subject,bodyPreview,receivedDateTime,from",
  });

  const list = (await graphGet(`/me/mailFolders('inbox')/messages?${params.toString()}`)) as {
    value?: GraphMessage[];
  };

  const candidates: CandidateEmail[] = [];
  for (const msg of list.value ?? []) {
    const from = formatFrom(msg.from);
    const subject = msg.subject ?? "";
    const snippet = msg.bodyPreview ?? "";
    const reasons = matchReasons(from, subject, snippet, vendorNames);
    if (reasons.length > 0) {
      candidates.push({
        id: msg.id,
        from,
        subject,
        date: msg.receivedDateTime ?? "",
        snippet,
        matchReasons: reasons,
      });
    }
  }

  return candidates;
}

interface GraphAttachment {
  "@odata.type"?: string;
  name?: string;
  contentType?: string;
  contentBytes?: string;
  size?: number;
}

// Attachment types the AI parser can read directly.
const PARSEABLE_ATTACHMENT_TYPES = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
]);
const MAX_ATTACHMENTS = 3;
const MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024;

function htmlToText(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("style, script, head").forEach((el) => el.remove());
  const text = doc.body?.innerText ?? doc.body?.textContent ?? "";
  return text.replace(/\n{3,}/g, "\n\n").trim();
}

/** Fetch one email's headers, readable body text, and parseable attachments (for View / Record Order). */
async function fetchOutlookEmailDetail(messageId: string): Promise<EmailDetail> {
  const msg = (await graphGet(
    `/me/messages/${messageId}?$select=subject,from,toRecipients,receivedDateTime,body,hasAttachments`
  )) as unknown as GraphMessage;

  const bodyContent = msg.body?.content ?? "";
  const bodyText = msg.body?.contentType === "html" ? htmlToText(bodyContent) : bodyContent.trim();

  const attachments: EmailAttachment[] = [];
  if (msg.hasAttachments) {
    const attachmentList = (await graphGet(`/me/messages/${messageId}/attachments`)) as {
      value?: GraphAttachment[];
    };
    for (const att of attachmentList.value ?? []) {
      if (attachments.length >= MAX_ATTACHMENTS) break;
      if (
        att["@odata.type"] === "#microsoft.graph.fileAttachment" &&
        att.contentType &&
        PARSEABLE_ATTACHMENT_TYPES.has(att.contentType) &&
        att.contentBytes &&
        (att.size ?? 0) <= MAX_ATTACHMENT_BYTES
      ) {
        attachments.push({
          filename: att.name ?? "attachment",
          mimeType: att.contentType,
          base64Data: att.contentBytes,
        });
      }
    }
  }

  return {
    id: messageId,
    from: formatFrom(msg.from),
    to: (msg.toRecipients ?? []).map((r) => formatFrom({ emailAddress: r.emailAddress })).join(", "),
    subject: msg.subject ?? "",
    date: msg.receivedDateTime ?? "",
    bodyText,
    attachments,
  };
}

let cachedFolderId: string | null = null;

async function findOrCreateFolder(folderName: string): Promise<string> {
  if (cachedFolderId) return cachedFolderId;

  const list = (await graphGet(
    `/me/mailFolders?$filter=${encodeURIComponent(`displayName eq '${folderName.replace(/'/g, "''")}'`)}`
  )) as { value?: { id: string; displayName: string }[] };
  const existing = (list.value ?? [])[0];
  if (existing) {
    cachedFolderId = existing.id;
    return existing.id;
  }

  const created = (await graphPost("/me/mailFolders", { displayName: folderName })) as { id: string };
  cachedFolderId = created.id;
  return created.id;
}

/**
 * Move a recorded order's email out of the inbox into the configured orders
 * folder, creating the folder if it doesn't exist yet. Never throws: a
 * missing Mail.ReadWrite grant or any other failure comes back as
 * `{ moved: false }` so the caller can toast it and leave the email alone.
 */
async function moveEmailToOrdersFolder(messageId: string): Promise<MoveEmailResult> {
  try {
    const folderId = await findOrCreateFolder(OUTLOOK_ORDERS_FOLDER_NAME);
    await graphPost(`/me/messages/${messageId}/move`, { destinationId: folderId });
    return { moved: true };
  } catch (err) {
    if (err instanceof GraphApiError && (err.status === 403 || err.status === 401)) {
      return {
        moved: false,
        reason: "permission",
        message: `Outlook didn't grant permission to move this email into "${OUTLOOK_ORDERS_FOLDER_NAME}". The order was still recorded — grant the additional Outlook permission next time you scan if you'd like emails filed automatically.`,
      };
    }
    return {
      moved: false,
      reason: "error",
      message: `Could not move this email into "${OUTLOOK_ORDERS_FOLDER_NAME}" (it's still in your inbox). The order was recorded successfully.`,
    };
  }
}

export const outlookAdapter: EmailProviderAdapter = {
  id: "outlook",
  label: "Outlook",
  configured: Boolean(CLIENT_ID),
  notConfiguredMessage:
    "Outlook scanning isn't configured yet. An administrator needs to set the VITE_MICROSOFT_CLIENT_ID environment variable to an Azure App registration's client ID (registered as a Single Page Application with this site's URL as a redirect URI) and redeploy.",
  ordersFolderName: OUTLOOK_ORDERS_FOLDER_NAME,
  scanForOrderEmails: scanOutlookForOrderEmails,
  fetchEmailDetail: fetchOutlookEmailDetail,
  moveEmailToOrdersFolder,
};
