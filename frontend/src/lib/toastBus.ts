export type ToastTone = "info" | "success" | "warn" | "error";

export interface ToastMessage {
  id: string;
  text: string;
  tone: ToastTone;
}

type Listener = (toast: ToastMessage) => void;

const listeners = new Set<Listener>();

export function subscribeToast(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function showToast(text: string, tone: ToastTone = "info"): void {
  const toast: ToastMessage = { id: crypto.randomUUID(), text, tone };
  listeners.forEach((listener) => listener(toast));
}
