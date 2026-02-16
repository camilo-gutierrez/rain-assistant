import type { AuthResponse, BrowseResponse, ConversationFull, ConversationMeta, HistoryMessage, MetricsData } from "./types";
import { getApiUrl } from "./constants";

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Fetch with automatic retry on 429 (rate limit).
 * Reads the Retry-After header and waits before retrying.
 */
async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 1
): Promise<Response> {
  let res = await fetch(url, options);
  let retries = 0;
  while (res.status === 429 && retries < maxRetries) {
    const retryAfter = parseInt(res.headers.get("Retry-After") || "2", 10);
    const waitMs = Math.min(retryAfter * 1000, 30_000); // cap at 30s
    await new Promise((resolve) => setTimeout(resolve, waitMs));
    res = await fetch(url, options);
    retries++;
  }
  return res;
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
  const res = await fetchWithRetry(
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
  const res = await fetchWithRetry(`${getApiUrl()}/upload-audio`, {
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

// === TTS Synthesis ===

export async function synthesize(
  text: string,
  voice: string,
  rate: string,
  token: string | null
): Promise<Blob | null> {
  const res = await fetchWithRetry(`${getApiUrl()}/synthesize`, {
    method: "POST",
    headers: {
      ...authHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text, voice, rate }),
  });

  // 204 = nothing to synthesize (mostly code)
  if (res.status === 204) return null;
  if (!res.ok) throw new Error(`Synthesize failed: ${res.status}`);

  return res.blob();
}

// === Conversation History ===

export async function listConversations(
  token: string | null
): Promise<{ conversations: ConversationMeta[] }> {
  const res = await fetch(`${getApiUrl()}/history`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`List conversations failed: ${res.status}`);
  return res.json();
}

export async function saveConversation(
  conversation: ConversationFull,
  token: string | null
): Promise<{ saved: boolean; id: string; deleted: string[] }> {
  const res = await fetch(`${getApiUrl()}/history`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(conversation),
  });
  if (!res.ok) throw new Error(`Save conversation failed: ${res.status}`);
  return res.json();
}

export async function loadConversation(
  conversationId: string,
  token: string | null
): Promise<ConversationFull> {
  const res = await fetch(
    `${getApiUrl()}/history/${encodeURIComponent(conversationId)}`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Load conversation failed: ${res.status}`);
  return res.json();
}

export async function deleteConversation(
  conversationId: string,
  token: string | null
): Promise<{ deleted: boolean }> {
  const res = await fetch(
    `${getApiUrl()}/history/${encodeURIComponent(conversationId)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Delete conversation failed: ${res.status}`);
  return res.json();
}
