"use client";

import { useMetricsStore } from "@/stores/useMetricsStore";
import { Activity } from "lucide-react";

function pct(remaining: number | undefined, limit: number | undefined): number {
  if (!limit || limit === 0) return 100;
  return Math.round(((remaining ?? 0) / limit) * 100);
}

function barColor(percent: number): string {
  if (percent > 50) return "bg-green";
  if (percent > 20) return "bg-yellow";
  return "bg-red";
}

function dotColor(percent: number): string {
  if (percent > 50) return "text-green";
  if (percent > 20) return "text-yellow";
  return "text-red";
}

export default function RateLimitBadge() {
  const rateLimits = useMetricsStore((s) => s.rateLimits);

  if (!rateLimits) return null;

  const reqPct = pct(rateLimits["requests-remaining"], rateLimits["requests-limit"]);
  const inPct = pct(rateLimits["input-tokens-remaining"], rateLimits["input-tokens-limit"]);
  const outPct = pct(rateLimits["output-tokens-remaining"], rateLimits["output-tokens-limit"]);

  const bars = [
    { label: "REQ", pct: reqPct },
    { label: "IN", pct: inPct },
    { label: "OUT", pct: outPct },
  ];

  // Worst (lowest) percentage across all limits for mobile indicator
  const worstPct = Math.min(reqPct, inPct, outPct);
  const mobileAriaLabel = `Rate limits: REQ ${reqPct}%, IN ${inPct}%, OUT ${outPct}%`;

  return (
    <>
      {/* Mobile compact indicator — visible only on small screens */}
      <output
        className="flex sm:hidden items-center justify-center"
        aria-label={mobileAriaLabel}
        title={mobileAriaLabel}
      >
        <Activity size={16} className={`${dotColor(worstPct)} shrink-0`} />
      </output>

      {/* Desktop rate bars — visible on sm+ */}
      <output
        className="hidden sm:flex items-center gap-2"
        aria-label={mobileAriaLabel}
      >
        <div className="flex items-center gap-1.5 rate-bars-responsive">
          {bars.map((bar) => (
            <div key={bar.label} className="flex items-center gap-1">
              <span className="text-xs text-subtext font-medium">
                {bar.label}
              </span>
              <div className="w-8 h-1.5 rounded-full bg-surface2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${barColor(bar.pct)}`}
                  style={{ width: `${bar.pct}%` }}
                />
              </div>
              <span className="text-xs text-subtext">
                {bar.pct}%
              </span>
            </div>
          ))}
        </div>
      </output>
    </>
  );
}
