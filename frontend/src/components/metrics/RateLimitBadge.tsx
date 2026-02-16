"use client";

import { useMetricsStore } from "@/stores/useMetricsStore";

function pct(remaining: number | undefined, limit: number | undefined): number {
  if (!limit || limit === 0) return 100;
  return Math.round(((remaining ?? 0) / limit) * 100);
}

function barColor(percent: number): string {
  if (percent > 50) return "bg-green";
  if (percent > 20) return "bg-yellow";
  return "bg-red";
}

export default function RateLimitBadge() {
  const rateLimits = useMetricsStore((s) => s.rateLimits);
  const currentModel = useMetricsStore((s) => s.currentModel);

  if (!rateLimits) return null;

  const reqPct = pct(rateLimits["requests-remaining"], rateLimits["requests-limit"]);
  const inPct = pct(rateLimits["input-tokens-remaining"], rateLimits["input-tokens-limit"]);
  const outPct = pct(rateLimits["output-tokens-remaining"], rateLimits["output-tokens-limit"]);

  const bars = [
    { label: "REQ", pct: reqPct },
    { label: "IN", pct: inPct },
    { label: "OUT", pct: outPct },
  ];

  return (
    <div className="hidden sm:flex items-center gap-2">
      {/* Model badge */}
      {currentModel && (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-primary/10 text-primary">
          {currentModel}
        </span>
      )}

      {/* Rate bars */}
      <div className="flex items-center gap-1.5 rate-bars-responsive">
        {bars.map((bar) => (
          <div key={bar.label} className="flex items-center gap-1">
            <span className="text-[9px] text-subtext font-medium">
              {bar.label}
            </span>
            <div className="w-8 h-1.5 rounded-full bg-surface2 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${barColor(bar.pct)}`}
                style={{ width: `${bar.pct}%` }}
              />
            </div>
            <span className="text-[9px] text-subtext">
              {bar.pct}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
