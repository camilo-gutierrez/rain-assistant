"use client";

import { useState } from "react";
import type { ComputerScreenshotMessage } from "@/lib/types";

interface Props {
  message: ComputerScreenshotMessage;
}

export default function ScreenshotViewer({ message }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col gap-1 my-1 animate-fade-in">
      <div className="flex items-center gap-2 text-xs text-subtext">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple/10 text-purple font-medium">
          📸 {message.description}
        </span>
        {message.iteration > 0 && (
          <span className="text-subtext/60">paso {message.iteration}</span>
        )}
      </div>
      <img
        src={`data:image/png;base64,${message.image}`}
        alt={message.description}
        className={`rounded-lg border border-overlay cursor-pointer transition-all hover:border-primary/40 ${
          expanded ? "max-w-full" : "max-w-sm"
        }`}
        onClick={() => setExpanded(!expanded)}
      />
    </div>
  );
}
