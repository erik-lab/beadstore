import { api } from "./apiClient";
import { withTimeout } from "./promiseUtils";

export interface ConnectResult {
  ok: boolean;
  message: string;
}

interface CallbackMessage {
  source?: string;
  ok?: boolean;
  message?: string;
}

const CONNECT_TIMEOUT_MS = 5 * 60_000;

// Same popup-postMessage pattern as lib/emailAccounts.ts's connectEmailAccount —
// see that file for the reasoning. Etsy's own consent screen sits in
// between in production; locally it's the simulator's auto-approve page.
export async function connectEtsyShop(): Promise<ConnectResult> {
  const { url } = await api.get<{ url: string }>("/etsy/connect");

  const popup = window.open(url, "patti-etsy-connect", "width=520,height=680");
  if (!popup) {
    throw new Error("The sign-in popup was blocked. Please allow popups for this site and try again.");
  }

  const messageReceived = new Promise<ConnectResult>((resolve) => {
    function onMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      const data = event.data as CallbackMessage | null;
      if (data?.source !== "patti-etsy-connect") return;
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
