/**
 * Race a promise against a timeout. Used for OAuth popups — if the user
 * closes the sign-in popup manually rather than completing or explicitly
 * cancelling it, some providers never call back at all, which would
 * otherwise leave calling code (and any "Scanning..." button state) hung
 * forever.
 */
export function withTimeout<T>(promise: Promise<T>, ms: number, timeoutMessage: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(timeoutMessage)), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}
