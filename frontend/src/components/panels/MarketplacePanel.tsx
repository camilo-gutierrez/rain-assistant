"use client";

import { useEffect, useState, useCallback } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { useTranslation } from "@/hooks/useTranslation";
import {
  searchMarketplaceSkills,
  getMarketplaceCategories,
  installMarketplaceSkill,
  uninstallMarketplaceSkill,
  getInstalledMarketplaceSkills,
  checkMarketplaceUpdates,
  updateMarketplaceSkill,
} from "@/lib/api";
import type {
  MarketplaceSkill,
  MarketplaceCategory,
  InstalledMarketplaceSkill,
  SkillUpdate,
} from "@/lib/types";
import {
  Store,
  Search,
  Download,
  Trash2,
  RefreshCw,
  CheckCircle,
  Shield,
  ArrowUpCircle,
  Package,
  Loader2,
} from "lucide-react";

type Tab = "browse" | "installed" | "updates";

const PERMISSION_DOTS: Record<string, string> = {
  green: "bg-green",
  yellow: "bg-yellow",
  red: "bg-red",
};

export default function MarketplacePanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);
  const language = useSettingsStore((s) => s.language);

  const [tab, setTab] = useState<Tab>("browse");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [skills, setSkills] = useState<MarketplaceSkill[]>([]);
  const [categories, setCategories] = useState<MarketplaceCategory[]>([]);
  const [installed, setInstalled] = useState<InstalledMarketplaceSkill[]>([]);
  const [updates, setUpdates] = useState<SkillUpdate[]>([]);
  const [loading, setLoading] = useState(false);
  const [installingName, setInstallingName] = useState<string | null>(null);

  const installedNames = new Set(installed.map((s) => s.name));

  const loadCategories = useCallback(async () => {
    if (!authToken) return;
    try {
      const data = await getMarketplaceCategories(authToken);
      setCategories(data.categories);
    } catch {
      // silent
    }
  }, [authToken]);

  const loadSkills = useCallback(
    async (q?: string, cat?: string) => {
      if (!authToken) return;
      setLoading(true);
      try {
        const data = await searchMarketplaceSkills(authToken, {
          q: q || undefined,
          category: cat || undefined,
        });
        setSkills(data.skills);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    },
    [authToken]
  );

  const loadInstalled = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await getInstalledMarketplaceSkills(authToken);
      setInstalled(data.skills);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  const loadUpdates = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await checkMarketplaceUpdates(authToken);
      setUpdates(data.updates);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    loadCategories();
    loadInstalled();
  }, [loadCategories, loadInstalled]);

  useEffect(() => {
    if (tab === "browse") loadSkills(query, category);
    else if (tab === "installed") loadInstalled();
    else if (tab === "updates") loadUpdates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  function handleSearch() {
    loadSkills(query, category);
  }

  function handleCategoryChange(cat: string) {
    setCategory(cat);
    loadSkills(query, cat);
  }

  async function handleInstall(name: string) {
    if (!authToken) return;
    setInstallingName(name);
    try {
      await installMarketplaceSkill(name, authToken);
      setInstalled((prev) => [
        ...prev,
        { name, version: "", source: "marketplace", installed_at: Date.now(), updated_at: Date.now() },
      ]);
    } catch {
      // silent
    } finally {
      setInstallingName(null);
    }
  }

  async function handleUninstall(name: string) {
    if (!authToken) return;
    setInstallingName(name);
    try {
      await uninstallMarketplaceSkill(name, authToken);
      setInstalled((prev) => prev.filter((s) => s.name !== name));
    } catch {
      // silent
    } finally {
      setInstallingName(null);
    }
  }

  async function handleUpdate(name: string) {
    if (!authToken) return;
    setInstallingName(name);
    try {
      await updateMarketplaceSkill(name, authToken);
      setUpdates((prev) => prev.filter((u) => u.name !== name));
    } catch {
      // silent
    } finally {
      setInstallingName(null);
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "browse", label: t("marketplace.browse") },
    { key: "installed", label: t("marketplace.installed") },
    { key: "updates", label: t("marketplace.updates") },
  ];

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Store size={20} className="text-primary" />
        <h2 className="text-base font-semibold text-text">
          {t("marketplace.title")}
        </h2>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface2/50 rounded-lg p-1">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={`flex-1 text-xs font-medium py-1.5 px-2 rounded-md transition-colors ${
              tab === tb.key
                ? "bg-primary text-on-primary"
                : "text-text2 hover:text-text hover:bg-surface2"
            }`}
          >
            {tb.label}
            {tb.key === "updates" && updates.length > 0 && (
              <span className="ml-1 text-[10px] bg-red/20 text-red px-1 rounded-full">
                {updates.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Browse tab */}
      {tab === "browse" && (
        <>
          {/* Search */}
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-subtext"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder={t("marketplace.search")}
                className="w-full text-sm pl-8 pr-3 py-2 rounded-lg bg-surface2 border border-overlay text-text placeholder:text-subtext focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleSearch}
              className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg bg-primary text-on-primary hover:bg-primary/80 transition-colors"
            >
              <Search size={16} />
            </button>
          </div>

          {/* Category pills */}
          {categories.length > 0 && (
            <div className="flex gap-1.5 flex-wrap">
              <button
                onClick={() => handleCategoryChange("")}
                className={`text-[11px] px-2 py-1 rounded-full transition-colors ${
                  !category
                    ? "bg-primary text-on-primary"
                    : "bg-surface2 text-text2 hover:bg-surface2/80"
                }`}
              >
                {t("marketplace.allCategories")}
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => handleCategoryChange(cat.id)}
                  className={`text-[11px] px-2 py-1 rounded-full transition-colors ${
                    category === cat.id
                      ? "bg-primary text-on-primary"
                      : "bg-surface2 text-text2 hover:bg-surface2/80"
                  }`}
                >
                  {cat.emoji} {language === "es" ? cat.name_es : cat.name}
                </button>
              ))}
            </div>
          )}

          {/* Skill cards */}
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 rounded-lg shimmer-bg" />
              ))}
            </div>
          ) : skills.length === 0 ? (
            <div className="text-center py-8">
              <Package size={32} className="mx-auto text-text2/40 mb-2" />
              <p className="text-sm text-text2">{t("marketplace.noResults")}</p>
              <p className="text-xs text-subtext mt-1">
                {t("marketplace.noResultsHint")}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {skills.map((skill) => (
                <SkillCard
                  key={skill.name}
                  skill={skill}
                  language={language}
                  isInstalled={installedNames.has(skill.name)}
                  isLoading={installingName === skill.name}
                  onInstall={() => handleInstall(skill.name)}
                  onUninstall={() => handleUninstall(skill.name)}
                  t={t}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Installed tab */}
      {tab === "installed" && (
        <>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 rounded-lg shimmer-bg" />
              ))}
            </div>
          ) : installed.length === 0 ? (
            <div className="text-center py-8">
              <Store size={32} className="mx-auto text-text2/40 mb-2" />
              <p className="text-sm text-text2">{t("marketplace.empty")}</p>
              <p className="text-xs text-subtext mt-1">
                {t("marketplace.emptyHint")}
              </p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {installed.map((skill) => (
                <div
                  key={skill.name}
                  className="group flex items-center gap-3 p-2.5 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors"
                >
                  <Package size={16} className="text-primary shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-text">
                      {skill.name}
                    </span>
                    {skill.version && (
                      <span className="text-[10px] text-text2 ml-1.5">
                        v{skill.version}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => handleUninstall(skill.name)}
                    disabled={installingName === skill.name}
                    className="opacity-0 group-hover:opacity-100 text-text2 hover:text-red transition-all shrink-0 disabled:opacity-40"
                    title={t("marketplace.uninstall")}
                  >
                    {installingName === skill.name ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Trash2 size={14} />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Updates tab */}
      {tab === "updates" && (
        <>
          {loading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-14 rounded-lg shimmer-bg" />
              ))}
            </div>
          ) : updates.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle size={32} className="mx-auto text-green/40 mb-2" />
              <p className="text-sm text-text2">All skills are up to date</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {updates.map((upd) => (
                <div
                  key={upd.name}
                  className="flex items-center gap-3 p-2.5 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors"
                >
                  <ArrowUpCircle size={16} className="text-blue-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-text">
                      {upd.name}
                    </span>
                    <span className="text-[10px] text-text2 ml-1.5">
                      {upd.current_version} → {upd.latest_version}
                    </span>
                  </div>
                  <button
                    onClick={() => handleUpdate(upd.name)}
                    disabled={installingName === upd.name}
                    className="text-xs px-2.5 py-1 rounded-lg bg-blue-500/15 text-blue-500 hover:bg-blue-500/25 transition-colors disabled:opacity-40"
                  >
                    {installingName === upd.name ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      t("marketplace.update")
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Refresh button */}
          <button
            onClick={loadUpdates}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 text-xs py-2 rounded-lg bg-surface2 text-text2 hover:bg-surface2/80 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Check for updates
          </button>
        </>
      )}
    </div>
  );
}

// --- SkillCard sub-component ---

interface SkillCardProps {
  skill: MarketplaceSkill;
  language: string;
  isInstalled: boolean;
  isLoading: boolean;
  onInstall: () => void;
  onUninstall: () => void;
  t: (key: string) => string;
}

function SkillCard({
  skill,
  language,
  isInstalled,
  isLoading,
  onInstall,
  onUninstall,
  t,
}: SkillCardProps) {
  const description =
    language === "es" && skill.description_es
      ? skill.description_es
      : skill.description;

  return (
    <div className="p-3 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors space-y-2">
      {/* Top row: name + badges + action */}
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-text">
              {skill.display_name || skill.name}
            </span>
            {/* Permission dot */}
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                PERMISSION_DOTS[skill.permission_level] || "bg-subtext"
              }`}
              title={`Permission: ${skill.permission_level}`}
            />
            {/* Verified badge */}
            {skill.verified && (
              <span title={t("marketplace.verified")}>
                <Shield size={12} className="text-blue-400 shrink-0" />
              </span>
            )}
          </div>
          <p className="text-xs text-text2 mt-0.5 line-clamp-2">{description}</p>
        </div>

        {/* Install/Uninstall button */}
        <div className="shrink-0">
          {isInstalled ? (
            <button
              onClick={onUninstall}
              disabled={isLoading}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-red/10 text-red hover:bg-red/20 transition-colors disabled:opacity-40"
            >
              {isLoading ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                t("marketplace.uninstall")
              )}
            </button>
          ) : (
            <button
              onClick={onInstall}
              disabled={isLoading}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-green/10 text-green hover:bg-green/20 transition-colors disabled:opacity-40"
            >
              {isLoading ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <span className="flex items-center gap-1">
                  <Download size={11} />
                  {t("marketplace.install")}
                </span>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Bottom row: tags + meta */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {skill.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary"
          >
            {tag}
          </span>
        ))}
        <span className="text-[10px] text-subtext ml-auto">
          v{skill.version} · {skill.author}
        </span>
      </div>

      {/* Env requirements */}
      {skill.requires_env.length > 0 && (
        <p className="text-[10px] text-yellow flex items-center gap-1">
          <Shield size={10} />
          {t("marketplace.requiresEnv")}: {skill.requires_env.join(", ")}
        </p>
      )}
    </div>
  );
}
