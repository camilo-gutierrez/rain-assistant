"use client";

import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useTranslation } from "@/hooks/useTranslation";
import RateLimitBadge from "@/components/metrics/RateLimitBadge";
import ModelSwitcher from "@/components/ModelSwitcher";
import EgoSwitcher from "@/components/EgoSwitcher";
import { Menu, Settings, BarChart3, Brain, Store } from "lucide-react";

export default function StatusBar() {
  const connectionStatus = useConnectionStore((s) => s.connectionStatus);
  const statusText = useConnectionStore((s) => s.statusText);
  const rateLimits = useMetricsStore((s) => s.rateLimits);
  const toggleMetrics = useUIStore((s) => s.toggleMetricsDrawer);
  const toggleSettings = useUIStore((s) => s.toggleSettingsDrawer);
  const toggleMemories = useUIStore((s) => s.toggleMemoriesDrawer);
  const toggleMarketplace = useUIStore((s) => s.toggleMarketplaceDrawer);
  const toggleMobileSidebar = useUIStore((s) => s.toggleMobileSidebar);
  const { t } = useTranslation();

  const dotClass =
    connectionStatus === "connected"
      ? "bg-green"
      : connectionStatus === "error"
      ? "bg-red"
      : "bg-subtext";

  return (
    <header className="flex items-center gap-2 px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))] bg-surface shadow-sm">
      {/* Mobile hamburger */}
      <button
        onClick={toggleMobileSidebar}
        className="md:hidden min-w-[44px] min-h-[44px] flex items-center justify-center -ml-2 rounded-full hover:bg-surface2 transition-colors text-text2 focus-ring"
        aria-label="Menu"
        title="Menu"
      >
        <Menu size={20} />
      </button>

      {/* Connection indicator */}
      <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${dotClass}`} />

      {/* Ego Switcher (replaces static "Rain Assistant" title) */}
      <EgoSwitcher />

      {/* Status text */}
      <span className="text-sm text-text2 flex-1 truncate">
        {statusText}
      </span>

      {/* Model/Provider quick-switch */}
      <ModelSwitcher />

      {/* Rate limit badge */}
      {rateLimits && <RateLimitBadge />}

      {/* Memories toggle */}
      <button
        onClick={toggleMemories}
        className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-full hover:bg-surface2 transition-colors text-text2 hover:text-primary focus-ring"
        aria-label={t("memories.title")}
        title={t("memories.title")}
      >
        <Brain size={20} />
      </button>

      {/* Marketplace toggle */}
      <button
        onClick={toggleMarketplace}
        className="hidden md:flex min-w-[44px] min-h-[44px] items-center justify-center rounded-full hover:bg-surface2 transition-colors text-text2 hover:text-primary focus-ring"
        aria-label={t("marketplace.title")}
        title={t("marketplace.title")}
      >
        <Store size={20} />
      </button>

      {/* Metrics toggle — hidden on mobile (available in bottom nav) */}
      <button
        onClick={toggleMetrics}
        className="hidden md:flex min-w-[44px] min-h-[44px] items-center justify-center rounded-full hover:bg-surface2 transition-colors text-text2 hover:text-primary focus-ring"
        aria-label={t("btn.metricsToggle.title")}
        title={t("btn.metricsToggle.title")}
      >
        <BarChart3 size={20} />
      </button>

      {/* Settings toggle — hidden on mobile (available in bottom nav) */}
      <button
        onClick={toggleSettings}
        className="hidden md:flex min-w-[44px] min-h-[44px] items-center justify-center rounded-full hover:bg-surface2 transition-colors text-text2 hover:text-primary focus-ring"
        aria-label={t("btn.settings.title")}
        title={t("btn.settings.title")}
      >
        <Settings size={20} />
      </button>
    </header>
  );
}
