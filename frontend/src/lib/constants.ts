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

/**
 * Returns true if the current connection is considered secure:
 * - HTTPS, or
 * - localhost / 127.0.0.1 (development)
 */
export function isSecureContext(): boolean {
  if (typeof window === "undefined") return true;
  const { protocol, hostname } = window.location;
  if (protocol === "https:") return true;
  if (hostname === "localhost" || hostname === "127.0.0.1") return true;
  return false;
}
