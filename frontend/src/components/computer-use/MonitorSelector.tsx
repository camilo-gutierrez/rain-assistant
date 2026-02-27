"use client";

import { usePopover } from "@/hooks/usePopover";
import { useTranslation } from "@/hooks/useTranslation";
import type { MonitorInfo } from "@/lib/types";

interface Props {
  readonly monitors: MonitorInfo[];
  readonly currentIndex: number;
  readonly onSelect: (index: number) => void;
}

export default function MonitorSelector({ monitors, currentIndex, onSelect }: Props) {
  const { ref, isOpen, toggle } = usePopover<HTMLDivElement>();
  const { t } = useTranslation();

  // Only show if there are multiple monitors
  if (monitors.length <= 1) return null;

  const current = monitors.find((m) => m.index === currentIndex);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-subtext hover:text-text hover:bg-surface2 transition-colors focus-ring"
        title={t("cu.monitorSelector")}
      >
        <span>{t("cu.monitor")} {currentIndex}</span>
        {current && (
          <span className="text-subtext/60">{current.width}x{current.height}</span>
        )}
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 py-1 bg-surface border border-overlay rounded-lg shadow-lg z-50 min-w-48">
          {monitors.map((mon) => (
            <button
              key={mon.index}
              type="button"
              onClick={() => {
                onSelect(mon.index);
                toggle();
              }}
              className={`w-full text-left px-3 py-1.5 text-sm flex items-center justify-between hover:bg-surface2 transition-colors ${
                mon.index === currentIndex ? "text-primary font-medium" : "text-text"
              }`}
            >
              <span>
                {t("cu.monitor")} {mon.index}
                {mon.primary && (
                  <span className="ml-1.5 text-xs text-subtext">({t("cu.primaryMonitor")})</span>
                )}
              </span>
              <span className="text-xs text-subtext tabular-nums">
                {mon.width}x{mon.height}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
