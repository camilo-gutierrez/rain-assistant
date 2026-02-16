import { create } from "zustand";
import type { RateLimits, MetricsData } from "@/lib/types";
import { fetchMetrics as apiFetchMetrics } from "@/lib/api";

const CACHE_TTL = 60_000; // 1 minute

interface MetricsState {
  currentModel: string | null;
  rateLimits: RateLimits | null;
  lastUsage: { input_tokens: number; output_tokens: number } | null;
  metricsData: MetricsData | null;
  lastFetch: number;

  updateModelInfo: (model: string) => void;
  updateRateLimits: (limits: RateLimits) => void;
  updateUsageInfo: (usage: { input_tokens: number; output_tokens: number }) => void;
  fetchMetrics: (authToken: string | null, forceRefresh?: boolean) => Promise<void>;
}

export const useMetricsStore = create<MetricsState>()((set, get) => ({
  currentModel: null,
  rateLimits: null,
  lastUsage: null,
  metricsData: null,
  lastFetch: 0,

  updateModelInfo: (model) => set({ currentModel: model }),
  updateRateLimits: (limits) => set({ rateLimits: limits }),
  updateUsageInfo: (usage) => set({ lastUsage: usage }),

  fetchMetrics: async (authToken, forceRefresh = false) => {
    const { lastFetch } = get();
    if (!forceRefresh && Date.now() - lastFetch < CACHE_TTL) return;

    try {
      const data = await apiFetchMetrics(authToken);
      set({ metricsData: data, lastFetch: Date.now() });
    } catch (err) {
      console.error("Failed to fetch metrics:", err);
    }
  },
}));
