import { api } from "./apiClient";
import { withTimeout } from "./promiseUtils";
import type { EmailAccount, EmailProvider } from "./types";

export function listEmailAccounts(): Promise<EmailAccount[]> {
  return api.get<EmailAccount[]>("/email-accounts");
}

export function deleteEmailAccount(id: string): Promise<void> {
  return api.delete(`/email-accounts/${id}`);
}

export interface ConnectResult {
  ok: boolean;
  message: string;
}

// Wide backstop — this spans the user's actual sign-in on Google's/Microsoft's
// own site, not just a single request, so it needs much more room than the
// old direct-popup timeout did.
const CONNECT_TIMEOUT_MS = 5 * 60_000;

interface CallbackMessage {
  source?: string;
  ok?: boolean;
  message?: string;
}

/**
 * Open the OAuth consent popup for `provider` and resolve once it's done.
 * The popup's own callback page always posts a message back with { ok,
 * message } before closing itself — success or failure alike — so this
 * reliably reports what actually happened server-side instead of assuming
 * success just because the popup closed. Only a genuinely ambiguous case
 * (the user closes the popup manually before the callback ever runs) falls
 * back to a generic "cancelled" result.
 */
export async function connectEmailAccount(provider: EmailProvider): Promise<ConnectResult> {
  const { url } = await api.get<{ url: string }>(`/email-accounts/${provider}/connect`);

  const popup = window.open(url, "patti-email-connect", "width=520,height=680");
  if (!popup) {
    throw new Error("The sign-in popup was blocked. Please allow popups for this site and try again.");
  }

  const messageReceived = new Promise<ConnectResult>((resolve) => {
    function onMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      const data = event.data as CallbackMessage | null;
      if (data?.source !== "patti-email-account-connect") return;
      window.removeEventListener("message", onMessage);
      resolve({ ok: data.ok === true, message: data.message ?? "" });
    }
    window.addEventListener("message", onMessage);
  });

  const popupClosedWithoutMessage = new Promise<ConnectResult>((resolve) => {
    const check = setInterval(() => {
      if (popup.closed) {
        clearInterval(check);
        resolve({ ok: false, message: "Sign-in was cancelled." });
      }
    }, 500);
  });

  return withTimeout(
    Promise.race([messageReceived, popupClosedWithoutMessage]),
    CONNECT_TIMEOUT_MS,
    "Sign-in timed out. Please try again."
  );
}
