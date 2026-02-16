"use client";

import { useEffect, useState } from "react";
import { useMetricsStore } from "@/stores/useMetricsStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { MetricsData, MetricsTotals, RateLimits } from "@/lib/types";

// --- Sub-components (kept inline) ---

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-surface rounded-xl border border-overlay p-4 flex flex-col gap-1">
      <span className="text-xs text-subtext font-[family-name:var(--font-orbitron)] uppercase tracking-wider">
        {label}
      </span>
      <span className="text-xl font-bold text-text font-[family-name:var(--font-jetbrains)]">
        {value}
      </span>
      {sub && (
        <span className="text-[10px] text-text2 font-[family-name:var(--font-jetbrains)]">
          {sub}
        </span>
      )}
    </div>
  );
}

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
    <div className="bg-surface rounded-xl border border-overlay p-4">
      <h4 className="text-xs text-text2 font-[family-name:var(--font-orbitron)] uppercase tracking-wider mb-3">
        {title}
      </h4>
      <div className="flex items-end gap-1 h-[100px] chart-container-responsive">
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
              className="flex-1 flex flex-col items-center justify-end gap-1 min-w-0"
              title={`${label}: ${formatted}${subFormatted ? ` (${subFormatted})` : ""}`}
            >
              <div
                className="w-full max-w-[24px] rounded-t transition-all"
                style={{
                  height: `${Math.max(pct, 2)}%`,
                  background: "linear-gradient(180deg, var(--cyan), var(--mauve))",
                }}
              />
              <span className="text-[8px] text-subtext font-[family-name:var(--font-jetbrains)] truncate w-full text-center">
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
  const fillColor = pct > 50 ? "var(--green)" : pct > 20 ? "var(--yellow)" : "var(--red)";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-baseline">
        <span className="text-[10px] text-text2 font-[family-name:var(--font-jetbrains)]">
          {label}
        </span>
        <span className="text-[10px] text-subtext font-[family-name:var(--font-jetbrains)]">
          {remaining?.toLocaleString()} / {limit?.toLocaleString()}
        </span>
      </div>
      <div className="h-2 rounded-full bg-surface2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: fillColor }}
        />
      </div>
      {reset && (
        <span className="text-[9px] text-subtext font-[family-name:var(--font-jetbrains)]">
          Reset: {reset}
        </span>
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
  const toggleMetrics = useUIStore((s) => s.toggleMetrics);
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

  return (
    <div className="flex-1 flex flex-col overflow-y-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2
          className="font-[family-name:var(--font-orbitron)] text-lg font-bold bg-clip-text text-transparent"
          style={{
            backgroundImage: "linear-gradient(135deg, var(--cyan), var(--magenta))",
          }}
        >
          {t("metrics.title")}
        </h2>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="px-3 py-1 text-xs rounded border border-overlay text-text2 hover:text-cyan hover:border-cyan transition-colors font-[family-name:var(--font-jetbrains)] disabled:opacity-50"
          >
            {t("metrics.refresh")}
          </button>
          <button
            onClick={toggleMetrics}
            className="px-3 py-1 text-xs rounded border border-overlay text-text2 hover:text-cyan hover:border-cyan transition-colors font-[family-name:var(--font-jetbrains)]"
          >
            {t("metrics.close")}
          </button>
        </div>
      </div>

      {loading && !metricsData ? (
        <div className="flex-1 flex items-center justify-center text-text2 text-sm">
          {t("metrics.loading")}
        </div>
      ) : !metricsData || !totals ? (
        <div className="flex-1 flex items-center justify-center text-text2 text-sm">
          {t("metrics.noData")}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 metrics-cards-responsive">
            <MetricCard
              label={t("metrics.totalSpent")}
              value={`$${totals.cost.toFixed(2)}`}
              sub={`${t("metrics.avgCost")}: $${totals.avg_cost.toFixed(4)}`}
            />
            <MetricCard
              label={t("metrics.sessions")}
              value={String(totals.sessions)}
            />
            <MetricCard
              label={t("metrics.avgDuration")}
              value={formatDuration(totals.avg_duration_ms)}
            />
            <MetricCard
              label={t("metrics.totalTurns")}
              value={String(totals.total_turns)}
              sub={`${t("metrics.inputTokens")}: ${totals.total_input_tokens.toLocaleString()}`}
            />
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
                  className="bg-surface rounded-xl border border-overlay p-3"
                >
                  <span className="text-[10px] text-subtext font-[family-name:var(--font-orbitron)] uppercase tracking-wider">
                    {t(labelKey)}
                  </span>
                  <div className="text-lg font-bold text-text font-[family-name:var(--font-jetbrains)]">
                    ${p.cost.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-text2 font-[family-name:var(--font-jetbrains)]">
                    {p.sessions} {t("metrics.sessionsLabel")}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Rate limits */}
          {rateLimits && (
            <div className="bg-surface rounded-xl border border-overlay p-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs text-text2 font-[family-name:var(--font-orbitron)] uppercase tracking-wider">
                  {t("metrics.rateLimits")}
                </h4>
                {currentModel && (
                  <span
                    className="px-2 py-0.5 rounded text-[10px] font-bold text-white"
                    style={{
                      background: "linear-gradient(135deg, var(--cyan), var(--mauve))",
                    }}
                  >
                    {currentModel}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 rl-dashboard-responsive">
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
