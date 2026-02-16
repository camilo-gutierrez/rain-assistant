"use client";

import { useEffect, useRef, useLayoutEffect } from "react";
import { useAgentStore } from "@/stores/useAgentStore";
import MessageBubble from "@/components/chat/MessageBubble";
import ToolUseBlock from "@/components/chat/ToolUseBlock";
import ToolResultBlock from "@/components/chat/ToolResultBlock";

export default function ChatMessages() {
  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const saveScrollPos = useAgentStore((s) => s.saveScrollPos);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevAgentIdRef = useRef<string | null>(null);
  const autoScrollRef = useRef(true);

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const messages = activeAgent?.messages || [];

  // Save scroll position when switching away from an agent
  useLayoutEffect(() => {
    if (prevAgentIdRef.current && prevAgentIdRef.current !== activeAgentId) {
      // Save scroll pos for the previous agent
      if (scrollRef.current) {
        saveScrollPos(prevAgentIdRef.current, scrollRef.current.scrollTop);
      }
    }
    prevAgentIdRef.current = activeAgentId;
  }, [activeAgentId, saveScrollPos]);

  // Restore scroll position when switching to an agent
  useLayoutEffect(() => {
    if (!scrollRef.current || !activeAgent) return;
    const el = scrollRef.current;

    if (activeAgent.scrollPos > 0) {
      el.scrollTop = activeAgent.scrollPos;
    } else {
      // Default: scroll to bottom
      el.scrollTop = el.scrollHeight;
    }
  }, [activeAgentId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (!scrollRef.current || !autoScrollRef.current) return;
    const el = scrollRef.current;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, activeAgent?.streamText]);

  // Track if user scrolled away from bottom
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    autoScrollRef.current = atBottom;
  };

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-2"
    >
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
          default:
            return null;
        }
      })}
    </div>
  );
}
