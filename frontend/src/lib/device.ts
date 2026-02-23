const DEVICE_ID_KEY = "rain-device-id";
const DEVICE_NAME_KEY = "rain-device-name";

export function getDeviceId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

export function getDeviceName(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(DEVICE_NAME_KEY) || detectDeviceName();
}

export function setDeviceName(name: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(DEVICE_NAME_KEY, name);
  }
}

function detectDeviceName(): string {
  const ua = navigator.userAgent;
  if (/Mobile|Android/i.test(ua)) return "Mobile Browser";
  if (/Windows/i.test(ua)) return "Windows PC";
  if (/Mac/i.test(ua)) return "Mac";
  if (/Linux/i.test(ua)) return "Linux PC";
  return "Web Browser";
}
