// === Agent Status ===
export type AgentStatus = "idle" | "working" | "done" | "error";

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

export type AnyMessage =
  | UserMessage
  | AssistantMessage
  | SystemMessage
  | ToolUseMessage
  | ToolResultMessage;

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
  | { type: "set_api_key"; key: string }
  | { type: "set_transcription_lang"; lang: string };

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
  | { type: "agent_destroyed"; agent_id: string };

// === Theme & Language ===
export type Theme = "dark" | "light" | "ocean";
export type Language = "en" | "es";

// === Active Panel ===
export type ActivePanel = "pin" | "apiKey" | "fileBrowser" | "chat" | "metrics" | "settings";

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
