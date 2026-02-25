"use client";

import { useEffect, useRef, useLayoutEffect, useState } from "react";
import { ArrowDown } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useTranslation } from "@/hooks/useTranslation";
import MessageBubble from "@/components/chat/MessageBubble";
import ToolUseBlock from "@/components/chat/ToolUseBlock";
import ToolResultBlock from "@/components/chat/ToolResultBlock";
import PermissionRequestBlock from "@/components/chat/PermissionRequestBlock";
import ScreenshotViewer from "@/components/computer-use/ScreenshotViewer";
import ComputerActionBubble from "@/components/computer-use/ComputerActionBubble";
import SubAgentIndicator from "@/components/chat/SubAgentIndicator";

function MessageSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4 animate-fade-in">
      <div className="self-end w-48 h-10 rounded-2xl shimmer-bg" />
      <div className="self-start w-64 h-16 rounded-2xl shimmer-bg" />
      <div className="self-start w-40 h-10 rounded-2xl shimmer-bg" />
    </div>
  );
}

export default function ChatMessages() {
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const saveScrollPos = useAgentStore((s) => s.saveScrollPos);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevAgentIdRef = useRef<string | null>(null);
  const autoScrollRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const messages = activeAgent?.messages || [];

  useLayoutEffect(() => {
    if (prevAgentIdRef.current && prevAgentIdRef.current !== activeAgentId) {
      if (scrollRef.current) {
        saveScrollPos(prevAgentIdRef.current, scrollRef.current.scrollTop);
      }
    }
    prevAgentIdRef.current = activeAgentId;
  }, [activeAgentId, saveScrollPos]);

  useLayoutEffect(() => {
    if (!scrollRef.current || !activeAgent) return;
    const el = scrollRef.current;

    if (activeAgent.scrollPos > 0) {
      el.scrollTop = activeAgent.scrollPos;
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [activeAgentId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!scrollRef.current || !autoScrollRef.current) return;
    const el = scrollRef.current;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, activeAgent?.streamText]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    autoScrollRef.current = atBottom;
    setShowScrollBtn(!atBottom);
  };

  const scrollToBottom = () => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    autoScrollRef.current = true;
    setShowScrollBtn(false);
  };

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-4 md:px-8 py-3 flex flex-col gap-2 bg-bg"
      >
        <div className="max-w-3xl mx-auto w-full flex flex-col gap-2">
          {messages.length === 0 && activeAgent?.isProcessing && (
            <MessageSkeleton />
          )}
          {messages.map((msg) => {
            switch (msg.type) {
              case "user":
              case "assistant":
              case "system":
                return <MessageBubble key={msg.id} message={msg} />;
              case "tool_use":
                return <ToolUseBlock key={msg.id} message={msg} />;
              case "tool_result":
                return <ToolResultBlock key={msg.id} message={msg} />;
              case "permission_request":
                return <PermissionRequestBlock key={msg.id} message={msg} />;
              case "computer_screenshot":
                return <ScreenshotViewer key={msg.id} message={msg} />;
              case "computer_action":
                return <ComputerActionBubble key={msg.id} message={msg} />;
              case "subagent_event":
                return <SubAgentIndicator key={msg.id} message={msg} />;
              default:
                return null;
            }
          })}
        </div>
      </div>

      {/* Scroll to bottom FAB */}
      <button
        onClick={scrollToBottom}
        className={`absolute bottom-4 left-1/2 -translate-x-1/2 z-10
          flex items-center justify-center w-9 h-9 rounded-full
          bg-surface border border-overlay text-text2
          shadow-[var(--shadow-2)] hover:bg-surface2 hover:text-primary
          transition-all duration-200 cursor-pointer
          ${showScrollBtn ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-2 scale-90 pointer-events-none"}`}
        title={t("chat.scrollToBottom")}
        aria-label={t("chat.scrollToBottom")}
      >
        <ArrowDown size={18} />
      </button>
    </div>
  );
}
