import type { CandidateEmail } from "./emailScanTypes";

// Keeps a provider's last scan results (and which ones were already
// recorded) around in sessionStorage, keyed per adapter, so navigating away
// from Order Email Scan and back doesn't lose the list — only a fresh scan
// or closing the tab does. Deliberately not localStorage: email contents are
// sensitive enough that they shouldn't outlive the browser session.
interface StoredScanState {
  results: CandidateEmail[] | null;
  recordedIds: Record<string, string>;
}

const EMPTY_STATE: StoredScanState = { results: null, recordedIds: {} };

function storageKey(adapterId: string): string {
  return `patti-email-scan-${adapterId}`;
}

export function loadScanState(adapterId: string): StoredScanState {
  try {
    const raw = sessionStorage.getItem(storageKey(adapterId));
    if (!raw) return EMPTY_STATE;
    const parsed = JSON.parse(raw);
    return {
      results: Array.isArray(parsed.results) ? parsed.results : null,
      recordedIds: typeof parsed.recordedIds === "object" && parsed.recordedIds ? parsed.recordedIds : {},
    };
  } catch {
    return EMPTY_STATE;
  }
}

export function saveScanState(adapterId: string, state: StoredScanState): void {
  try {
    sessionStorage.setItem(storageKey(adapterId), JSON.stringify(state));
  } catch {
    // sessionStorage unavailable (private browsing quota, etc.) — the list
    // just won't survive a navigation away and back this time.
  }
}
