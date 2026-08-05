import type { Theme } from "./types";

// Cached client-side (independent of the backend profile) purely so the
// correct theme can be applied to <html> before React mounts and the
// profile has loaded — avoids a flash of the wrong theme on refresh.
const STORAGE_KEY = "patti-theme";

export function getStoredTheme(): Theme {
  const value = localStorage.getItem(STORAGE_KEY);
  return value === "light" || value === "dark" || value === "system" ? value : "system";
}

export function applyTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
}
