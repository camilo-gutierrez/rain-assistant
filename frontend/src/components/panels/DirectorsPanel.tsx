"use client";

import { useEffect, useState, useCallback } from "react";
import React from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import {
  fetchDirectors,
  deleteDirector,
  runDirector,
  fetchDirectorTemplates,
  createDirector,
  updateDirector,
  fetchDirectorTasks,
  fetchDirectorActivity,
} from "@/lib/api";
import type {
  Director,
  DirectorTemplate,
  DirectorTask,
  ActivityItem,
} from "@/lib/types";
import {
  Bot,
  Play,
  Trash2,
  Clock,
  Power,
  Loader2,
  ChevronDown,
  ChevronUp,
  ListTodo,
  Zap,
  Download,
} from "lucide-react";
import EmptyState from "@/components/EmptyState";
import { SkeletonList } from "@/components/Skeleton";

type Tab = "directors" | "templates" | "tasks" | "activity";

export default function DirectorsPanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);

  const [tab, setTab] = useState<Tab>("directors");
  const [directors, setDirectors] = useState<Director[]>([]);
  const [templates, setTemplates] = useState<DirectorTemplate[]>([]);
  const [tasks, setTasks] = useState<DirectorTask[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [installingId, setInstallingId] = useState<string | null>(null);

  const loadDirectors = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchDirectors(authToken);
      setDirectors(data.directors);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  const loadTemplates = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchDirectorTemplates(authToken);
      setTemplates(data.templates);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  const loadTasks = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchDirectorTasks(authToken);
      setTasks(data.tasks);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  const loadActivity = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchDirectorActivity(authToken);
      setActivity(data.activity);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    loadDirectors();
  }, [loadDirectors]);

  useEffect(() => {
    if (tab === "directors") loadDirectors();
    else if (tab === "templates") loadTemplates();
    else if (tab === "tasks") loadTasks();
    else if (tab === "activity") loadActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function handleRun(id: string) {
    if (!authToken) return;
    setRunningId(id);
    try {
      await runDirector(id, authToken);
    } catch {
      // silent
    } finally {
      setRunningId(null);
    }
  }

  async function handleDelete(id: string) {
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id);
      return;
    }
    if (!authToken) return;
    setDeletingId(id);
    try {
      await deleteDirector(id, authToken);
      setDirectors((prev) => prev.filter((d) => d.id !== id));
    } catch {
      // silent
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  }

  async function handleToggleEnabled(director: Director) {
    if (!authToken) return;
    try {
      const data = await updateDirector(director.id, { enabled: !director.enabled } as Partial<Director>, authToken);
      setDirectors((prev) => prev.map((d) => d.id === director.id ? data.director : d));
    } catch {
      // silent
    }
  }

  async function handleInstallTemplate(tmpl: DirectorTemplate) {
    if (!authToken) return;
    setInstallingId(tmpl.id);
    try {
      const data = await createDirector({
        id: tmpl.id,
        name: tmpl.name,
        emoji: tmpl.emoji,
        description: tmpl.description,
        role_prompt: tmpl.role_prompt,
        schedule: tmpl.schedule,
        tools_allowed: tmpl.tools_allowed,
        plugins_allowed: tmpl.plugins_allowed,
        permission_level: tmpl.permission_level as "green" | "yellow",
        can_delegate: tmpl.can_delegate,
      }, authToken);
      setDirectors((prev) => [...prev, data.director]);
      setTab("directors");
    } catch {
      // silent
    } finally {
      setInstallingId(null);
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "directors", label: t("directors.title") },
    { key: "templates", label: t("directors.templates") },
    { key: "tasks", label: t("directors.taskQueue") },
    { key: "activity", label: t("directors.activity") },
  ];

  const directorIds = new Set(directors.map((d) => d.id));

  return (
    <div className="p-4 space-y-4">
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
          </button>
        ))}
      </div>

      {/* Directors tab */}
      {tab === "directors" && (
        <>
          {loading ? (
            <SkeletonList count={3} height="h-24" />
          ) : directors.length === 0 ? (
            <EmptyState
              icon={Bot}
              title={t("directors.empty")}
              hint={t("directors.emptyHint")}
            />
          ) : (
            <div className="space-y-2">
              {directors.map((d) => (
                <DirectorCard
                  key={d.id}
                  director={d}
                  isRunning={runningId === d.id}
                  isDeleting={deletingId === d.id}
                  isConfirmDelete={confirmDeleteId === d.id}
                  onRun={() => handleRun(d.id)}
                  onDelete={() => handleDelete(d.id)}
                  onToggle={() => handleToggleEnabled(d)}
                  t={t}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Templates tab */}
      {tab === "templates" && (
        <>
          {loading ? (
            <SkeletonList count={3} height="h-20" />
          ) : templates.length === 0 ? (
            <EmptyState icon={Bot} title={t("directors.noTemplates")} />
          ) : (
            <div className="space-y-2">
              {templates.map((tmpl) => (
                <div
                  key={tmpl.id}
                  className="p-3 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors space-y-2"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-lg">{tmpl.emoji}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-text">{tmpl.name}</div>
                      <p className="text-xs text-text2 mt-0.5 line-clamp-2">{tmpl.description}</p>
                    </div>
                    <button
                      onClick={() => handleInstallTemplate(tmpl)}
                      disabled={installingId === tmpl.id || directorIds.has(tmpl.id)}
                      className="shrink-0 text-xs px-2.5 py-1 rounded-lg bg-green/10 text-green hover:bg-green/20 transition-colors disabled:opacity-40"
                    >
                      {installingId === tmpl.id ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : directorIds.has(tmpl.id) ? (
                        t("directors.enabled")
                      ) : (
                        <span className="flex items-center gap-1">
                          <Download size={11} />
                          {t("directors.install")}
                        </span>
                      )}
                    </button>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {tmpl.schedule && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue/10 text-blue flex items-center gap-1">
                        <Clock size={10} />
                        {tmpl.schedule}
                      </span>
                    )}
                    {tmpl.can_delegate && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-mauve/10 text-mauve">
                        {t("directors.canDelegate")}
                      </span>
                    )}
                    <span className={`w-2 h-2 rounded-full ${tmpl.permission_level === "yellow" ? "bg-yellow" : "bg-green"}`} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Tasks tab */}
      {tab === "tasks" && (
        <>
          {loading ? (
            <SkeletonList count={3} height="h-14" />
          ) : tasks.length === 0 ? (
            <EmptyState icon={ListTodo} title={t("directors.noTasks")} />
          ) : (
            <div className="space-y-1.5">
              {tasks.map((task) => (
                <TaskRow key={task.id} task={task} t={t} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Activity tab */}
      {tab === "activity" && (
        <>
          {loading ? (
            <SkeletonList count={4} height="h-12" />
          ) : activity.length === 0 ? (
            <EmptyState icon={Zap} title={t("directors.noActivity")} />
          ) : (
            <div className="space-y-1">
              {activity.map((item, i) => (
                <ActivityRow key={`${item.type}-${item.timestamp}-${i}`} item={item} t={t} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// --- DirectorCard sub-component ---

interface DirectorCardProps {
  director: Director;
  isRunning: boolean;
  isDeleting: boolean;
  isConfirmDelete: boolean;
  onRun: () => void;
  onDelete: () => void;
  onToggle: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const DirectorCard = React.memo(function DirectorCard({
  director: d,
  isRunning,
  isDeleting,
  isConfirmDelete,
  onRun,
  onDelete,
  onToggle,
  t,
}: DirectorCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors overflow-hidden">
      {/* Main row */}
      <div className="flex items-center gap-3 p-3">
        <span className="text-lg shrink-0">{d.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-text">{d.name}</span>
            <span className={`w-2 h-2 rounded-full shrink-0 ${d.enabled ? "bg-green" : "bg-subtext"}`} />
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {d.schedule ? (
              <span className="text-xs text-text2 flex items-center gap-1">
                <Clock size={10} />
                {d.schedule}
              </span>
            ) : (
              <span className="text-xs text-subtext">{t("directors.manual")}</span>
            )}
            {d.run_count > 0 && (
              <span className="text-xs text-subtext">
                {t("directors.runs", { count: d.run_count })}
              </span>
            )}
            {d.total_cost > 0 && (
              <span className="text-xs text-subtext">
                ${d.total_cost.toFixed(4)}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {/* Run button */}
          <button
            onClick={onRun}
            disabled={isRunning}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
            title={t("directors.runNow")}
          >
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          </button>
          {/* Toggle enabled */}
          <button
            onClick={onToggle}
            className={`min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg transition-colors ${
              d.enabled ? "text-green hover:bg-green/10" : "text-subtext hover:bg-surface2"
            }`}
            title={d.enabled ? t("directors.enabled") : t("directors.disabled")}
          >
            <Power size={14} />
          </button>
          {/* Expand */}
          <button
            onClick={() => setExpanded(!expanded)}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg text-text2 hover:bg-surface2 transition-colors"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-overlay/50 pt-2">
          {d.description && (
            <p className="text-xs text-text2">{d.description}</p>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            {d.can_delegate && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-mauve/10 text-mauve">
                {t("directors.canDelegate")}
              </span>
            )}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              d.permission_level === "yellow" ? "bg-yellow/10 text-yellow" : "bg-green/10 text-green"
            }`}>
              {d.permission_level}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="text-subtext">
              {t("directors.lastRun")}:{" "}
              <span className="text-text2">
                {d.last_run ? new Date(d.last_run * 1000).toLocaleString() : t("directors.never")}
              </span>
            </div>
            <div className="text-subtext">
              {t("directors.nextRun")}:{" "}
              <span className="text-text2">
                {d.next_run ? new Date(d.next_run * 1000).toLocaleString() : "—"}
              </span>
            </div>
          </div>
          {d.last_error && (
            <p className="text-xs text-red bg-red/5 px-2 py-1 rounded">{d.last_error}</p>
          )}
          {/* Delete */}
          <div className="flex justify-end">
            <button
              onClick={onDelete}
              disabled={isDeleting}
              className="text-xs px-2.5 py-1 rounded-lg text-red hover:bg-red/10 transition-colors disabled:opacity-40"
            >
              {isDeleting ? (
                <Loader2 size={12} className="animate-spin" />
              ) : isConfirmDelete ? (
                t("directors.deleteConfirm", { name: d.name })
              ) : (
                <span className="flex items-center gap-1">
                  <Trash2 size={11} />
                  {t("directors.delete")}
                </span>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

// --- TaskRow sub-component ---

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: "bg-subtext",
  claimed: "bg-blue",
  running: "bg-primary animate-pulse",
  completed: "bg-green",
  failed: "bg-red",
  cancelled: "bg-subtext",
};

interface TaskRowProps {
  task: DirectorTask;
  t: (key: string) => string;
}

const TaskRow = React.memo(function TaskRow({ task }: TaskRowProps) {
  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors">
      <div className={`w-2 h-2 rounded-full shrink-0 ${TASK_STATUS_COLORS[task.status] || "bg-subtext"}`} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-text truncate">{task.title}</div>
        <div className="text-xs text-subtext">
          {task.creator_id} → {task.assignee_id || "?"}
          {task.priority <= 3 && " !!"}
        </div>
      </div>
      <span className="text-xs text-text2 shrink-0">{task.status}</span>
    </div>
  );
});

// --- ActivityRow sub-component ---

interface ActivityRowProps {
  item: ActivityItem;
  t: (key: string) => string;
}

const ActivityRow = React.memo(function ActivityRow({ item }: ActivityRowProps) {
  const timeStr = new Date(item.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-surface2/50 transition-colors">
      <span className="text-sm shrink-0">{item.emoji || (item.type === "task" ? "\u{1F4CB}" : "\u{1F916}")}</span>
      <div className="flex-1 min-w-0">
        <span className="text-xs text-text truncate block">
          {item.type === "director_run" && (
            <>{item.director_name}: {item.success ? (item.preview?.slice(0, 60) || "OK") : "Error"}</>
          )}
          {item.type === "inbox_item" && (
            <>{item.director_name}: {item.title}</>
          )}
          {item.type === "task" && (
            <>{item.creator_id} → {item.assignee_id}: {item.title}</>
          )}
        </span>
      </div>
      <span className="text-xs text-subtext shrink-0">{timeStr}</span>
    </div>
  );
});
