import type { AuthResponse, BrowseResponse, HistoryMessage, MetricsData } from "./types";
import { getApiUrl } from "./constants";

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function authenticate(pin: string): Promise<AuthResponse> {
  const res = await fetch(`${getApiUrl()}/auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });
  return res.json();
}

export async function browseDirectory(
  path: string,
  token: string | null
): Promise<BrowseResponse> {
  const res = await fetch(
    `${getApiUrl()}/browse?path=${encodeURIComponent(path)}`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Browse failed: ${res.status}`);
  return res.json();
}

export async function uploadAudio(
  blob: Blob,
  token: string | null
): Promise<{ text: string; error?: string }> {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  const res = await fetch(`${getApiUrl()}/upload-audio`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  return res.json();
}

export async function loadMessages(
  cwd: string,
  agentId: string,
  token: string | null
): Promise<{ messages: HistoryMessage[] }> {
  const params = new URLSearchParams({ cwd, agent_id: agentId });
  const res = await fetch(`${getApiUrl()}/messages?${params}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Load messages failed: ${res.status}`);
  return res.json();
}

export async function clearMessages(
  cwd: string,
  agentId: string,
  token: string | null
): Promise<{ deleted: number }> {
  const params = new URLSearchParams({ cwd, agent_id: agentId });
  const res = await fetch(`${getApiUrl()}/messages?${params}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Clear messages failed: ${res.status}`);
  return res.json();
}

export async function fetchMetrics(
  token: string | null
): Promise<MetricsData> {
  const res = await fetch(`${getApiUrl()}/metrics`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch metrics failed: ${res.status}`);
  return res.json();
}
