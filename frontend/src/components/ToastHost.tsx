import { useEffect, useState } from "react";
import { subscribeToast, type ToastMessage } from "../lib/toastBus";

const AUTO_DISMISS_MS = 8000;

export function ToastHost() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    return subscribeToast((toast) => {
      setToasts((prev) => [...prev, toast]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id));
      }, AUTO_DISMISS_MS);
    });
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-host">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.tone}`}>
          <span>{toast.text}</span>
          <button
            type="button"
            className="toast-close"
            aria-label="Dismiss"
            onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
