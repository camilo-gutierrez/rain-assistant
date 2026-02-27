import type { AuthResponse, BrowseResponse, ConversationFull, ConversationMeta, HistoryMessage, MetricsData, Memory, AlterEgo, MarketplaceSkill, MarketplaceCategory, InstalledMarketplaceSkill, SkillUpdate, DeviceInfo, Director, DirectorTask, InboxItem, DirectorTemplate, ActivityItem } from "./types";
import { getApiUrl } from "./constants";

const DEFAULT_TIMEOUT_MS = 30_000;

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Fetch with a timeout via AbortController.
 * Throws "Request timed out" if the request exceeds timeoutMs.
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Fetch with automatic retry on 429 (rate limit) + timeout.
 * Reads the Retry-After header and waits before retrying.
 */
async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 1
): Promise<Response> {
  let res = await fetchWithTimeout(url, options);
  let retries = 0;
  while (res.status === 429 && retries < maxRetries) {
    const rawRetry = Number.parseInt(res.headers.get("Retry-After") || "2", 10);
    const retryAfter = Number.isFinite(rawRetry) && rawRetry > 0 ? rawRetry : 2;
    const waitMs = Math.min(retryAfter * 1000, 30_000); // cap at 30s
    await new Promise((resolve) => setTimeout(resolve, waitMs));
    res = await fetchWithTimeout(url, options);
    retries++;
  }
  return res;
}

export async function authenticate(
  pin: string,
  deviceId: string = "",
  deviceName: string = "",
  replaceDeviceId: string = "",
): Promise<AuthResponse> {
  const body: Record<string, string> = { pin, device_id: deviceId, device_name: deviceName };
  if (replaceDeviceId) body.replace_device_id = replaceDeviceId;
  const res = await fetchWithTimeout(`${getApiUrl()}/auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function fetchDevicesWithPin(
  pin: string,
): Promise<{ devices: DeviceInfo[]; max_devices: number } | null> {
  try {
    const res = await fetchWithTimeout(`${getApiUrl()}/auth/devices`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function revokeDeviceWithPin(pin: string, deviceId: string): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${getApiUrl()}/auth/revoke-device`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin, device_id: deviceId }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data.revoked === true;
  } catch {
    return false;
  }
}

export async function revokeAllWithPin(pin: string): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${getApiUrl()}/auth/revoke-all`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data.revoked_all === true;
  } catch {
    return false;
  }
}

// === Devices ===

export async function fetchDevices(
  token: string | null
): Promise<{ devices: DeviceInfo[]; max_devices: number }> {
  const res = await fetchWithRetry(`${getApiUrl()}/devices`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch devices failed: ${res.status}`);
  return res.json();
}

export async function revokeDevice(
  deviceId: string,
  token: string | null
): Promise<{ revoked: boolean }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/devices/${encodeURIComponent(deviceId)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Revoke device failed: ${res.status}`);
  return res.json();
}

export async function renameDevice(
  deviceId: string,
  name: string,
  token: string | null
): Promise<{ renamed: boolean }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/devices/${encodeURIComponent(deviceId)}`,
    {
      method: "PATCH",
      headers: { ...authHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }
  );
  if (!res.ok) throw new Error(`Rename device failed: ${res.status}`);
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

export async function uploadImage(
  file: File,
  token: string | null
): Promise<{ image_id: string; media_type: string; size: number }> {
  const form = new FormData();
  form.append("image", file);
  const res = await fetchWithRetry(`${getApiUrl()}/upload-image`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `Upload failed: ${res.status}` }));
    throw new Error(err.error || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function uploadImages(
  files: File[],
  token: string | null
): Promise<string[]> {
  const results = await Promise.allSettled(
    files.map((f) => uploadImage(f, token))
  );
  return results
    .filter((r): r is PromiseFulfilledResult<{ image_id: string; media_type: string; size: number }> => r.status === "fulfilled")
    .map((r) => r.value.image_id);
}

export async function loadMessages(
  cwd: string,
  agentId: string,
  token: string | null
): Promise<{ messages: HistoryMessage[] }> {
  const params = new URLSearchParams({ cwd, agent_id: agentId });
  const res = await fetchWithTimeout(`${getApiUrl()}/messages?${params}`, {
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
  const res = await fetchWithTimeout(`${getApiUrl()}/messages?${params}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Clear messages failed: ${res.status}`);
  return res.json();
}

export async function fetchMetrics(
  token: string | null
): Promise<MetricsData> {
  const res = await fetchWithTimeout(`${getApiUrl()}/metrics`, {
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
  const res = await fetchWithTimeout(`${getApiUrl()}/history`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`List conversations failed: ${res.status}`);
  return res.json();
}

export async function saveConversation(
  conversation: ConversationFull,
  token: string | null
): Promise<{ saved: boolean; id: string; deleted: string[] }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/history`, {
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
  const res = await fetchWithTimeout(
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
  const res = await fetchWithTimeout(
    `${getApiUrl()}/history/${encodeURIComponent(conversationId)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Delete conversation failed: ${res.status}`);
  return res.json();
}

// === Memories ===

export async function fetchMemories(
  token: string | null
): Promise<{ memories: Memory[] }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/memories`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch memories failed: ${res.status}`);
  return res.json();
}

export async function addMemory(
  content: string,
  category: string,
  token: string | null
): Promise<{ memory: Memory }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/memories`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ content, category }),
  });
  if (!res.ok) throw new Error(`Add memory failed: ${res.status}`);
  return res.json();
}

export async function deleteMemory(
  memoryId: string,
  token: string | null
): Promise<{ deleted: boolean }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/memories/${encodeURIComponent(memoryId)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Delete memory failed: ${res.status}`);
  return res.json();
}

export async function clearAllMemories(
  token: string | null
): Promise<{ cleared: number }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/memories`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Clear memories failed: ${res.status}`);
  return res.json();
}

// === Alter Egos ===

export async function fetchAlterEgos(
  token: string | null
): Promise<{ egos: AlterEgo[]; active_ego_id: string }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/alter-egos`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch alter egos failed: ${res.status}`);
  return res.json();
}

export async function saveAlterEgo(
  ego: Partial<AlterEgo>,
  token: string | null
): Promise<{ saved: boolean; path: string }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/alter-egos`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(ego),
  });
  if (!res.ok) throw new Error(`Save alter ego failed: ${res.status}`);
  return res.json();
}

export async function deleteAlterEgo(
  egoId: string,
  token: string | null
): Promise<{ deleted: boolean }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/alter-egos/${encodeURIComponent(egoId)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Delete alter ego failed: ${res.status}`);
  return res.json();
}

// === Skills Marketplace ===

export async function searchMarketplaceSkills(
  token: string | null,
  params: { q?: string; category?: string; tag?: string; page?: number } = {}
): Promise<{ skills: MarketplaceSkill[]; total: number; page: number }> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.category) sp.set("category", params.category);
  if (params.tag) sp.set("tag", params.tag);
  if (params.page) sp.set("page", String(params.page));
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/skills?${sp}`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Search skills failed: ${res.status}`);
  return res.json();
}

export async function getMarketplaceCategories(
  token: string | null
): Promise<{ categories: MarketplaceCategory[] }> {
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/categories`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Get categories failed: ${res.status}`);
  return res.json();
}

export async function installMarketplaceSkill(
  skillName: string,
  token: string | null
): Promise<{ installed: boolean; name: string; version: string; requires_env?: string[] }> {
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/install/${encodeURIComponent(skillName)}`,
    { method: "POST", headers: authHeaders(token) }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Install failed: ${res.status}`);
  }
  return res.json();
}

export async function uninstallMarketplaceSkill(
  skillName: string,
  token: string | null
): Promise<{ uninstalled: boolean }> {
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/install/${encodeURIComponent(skillName)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Uninstall failed: ${res.status}`);
  return res.json();
}

export async function getInstalledMarketplaceSkills(
  token: string | null
): Promise<{ skills: InstalledMarketplaceSkill[] }> {
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/installed`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Get installed failed: ${res.status}`);
  return res.json();
}

export async function checkMarketplaceUpdates(
  token: string | null
): Promise<{ updates: SkillUpdate[] }> {
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/updates`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Check updates failed: ${res.status}`);
  return res.json();
}

export async function updateMarketplaceSkill(
  skillName: string,
  token: string | null
): Promise<{ updated: boolean; version: string }> {
  const res = await fetchWithRetry(
    `${getApiUrl()}/marketplace/update/${encodeURIComponent(skillName)}`,
    { method: "POST", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Update failed: ${res.status}`);
  return res.json();
}

// === Autonomous Directors ===

export async function fetchDirectors(
  token: string | null
): Promise<{ directors: Director[] }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/directors`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch directors failed: ${res.status}`);
  return res.json();
}

export async function createDirector(
  data: Partial<Director> & { id: string; name: string; role_prompt: string },
  token: string | null
): Promise<{ director: Director }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/directors`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Create director failed: ${res.status}`);
  }
  return res.json();
}

export async function updateDirector(
  id: string,
  data: Partial<Director>,
  token: string | null
): Promise<{ director: Director }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/directors/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Update director failed: ${res.status}`);
  return res.json();
}

export async function deleteDirector(
  id: string,
  token: string | null
): Promise<{ deleted: boolean }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/directors/${encodeURIComponent(id)}`,
    { method: "DELETE", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Delete director failed: ${res.status}`);
  return res.json();
}

export async function runDirector(
  id: string,
  token: string | null
): Promise<{ queued: boolean; message: string }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/directors/${encodeURIComponent(id)}/run`,
    { method: "POST", headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Run director failed: ${res.status}`);
  return res.json();
}

export async function fetchDirectorTemplates(
  token: string | null
): Promise<{ templates: DirectorTemplate[] }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/directors/templates`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch templates failed: ${res.status}`);
  return res.json();
}

// === Directors Inbox ===

export async function fetchInbox(
  token: string | null,
  params: { status?: string; director_id?: string; content_type?: string; limit?: number; offset?: number } = {}
): Promise<{ items: InboxItem[]; unread_count: number }> {
  const sp = new URLSearchParams();
  if (params.status) sp.set("status", params.status);
  if (params.director_id) sp.set("director_id", params.director_id);
  if (params.content_type) sp.set("content_type", params.content_type);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  const res = await fetchWithTimeout(`${getApiUrl()}/directors/inbox?${sp}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch inbox failed: ${res.status}`);
  return res.json();
}

export async function fetchInboxUnread(
  token: string | null
): Promise<{ count: number }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/directors/inbox/unread`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch unread failed: ${res.status}`);
  return res.json();
}

export async function updateInboxItem(
  id: string,
  status: string,
  comment: string | null,
  token: string | null
): Promise<{ item: InboxItem }> {
  const res = await fetchWithTimeout(
    `${getApiUrl()}/directors/inbox/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { ...authHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({ status, user_comment: comment }),
    }
  );
  if (!res.ok) throw new Error(`Update inbox item failed: ${res.status}`);
  return res.json();
}

// === Directors Tasks ===

export async function fetchDirectorTasks(
  token: string | null,
  params: { status?: string; assignee_id?: string } = {}
): Promise<{ tasks: DirectorTask[]; stats: Record<string, number> }> {
  const sp = new URLSearchParams();
  if (params.status) sp.set("status", params.status);
  if (params.assignee_id) sp.set("assignee_id", params.assignee_id);
  const res = await fetchWithTimeout(`${getApiUrl()}/directors/tasks?${sp}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch tasks failed: ${res.status}`);
  return res.json();
}

// === Directors Activity ===

export async function fetchDirectorActivity(
  token: string | null,
  limit = 20
): Promise<{ activity: ActivityItem[] }> {
  const res = await fetchWithTimeout(`${getApiUrl()}/directors/activity?limit=${limit}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Fetch activity failed: ${res.status}`);
  return res.json();
}
