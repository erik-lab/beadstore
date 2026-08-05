import { api } from "./apiClient";
import { withTimeout } from "./promiseUtils";
import type { EmailAccount, EmailProvider } from "./types";

export function listEmailAccounts(): Promise<EmailAccount[]> {
  return api.get<EmailAccount[]>("/email-accounts");
}

export function deleteEmailAccount(id: string): Promise<void> {
  return api.delete(`/email-accounts/${id}`);
}

// Wide backstop — this spans the user's actual sign-in on Google's/Microsoft's
// own site, not just a single request, so it needs much more room than the
// old direct-popup timeout did.
const CONNECT_TIMEOUT_MS = 5 * 60_000;

/**
 * Open the OAuth consent popup for `provider` and resolve once it's done —
 * either the provider's callback posted a "connected" message back to this
 * window, or the popup was closed (completed, cancelled, or blocked partway
 * through). Doesn't distinguish success from cancellation; the caller just
 * reloads the account list afterward and reflects whatever actually
 * happened server-side.
 */
export async function connectEmailAccount(provider: EmailProvider): Promise<void> {
  const { url } = await api.get<{ url: string }>(`/email-accounts/${provider}/connect`);

  const popup = window.open(url, "patti-email-connect", "width=520,height=680");
  if (!popup) {
    throw new Error("The sign-in popup was blocked. Please allow popups for this site and try again.");
  }

  const popupClosed = new Promise<void>((resolve) => {
    const check = setInterval(() => {
      if (popup.closed) {
        clearInterval(check);
        resolve();
      }
    }, 500);
  });

  const messageReceived = new Promise<void>((resolve) => {
    function onMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if ((event.data as { source?: string } | null)?.source !== "patti-email-account-connect") return;
      window.removeEventListener("message", onMessage);
      resolve();
    }
    window.addEventListener("message", onMessage);
  });

  await withTimeout(Promise.race([popupClosed, messageReceived]), CONNECT_TIMEOUT_MS, "Sign-in timed out. Please try again.");
  // The popup's own script posts the message and then calls window.close()
  // in the same tick, so popupClosed and messageReceived usually settle
  // together — this just gives a slower browser a beat to deliver the
  // message before we treat "popup closed" as the final word.
  await new Promise((resolve) => setTimeout(resolve, 300));
}
