"use client";

import type { ComputerActionMessage } from "@/lib/types";

interface Props {
  message: ComputerActionMessage;
}

const ACTION_ICONS: Record<string, string> = {
  left_click: "🖱️",
  right_click: "🖱️",
  double_click: "🖱️",
  triple_click: "🖱️",
  middle_click: "🖱️",
  mouse_move: "↗️",
  type: "⌨️",
  key: "⌨️",
  scroll: "📜",
  screenshot: "📸",
  left_click_drag: "↔️",
  hold_key: "⌨️",
  wait: "⏳",
  bash: "💻",
  str_replace_based_edit_tool: "📝",
};

export default function ComputerActionBubble({ message }: Props) {
  const icon = ACTION_ICONS[message.action] || ACTION_ICONS[message.tool] || "🔧";

  return (
    <div className="flex items-start gap-2 py-1 px-3 my-0.5 rounded-lg bg-purple/5 border-l-2 border-l-purple/40 text-sm animate-fade-in">
      <span className="shrink-0 mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <span className="text-purple font-medium">{message.description}</span>
        {message.iteration > 0 && (
          <span className="ml-2 text-xs text-subtext/60">#{message.iteration}</span>
        )}
      </div>
    </div>
  );
}
