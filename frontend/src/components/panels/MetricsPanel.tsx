"use client";

import { useEffect, useState } from "react";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import { RefreshCw } from "lucide-react";

// --- Skeleton ---

function MetricsSkeleton() {
  return (
    <div className="space-y-5">
      <div className="bg-surface rounded-xl shadow-sm p-5">
        <div className="h-3 w-24 rounded shimmer-bg mb-3" />
        <div className="h-8 w-32 rounded shimmer-bg mb-2" />
        <div className="h-3 w-40 rounded shimmer-bg" />
      </div>
      <div className="bg-surface rounded-xl shadow-sm flex divide-x divide-overlay/50">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex-1 p-3.5 flex flex-col items-center gap-2">
            <div className="h-6 w-12 rounded shimmer-bg" />
            <div className="h-3 w-16 rounded shimmer-bg" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-surface rounded-xl shadow-sm p-3.5">
            <div className="h-3 w-12 rounded shimmer-bg mb-2" />
            <div className="h-6 w-16 rounded shimmer-bg" />
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Sub-components ---

function BarChart({
  title,
  data,
  labelKey,
  valueKey,
  formatValue,
  subKey,
  formatSub,
}: {
  title: string;
  data: Array<Record<string, unknown>>;
  labelKey: string;
  valueKey: string;
  formatValue?: (v: number) => string;
  subKey?: string;
  formatSub?: (v: number) => string;
}) {
  if (!data || data.length === 0) return null;

  const maxVal = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 0.001);

  return (
    <div className="bg-surface rounded-xl shadow-sm p-4">
      <h4 className="text-[11px] text-text2 uppercase tracking-wider font-semibold mb-3">
        {title}
      </h4>
      <div className="flex items-end gap-[3px] h-[140px] border-b border-overlay/50 pb-1">
        {data.map((d, i) => {
          const val = Number(d[valueKey]) || 0;
          const pct = (val / maxVal) * 100;
          const label = String(d[labelKey]);
          const formatted = formatValue ? formatValue(val) : val.toFixed(2);
          const subVal = subKey ? Number(d[subKey]) || 0 : 0;
          const subFormatted = formatSub ? formatSub(subVal) : "";

          return (
            <div
              key={i}
              className="group relative flex-1 flex flex-col items-center justify-end gap-1 min-w-0"
            >
              {/* Tooltip on hover */}
              <div className="absolute -top-7 left-1/2 -translate-x-1/2 hidden group-hover:block z-10">
                <div className="bg-text text-surface text-[9px] font-medium px-1.5 py-0.5 rounded whitespace-nowrap shadow-lg">
                  {formatted}
                </div>
              </div>
              <div
                className="w-full max-w-[20px] rounded-t-sm transition-all duration-300 group-hover:opacity-80"
                style={{
                  height: `${Math.max(pct, 2)}%`,
                  background: `linear-gradient(to top, var(--primary-dark), var(--primary))`,
                }}
              />
              <span className="text-[9px] text-subtext truncate w-full text-center leading-tight">
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RateLimitGauge({
  label,
  remaining,
  limit,
  reset,
}: {
  label: string;
  remaining?: number;
  limit?: number;
  reset?: string;
}) {
  if (!limit) return null;
  const pct = Math.round(((remaining ?? 0) / limit) * 100);
  const fillColor =
    pct > 50 ? "var(--green)" : pct > 20 ? "var(--yellow)" : "var(--red)";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-center">
        <span className="text-[11px] font-medium text-text2">{label}</span>
        <span className="text-[10px] text-subtext tabular-nums">
          {remaining?.toLocaleString()} / {limit?.toLocaleString()}
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-surface2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${pct}%`, background: fillColor }}
        />
      </div>
      {reset && (
        <span className="text-[9px] text-subtext">Reset: {reset}</span>
      )}
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms < 60000) return (ms / 1000).toFixed(0) + "s";
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

// --- Main MetricsPanel ---

export default function MetricsPanel() {
  const metricsData = useMetricsStore((s) => s.metricsData);
  const rateLimits = useMetricsStore((s) => s.rateLimits);
  const currentModel = useMetricsStore((s) => s.currentModel);
  const fetchMetrics = useMetricsStore((s) => s.fetchMetrics);
  const authToken = useConnectionStore((s) => s.authToken);
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    handleRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    await fetchMetrics(authToken, true);
    setLoading(false);
  };

  const totals = metricsData?.totals?.all_time;

  const periodColors = {
    today: "border-t-primary",
    this_week: "border-t-green",
    this_month: "border-t-blue",
  } as const;

  return (
    <div className="flex-1 flex flex-col overflow-y-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-text">
          {t("metrics.title")}
        </h2>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg text-primary hover:bg-primary/10 transition-colors disabled:opacity-50 font-medium focus-ring"
        >
          <RefreshCw size={14} className={loading ? "animate-spin-slow" : ""} />
          {!loading && t("metrics.refresh")}
        </button>
      </div>

      {loading && !metricsData ? (
        <MetricsSkeleton />
      ) : !metricsData || !totals ? (
        <div className="flex-1 flex items-center justify-center text-text2 text-sm">
          {t("metrics.noData")}
        </div>
      ) : (
        <div className="space-y-5">
          {/* Hero — Total Cost */}
          <div className="bg-surface rounded-xl shadow-sm border-l-4 border-l-primary p-5">
            <span className="text-[11px] text-subtext uppercase tracking-wider font-semibold">
              {t("metrics.totalSpent")}
            </span>
            <div className="text-3xl font-bold text-text mt-1 tabular-nums">
              ${totals.cost.toFixed(2)}
            </div>
            <span className="text-[11px] text-text2">
              {t("metrics.avgCost")}: ${totals.avg_cost.toFixed(4)}
            </span>
          </div>

          {/* Summary row — 3 stats */}
          <div className="bg-surface rounded-xl shadow-sm flex divide-x divide-overlay/50">
            <div className="flex-1 p-3.5 text-center">
              <div className="text-xl font-bold text-text tabular-nums">
                {totals.sessions}
              </div>
              <div className="text-[10px] text-subtext uppercase tracking-wider font-medium mt-0.5">
                {t("metrics.sessions")}
              </div>
            </div>
            <div className="flex-1 p-3.5 text-center">
              <div className="text-xl font-bold text-text tabular-nums">
                {formatDuration(totals.avg_duration_ms)}
              </div>
              <div className="text-[10px] text-subtext uppercase tracking-wider font-medium mt-0.5">
                {t("metrics.avgDuration")}
              </div>
            </div>
            <div className="flex-1 p-3.5 text-center">
              <div className="text-xl font-bold text-text tabular-nums">
                {totals.total_turns}
              </div>
              <div className="text-[10px] text-subtext uppercase tracking-wider font-medium mt-0.5">
                {t("metrics.totalTurns")}
              </div>
              <div className="text-[9px] text-text2 mt-0.5">
                {t("metrics.inputTokens")}:{" "}
                {totals.total_input_tokens.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Period breakdown */}
          <div className="grid grid-cols-3 gap-3">
            {(["today", "this_week", "this_month"] as const).map((period) => {
              const p = metricsData.totals[period];
              const labelKey =
                period === "today"
                  ? "metrics.today"
                  : period === "this_week"
                  ? "metrics.week"
                  : "metrics.month";
              return (
                <div
                  key={period}
                  className={`bg-surface rounded-xl shadow-sm p-3.5 border-t-[3px] ${periodColors[period]}`}
                >
                  <span className="text-[10px] text-subtext uppercase tracking-wider font-semibold">
                    {t(labelKey)}
                  </span>
                  <div className="text-lg font-bold text-text mt-1 tabular-nums">
                    ${p.cost.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-text2 mt-0.5">
                    {p.sessions} {t("metrics.sessionsLabel")}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Rate limits */}
          {rateLimits && (
            <div className="bg-surface rounded-xl shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-[11px] text-text2 uppercase tracking-wider font-semibold">
                  {t("metrics.rateLimits")}
                </h4>
                {currentModel && (
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-primary/10 text-primary">
                    {currentModel}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 gap-3.5">
                <RateLimitGauge
                  label="Requests"
                  remaining={rateLimits["requests-remaining"]}
                  limit={rateLimits["requests-limit"]}
                  reset={rateLimits["requests-reset"]}
                />
                <RateLimitGauge
                  label={t("metrics.inputTokens")}
                  remaining={rateLimits["input-tokens-remaining"]}
                  limit={rateLimits["input-tokens-limit"]}
                  reset={rateLimits["input-tokens-reset"]}
                />
                <RateLimitGauge
                  label={t("metrics.outputTokens")}
                  remaining={rateLimits["output-tokens-remaining"]}
                  limit={rateLimits["output-tokens-limit"]}
                  reset={rateLimits["output-tokens-reset"]}
                />
              </div>
            </div>
          )}

          {/* Charts */}
          <div className="grid grid-cols-1 gap-4">
            <BarChart
              title={t("metrics.usageByHour")}
              data={metricsData.by_hour}
              labelKey="hour"
              valueKey="cost"
              formatValue={(v) => `$${v.toFixed(4)}`}
              subKey="sessions"
              formatSub={(v) => `${v} ${t("metrics.sessionsLabel")}`}
            />
            <BarChart
              title={t("metrics.usageByDow")}
              data={metricsData.by_dow}
              labelKey="name"
              valueKey="cost"
              formatValue={(v) => `$${v.toFixed(4)}`}
              subKey="sessions"
              formatSub={(v) => `${v} ${t("metrics.sessionsLabel")}`}
            />
          </div>

          <div className="grid grid-cols-1 gap-4">
            <BarChart
              title={t("metrics.dailySpend")}
              data={metricsData.by_day}
              labelKey="day"
              valueKey="cost"
              formatValue={(v) => `$${v.toFixed(2)}`}
              subKey="sessions"
              formatSub={(v) => `${v} ${t("metrics.sessionsLabel")}`}
            />
            <BarChart
              title={t("metrics.monthlySpend")}
              data={metricsData.by_month}
              labelKey="month"
              valueKey="cost"
              formatValue={(v) => `$${v.toFixed(2)}`}
              subKey="sessions"
              formatSub={(v) => `${v} ${t("metrics.sessionsLabel")}`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
