export const ORIGINAL_TITLE = "Rain Assistant";

export function getApiUrl(): string {
  if (typeof window === "undefined") return "";
  return window.location.origin + "/api";
}

export function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}
