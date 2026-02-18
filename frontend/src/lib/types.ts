// === Agent Status ===
export type AgentStatus = "idle" | "working" | "done" | "error";

// === Agent Mode ===
export type AgentMode = "coding" | "computer_use";

// === Display Info (from server) ===
export interface DisplayInfo {
  screen_width: number;
  screen_height: number;
  scaled_width: number;
  scaled_height: number;
  scale_factor: number;
}

// === Chat Messages ===
export interface BaseMessage {
  id: string;
  timestamp: number;
  animate: boolean;
}

export interface UserMessage extends BaseMessage {
  type: "user";
  text: string;
}

export interface AssistantMessage extends BaseMessage {
  type: "assistant";
  text: string;
  isStreaming: boolean;
}

export interface SystemMessage extends BaseMessage {
  type: "system";
  text: string;
}

export interface ToolUseMessage extends BaseMessage {
  type: "tool_use";
  tool: string;
  input: Record<string, unknown>;
  toolUseId: string;
}

export interface ToolResultMessage extends BaseMessage {
  type: "tool_result";
  content: string;
  isError: boolean;
  toolUseId: string;
}

export interface PermissionRequestMessage extends BaseMessage {
  type: "permission_request";
  requestId: string;
  tool: string;
  input: Record<string, unknown>;
  level: "yellow" | "red" | "computer";
  reason: string;
  status: "pending" | "approved" | "denied" | "expired";
}

// === Computer Use Messages ===
export interface ComputerScreenshotMessage extends BaseMessage {
  type: "computer_screenshot";
  image: string;        // base64 PNG
  action: string;       // "left_click", "type", "initial", etc.
  description: string;  // Human-readable description
  iteration: number;
}

export interface ComputerActionMessage extends BaseMessage {
  type: "computer_action";
  tool: string;
  action: string;
  input: Record<string, unknown>;
  description: string;
  iteration: number;
}

export type AnyMessage =
  | UserMessage
  | AssistantMessage
  | SystemMessage
  | ToolUseMessage
  | ToolResultMessage
  | PermissionRequestMessage
  | ComputerScreenshotMessage
  | ComputerActionMessage;

// === Agent ===
export type AgentPanel = "fileBrowser" | "chat";

export interface Agent {
  id: string;
  cwd: string | null;
  currentBrowsePath: string;
  label: string;
  status: AgentStatus;
  unread: number;
  messages: AnyMessage[];
  scrollPos: number;
  streamText: string;
  streamMessageId: string | null;
  isProcessing: boolean;
  interruptPending: boolean;
  interruptTimerId: ReturnType<typeof setTimeout> | null;
  historyLoaded: boolean;
  sessionId: string | null;
  activePanel: AgentPanel;
  // Computer Use fields
  mode: AgentMode;
  displayInfo: DisplayInfo | null;
  lastScreenshot: string | null;
  computerIteration: number;
}

// === Rate Limits ===
export interface RateLimits {
  "requests-limit"?: number;
  "requests-remaining"?: number;
  "requests-reset"?: string;
  "input-tokens-limit"?: number;
  "input-tokens-remaining"?: number;
  "input-tokens-reset"?: string;
  "output-tokens-limit"?: number;
  "output-tokens-remaining"?: number;
  "output-tokens-reset"?: string;
}

// === Metrics ===
export interface MetricsTotals {
  cost: number;
  sessions: number;
  avg_duration_ms: number;
  avg_cost: number;
  total_turns: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface MetricsData {
  totals: {
    all_time: MetricsTotals;
    today: MetricsTotals;
    this_week: MetricsTotals;
    this_month: MetricsTotals;
  };
  by_hour: Array<{ hour: number; cost: number; sessions: number }>;
  by_dow: Array<{ name: string; cost: number; sessions: number }>;
  by_day: Array<{ day: string; cost: number; sessions: number; duration_ms?: number }>;
  by_month: Array<{ month: string; cost: number; sessions: number; duration_ms?: number }>;
}

// === WebSocket Send Messages ===
export type WSSendMessage =
  | { type: "send_message"; text: string; agent_id: string }
  | { type: "interrupt"; agent_id: string }
  | { type: "set_cwd"; path: string; agent_id: string; session_id?: string }
  | { type: "destroy_agent"; agent_id: string }
  | { type: "set_api_key"; key: string; provider: AIProvider; model: string }
  | { type: "set_transcription_lang"; lang: string }
  | { type: "permission_response"; request_id: string; agent_id: string; approved: boolean; pin?: string }
  | { type: "set_mode"; agent_id: string; mode: AgentMode }
  | { type: "emergency_stop"; agent_id: string }
  | { type: "set_alter_ego"; ego_id: string }
  | { type: "pong" };

// === WebSocket Receive Messages ===
export type WSReceiveMessage =
  | { type: "status"; text: string; cwd?: string; agent_id: string | null }
  | { type: "assistant_text"; text: string; agent_id: string }
  | { type: "tool_use"; tool: string; input: Record<string, unknown>; id: string; agent_id: string }
  | { type: "tool_result"; content: string; is_error: boolean; tool_use_id: string; agent_id: string }
  | { type: "model_info"; model: string; agent_id: string }
  | { type: "rate_limits"; limits: RateLimits; agent_id: string }
  | {
      type: "result";
      text: string;
      usage?: { input_tokens: number; output_tokens: number };
      cost?: number;
      duration_ms?: number;
      num_turns?: number;
      is_error: boolean;
      session_id?: string;
      agent_id: string;
    }
  | { type: "error"; text: string; agent_id: string }
  | { type: "agent_destroyed"; agent_id: string }
  | {
      type: "permission_request";
      request_id: string;
      agent_id: string;
      tool: string;
      input: Record<string, unknown>;
      level: "yellow" | "red" | "computer";
      reason: string;
    }
  | { type: "mode_changed"; agent_id: string; mode: AgentMode; display_info?: DisplayInfo }
  | { type: "computer_screenshot"; agent_id: string; image: string; action: string; description: string; iteration: number }
  | { type: "computer_action"; agent_id: string; tool: string; action: string; input: Record<string, unknown>; description: string; iteration: number }
  | { type: "ping"; ts: number }
  | { type: "api_key_loaded"; provider: AIProvider }
  | { type: "alter_ego_changed"; ego_id: string; agent_id: string };

// === AI Provider ===
export type AIProvider = "claude" | "openai" | "gemini";

export interface ProviderModelInfo {
  id: string;
  name: string;
}

export const PROVIDER_MODELS: Record<AIProvider, ProviderModelInfo[]> = {
  claude: [
    { id: "auto", name: "Auto (SDK)" },
  ],
  openai: [
    { id: "gpt-4o", name: "GPT-4o" },
    { id: "gpt-4o-mini", name: "GPT-4o Mini" },
    { id: "gpt-4.1", name: "GPT-4.1" },
    { id: "gpt-4.1-mini", name: "GPT-4.1 Mini" },
    { id: "gpt-4.1-nano", name: "GPT-4.1 Nano" },
    { id: "o3-mini", name: "o3-mini" },
    { id: "o4-mini", name: "o4-mini" },
  ],
  gemini: [
    { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro" },
    { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash" },
    { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash" },
    { id: "gemini-2.0-flash-lite", name: "Gemini 2.0 Flash Lite" },
  ],
};

export const PROVIDER_INFO: Record<AIProvider, {
  name: string;
  keyPlaceholder: string;
  consoleUrl: string;
  consoleName: string;
}> = {
  claude: {
    name: "Claude",
    keyPlaceholder: "sk-ant-...",
    consoleUrl: "https://console.anthropic.com",
    consoleName: "console.anthropic.com",
  },
  openai: {
    name: "OpenAI",
    keyPlaceholder: "sk-...",
    consoleUrl: "https://platform.openai.com/api-keys",
    consoleName: "platform.openai.com",
  },
  gemini: {
    name: "Gemini",
    keyPlaceholder: "AIza...",
    consoleUrl: "https://aistudio.google.com/apikey",
    consoleName: "aistudio.google.com",
  },
};

// === Model Name Formatting ===
const MODEL_SHORT_NAMES: Record<string, string> = {
  "claude-sonnet-4-5-20250929": "Sonnet 4.5",
  "claude-sonnet-4-20250514": "Sonnet 4",
  "claude-opus-4-20250514": "Opus 4",
  "claude-opus-4-6": "Opus 4.6",
  "claude-haiku-3-5-20241022": "Haiku 3.5",
  "claude-3-5-sonnet-20241022": "Sonnet 3.5",
  "claude-3-5-haiku-20241022": "Haiku 3.5",
};

export function formatModelName(rawModel: string): string {
  if (MODEL_SHORT_NAMES[rawModel]) return MODEL_SHORT_NAMES[rawModel];
  // Try partial match (model IDs can have date suffixes)
  for (const [key, name] of Object.entries(MODEL_SHORT_NAMES)) {
    if (rawModel.startsWith(key.replace(/-\d{8}$/, ""))) return name;
  }
  return rawModel.length > 24 ? rawModel.slice(0, 22) + "..." : rawModel;
}

// === Theme & Language ===
export type Theme = "light" | "dark";
export type Language = "en" | "es";

// === TTS ===
export type TTSVoice =
  | "es-MX-DaliaNeural"
  | "es-MX-JorgeNeural"
  | "en-US-JennyNeural"
  | "en-US-GuyNeural";

export type TTSPlaybackState = "idle" | "loading" | "playing";

// === Memories ===
export interface Memory {
  id: string;
  content: string;
  category: "preference" | "fact" | "pattern" | "project";
  created_at: string;
}

// === Alter Egos ===
export interface AlterEgo {
  id: string;
  name: string;
  emoji: string;
  description: string;
  system_prompt: string;
  color: string;
  is_builtin: boolean;
}

// === Active Panel ===
export type ActivePanel = "pin" | "apiKey" | "fileBrowser" | "chat";

// === File Browser ===
export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

export interface BrowseResponse {
  current: string;
  entries: FileEntry[];
}

// === Auth ===
export interface AuthResponse {
  token?: string;
  error?: string;
  remaining_attempts?: number;
  locked?: boolean;
  remaining_seconds?: number;
}

// === History Message (from API) ===
export interface HistoryMessage {
  id: number;
  role: string;
  type: string;
  content: Record<string, unknown>;
  timestamp: number;
}

// === Conversation History ===
export interface ConversationMeta {
  id: string;
  createdAt: number;
  updatedAt: number;
  label: string;
  cwd: string;
  messageCount: number;
  preview: string;
  totalCost: number;
}

export interface ConversationFull extends ConversationMeta {
  version: number;
  agentId: string;
  sessionId: string | null;
  messages: AnyMessage[];
}
