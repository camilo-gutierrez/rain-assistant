"use client";

import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useTranslation } from "@/hooks/useTranslation";
import RateLimitBadge from "@/components/metrics/RateLimitBadge";

export default function StatusBar() {
  const connectionStatus = useConnectionStore((s) => s.connectionStatus);
  const statusText = useConnectionStore((s) => s.statusText);
  const rateLimits = useMetricsStore((s) => s.rateLimits);
  const toggleMetrics = useUIStore((s) => s.toggleMetrics);
  const toggleSettings = useUIStore((s) => s.toggleSettings);
  const { t } = useTranslation();

  // Connection dot color/glow
  const dotClass =
    connectionStatus === "connected"
      ? "bg-green shadow-[0_0_8px_var(--green),0_0_16px_rgba(0,255,136,0.4)]"
      : connectionStatus === "error"
      ? "bg-red shadow-[0_0_8px_var(--red),0_0_16px_rgba(255,34,102,0.4)]"
      : "bg-subtext";

  return (
    <header className="flex items-center gap-2 px-4 py-2.5 bg-surface border-b border-overlay">
      {/* Connection indicator dot */}
      <div
        className={`w-2 h-2 rounded-full shrink-0 ${dotClass}`}
      />

      {/* Title */}
      <h1
        className="font-[family-name:var(--font-orbitron)] text-sm font-bold bg-clip-text text-transparent shrink-0"
        style={{
          backgroundImage: "linear-gradient(135deg, var(--cyan), var(--magenta))",
        }}
      >
        Rain Assistant
      </h1>

      {/* Status text */}
      <span className="text-sm text-text2 flex-1 truncate ml-2">
        {statusText}
      </span>

      {/* Rate limit badge */}
      {rateLimits && <RateLimitBadge />}

      {/* Metrics toggle */}
      <button
        onClick={toggleMetrics}
        className="p-1.5 rounded-md hover:bg-surface2 transition-colors text-text2 hover:text-cyan"
        title={t("btn.metricsToggle.title")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      </button>

      {/* Settings toggle */}
      <button
        onClick={toggleSettings}
        className="p-1.5 rounded-md hover:bg-surface2 transition-colors text-text2 hover:text-cyan"
        title={t("btn.settings.title")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </button>
    </header>
  );
}
