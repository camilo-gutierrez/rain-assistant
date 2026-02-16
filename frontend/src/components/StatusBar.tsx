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
  const toggleMetrics = useUIStore((s) => s.toggleMetricsDrawer);
  const toggleSettings = useUIStore((s) => s.toggleSettingsDrawer);
  const toggleMobileSidebar = useUIStore((s) => s.toggleMobileSidebar);
  const { t } = useTranslation();

  const dotClass =
    connectionStatus === "connected"
      ? "bg-green"
      : connectionStatus === "error"
      ? "bg-red"
      : "bg-subtext";

  return (
    <header className="flex items-center gap-3 px-4 py-3 bg-surface shadow-sm">
      {/* Mobile hamburger */}
      <button
        onClick={toggleMobileSidebar}
        className="md:hidden p-2 -ml-2 rounded-full hover:bg-surface2 transition-colors text-text2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Connection indicator */}
      <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${dotClass}`} />

      {/* Title */}
      <h1 className="text-sm font-semibold text-text shrink-0">
        Rain Assistant
      </h1>

      {/* Status text */}
      <span className="text-sm text-text2 flex-1 truncate">
        {statusText}
      </span>

      {/* Rate limit badge */}
      {rateLimits && <RateLimitBadge />}

      {/* Metrics toggle */}
      <button
        onClick={toggleMetrics}
        className="p-2 rounded-full hover:bg-surface2 transition-colors text-text2 hover:text-primary"
        title={t("btn.metricsToggle.title")}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      </button>

      {/* Settings toggle */}
      <button
        onClick={toggleSettings}
        className="p-2 rounded-full hover:bg-surface2 transition-colors text-text2 hover:text-primary"
        title={t("btn.settings.title")}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </button>
    </header>
  );
}
