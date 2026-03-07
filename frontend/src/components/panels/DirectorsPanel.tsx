"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import React from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import { useDirectorRunStore } from "@/stores/useDirectorRunStore";
import type { ActiveTeamRun, DirectorRunStatus } from "@/stores/useDirectorRunStore";
import {
  fetchDirectors,
  deleteDirector,
  runDirector,
  runProject,
  stopProject,
  fetchTeamTemplates,
  createProject,
  updateDirector,
  fetchDirectorTasks,
  fetchDirectorActivity,
  fetchProjects,
} from "@/lib/api";
import type {
  Director,
  DirectorTask,
  ActivityItem,
  DirectorProject,
  TeamTemplate,
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
  FolderOpen,
  Users,
  CheckCircle,
  X,
  Settings,
  AlertTriangle,
  ArrowLeft,
  FileText,
  Mail,
  Code,
  Bell,
  BarChart3,
  Shield,
  Square,
} from "lucide-react";
import type { InboxItem } from "@/lib/types";
import { fetchInbox } from "@/lib/api";
import EmptyState from "@/components/EmptyState";
import { SkeletonList } from "@/components/Skeleton";
import DirectorContextEditor from "@/components/panels/DirectorContextEditor";

type Tab = "directors" | "templates" | "tasks" | "activity";

export default function DirectorsPanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);

  const [tab, setTab] = useState<Tab>("directors");
  const [directors, setDirectors] = useState<Director[]>([]);
  const [tasks, setTasks] = useState<DirectorTask[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [teamTemplates, setTeamTemplates] = useState<TeamTemplate[]>([]);
  const [creatingProjectId, setCreatingProjectId] = useState<string | null>(null);
  const [expandedTeamId, setExpandedTeamId] = useState<string | null>(null);
  const [editingContextFor, setEditingContextFor] = useState<Director | null>(null);
  const [selectedDirector, setSelectedDirector] = useState<Director | null>(null);

  // Team run state from store
  const activeRun = useDirectorRunStore((s) => s.activeRun);
  const clearRun = useDirectorRunStore((s) => s.clearRun);
  const teamRunning = activeRun !== null;

  // Project state
  const [projects, setProjects] = useState<DirectorProject[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string>("");

  const loadProjects = useCallback(async () => {
    if (!authToken) return;
    try {
      const data = await fetchProjects(authToken);
      setProjects(data.projects);
    } catch {
      // silent
    }
  }, [authToken]);

  const loadDirectors = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchDirectors(authToken, activeProjectId || undefined);
      setDirectors(data.directors);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken, activeProjectId]);

  const loadTemplates = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const teamData = await fetchTeamTemplates(authToken);
      setTeamTemplates(teamData.team_templates.filter((t) => t.directors.length > 0));
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
      const data = await fetchDirectorTasks(authToken, { project_id: activeProjectId || undefined });
      setTasks(data.tasks);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken, activeProjectId]);

  const loadActivity = useCallback(async () => {
    if (!authToken) return;
    setLoading(true);
    try {
      const data = await fetchDirectorActivity(authToken, 20, activeProjectId || undefined);
      setActivity(data.activity);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [authToken, activeProjectId]);

  useEffect(() => {
    loadProjects();
    loadDirectors();
  }, [loadProjects, loadDirectors]);

  useEffect(() => {
    if (tab === "directors") loadDirectors();
    else if (tab === "templates") loadTemplates();
    else if (tab === "tasks") loadTasks();
    else if (tab === "activity") loadActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, activeProjectId]);

  // Auto-refresh data when a team run finishes (activeRun -> null)
  const prevRunRef = useRef(activeRun);
  useEffect(() => {
    if (prevRunRef.current && !activeRun) {
      loadDirectors();
      if (tab === "tasks") loadTasks();
      if (tab === "activity") loadActivity();
    }
    prevRunRef.current = activeRun;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRun]);

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

  async function handleCreateProject(team: TeamTemplate) {
    if (!authToken) return;
    setCreatingProjectId(team.id);
    try {
      const data = await createProject({
        name: team.name,
        emoji: team.emoji,
        description: team.description,
        color: team.color,
        team_template: team.id,
      }, authToken);
      setProjects((prev) => [...prev, data.project]);
      setDirectors((prev) => [...prev, ...data.installed_directors]);
      setActiveProjectId(data.project.id);
      setTab("directors");
    } catch {
      // silent
    } finally {
      setCreatingProjectId(null);
    }
  }

  async function handleRunTeam() {
    if (!authToken || !activeProjectId || teamRunning) return;
    try {
      const data = await runProject(activeProjectId, authToken);
      const store = useDirectorRunStore.getState();
      if (!store.activeRun) {
        store.startRun(
          activeProjectId,
          activeProject?.name || "",
          data.directors.length,
          data.directors,
        );
      }
    } catch {
      // silent
    }
  }

  async function handleStopTeam() {
    if (!authToken || !activeProjectId) return;
    try {
      await stopProject(activeProjectId, authToken);
    } catch {
      // silent
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "directors", label: t("directors.title") },
    { key: "templates", label: t("directors.templates") },
    { key: "tasks", label: t("directors.taskQueue") },
    { key: "activity", label: t("directors.activity") },
  ];

  const activeProject = projects.find((p) => p.id === activeProjectId);

  // If a director is selected, show detail view
  if (selectedDirector) {
    const freshDirector = directors.find((d) => d.id === selectedDirector.id) || selectedDirector;
    return (
      <div className="p-4 space-y-4">
        <DirectorDetailView
          director={freshDirector}
          authToken={authToken}
          onBack={() => setSelectedDirector(null)}
          onRun={() => handleRun(freshDirector.id)}
          onConfigure={() => setEditingContextFor(freshDirector)}
          onDelete={() => handleDelete(freshDirector.id)}
          isRunning={runningId === freshDirector.id}
          isConfirmDelete={confirmDeleteId === freshDirector.id}
          t={t}
        />
        {editingContextFor && (
          <DirectorContextEditor
            director={editingContextFor}
            onClose={() => setEditingContextFor(null)}
            onSaved={() => {
              setEditingContextFor(null);
              loadDirectors();
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Project Switcher */}
      {projects.length > 0 && (
        <div className="flex items-center gap-2">
          <FolderOpen size={14} className="text-text2 shrink-0" />
          <select
            value={activeProjectId}
            onChange={(e) => setActiveProjectId(e.target.value)}
            className="flex-1 text-xs bg-surface2/50 border border-border rounded-md px-2 py-1.5 text-text focus-ring"
          >
            <option value="">{t("projects.allDirectors")}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.emoji} {p.name}
              </option>
            ))}
          </select>
          {activeProject && (
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: activeProject.color }}
              title={activeProject.name}
            />
          )}
        </div>
      )}

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
          {/* Run Team button + progress */}
          {activeProjectId && directors.length > 0 && (
            <>
              {!teamRunning && (
                <button
                  onClick={handleRunTeam}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-sm font-medium"
                >
                  <Play size={14} />
                  {t("directors.runTeam")}
                </button>
              )}
              {activeRun && (
                <TeamRunProgress run={activeRun} onDismiss={clearRun} onStop={handleStopTeam} t={t} />
              )}
            </>
          )}
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
                  onConfigure={() => setEditingContextFor(d)}
                  onSelect={() => setSelectedDirector(d)}
                  t={t}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Templates tab — team templates only */}
      {tab === "templates" && (
        <>
          {loading ? (
            <SkeletonList count={3} height="h-20" />
          ) : teamTemplates.length === 0 ? (
            <EmptyState icon={Users} title={t("directors.noTemplates")} />
          ) : (
            <div className="space-y-2">
              {teamTemplates.map((team) => (
                <div
                  key={team.id}
                  className="rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors overflow-hidden"
                >
                  <div className="flex items-start gap-2 p-3">
                    <span className="text-lg">{team.emoji}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text">{team.name}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-mauve/10 text-mauve flex items-center gap-1">
                          <Users size={10} />
                          {t("directors.teamDirectors", { count: team.directors.length })}
                        </span>
                      </div>
                      <p className="text-xs text-text2 mt-0.5 line-clamp-2">{team.description}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleCreateProject(team)}
                        disabled={creatingProjectId === team.id}
                        className="text-xs px-2.5 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-40"
                      >
                        {creatingProjectId === team.id ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <span className="flex items-center gap-1">
                            <FolderOpen size={11} />
                            {t("directors.createProject")}
                          </span>
                        )}
                      </button>
                      <button
                        onClick={() => setExpandedTeamId(expandedTeamId === team.id ? null : team.id)}
                        className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded-lg text-text2 hover:bg-surface2 transition-colors"
                      >
                        {expandedTeamId === team.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    </div>
                  </div>
                  {/* Expanded: show team directors */}
                  {expandedTeamId === team.id && team.director_details && (
                    <div className="px-3 pb-3 space-y-1.5 border-t border-overlay/50 pt-2">
                      {team.director_details.map((dir) => (
                        <div key={dir.id} className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-bg/50">
                          <span className="text-sm">{dir.emoji}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-text">{dir.name}</div>
                            <p className="text-xs text-subtext truncate">{dir.description}</p>
                          </div>
                          {dir.schedule && (
                            <span className="text-xs text-text2 flex items-center gap-1 shrink-0">
                              <Clock size={9} />
                              {dir.schedule}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
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

      {/* Context Editor Modal */}
      {editingContextFor && (
        <DirectorContextEditor
          director={editingContextFor}
          onClose={() => setEditingContextFor(null)}
          onSaved={() => {
            setEditingContextFor(null);
            loadDirectors();
          }}
        />
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
  onConfigure: () => void;
  onSelect: () => void;
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
  onConfigure,
  onSelect,
  t,
}: DirectorCardProps) {
  const [expanded, setExpanded] = useState(false);
  const needsSetup = d.setup_status === "needs_setup";
  const hasContext = (d.required_context ?? []).length > 0;

  return (
    <div className="rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors overflow-hidden">
      {/* Main row */}
      <div className="flex items-center gap-3 p-3">
        <button
          type="button"
          onClick={onSelect}
          className="flex items-center gap-3 flex-1 min-w-0 text-left bg-transparent border-0 p-0 cursor-pointer"
        >
          <span className="text-lg shrink-0">{d.emoji}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-sm font-medium text-text">{d.name}</span>
              <span className={`w-2 h-2 rounded-full shrink-0 ${d.enabled ? "bg-green" : "bg-subtext"}`} />
              {needsSetup && (
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-yellow/10 text-yellow flex items-center gap-1">
                  <AlertTriangle size={10} />
                  {t("directors.needsSetup")}
                </span>
              )}
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
        </button>
        <div className="flex items-center gap-1 shrink-0">
          {hasContext && (
            <button
              onClick={onConfigure}
              className={`min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg transition-colors ${
                needsSetup
                  ? "text-yellow hover:bg-yellow/10"
                  : "text-text2 hover:bg-surface2"
              }`}
              title={t("directors.configure")}
            >
              <Settings size={14} />
            </button>
          )}
          <button
            onClick={onRun}
            disabled={isRunning}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
            title={t("directors.runNow")}
          >
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          </button>
          <button
            onClick={onToggle}
            className={`min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg transition-colors ${
              d.enabled ? "text-green hover:bg-green/10" : "text-subtext hover:bg-surface2"
            }`}
            title={d.enabled ? t("directors.enabled") : t("directors.disabled")}
          >
            <Power size={14} />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg text-text2 hover:bg-surface2 transition-colors"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Needs setup banner */}
      {needsSetup && !expanded && (
        <div className="mx-3 mb-2 px-2.5 py-1.5 rounded-md bg-yellow/5 border border-yellow/20">
          <p className="text-xs text-yellow">
            {t("directors.needsSetupHint").replace(
              "{fields}",
              (d.missing_fields ?? []).join(", ")
            )}
          </p>
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-overlay/50 pt-2">
          {d.description && (
            <p className="text-xs text-text2">{d.description}</p>
          )}

          {needsSetup && (
            <div className="flex items-start gap-2 px-2.5 py-2 rounded-md bg-yellow/5 border border-yellow/20">
              <AlertTriangle size={12} className="text-yellow shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-yellow">
                  {t("directors.needsSetupHint").replace(
                    "{fields}",
                    (d.missing_fields ?? []).join(", ")
                  )}
                </p>
                <button
                  onClick={onConfigure}
                  className="text-xs mt-1 px-2 py-0.5 rounded bg-yellow/10 text-yellow hover:bg-yellow/20 transition-colors"
                >
                  {t("directors.configure")}
                </button>
              </div>
            </div>
          )}

          {hasContext && !needsSetup && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-green flex items-center gap-1">
                <CheckCircle size={10} />
                {t("directors.contextConfigured")}
              </span>
              <button
                onClick={onConfigure}
                className="text-xs text-text2 hover:text-text transition-colors underline"
              >
                {t("directors.configure")}
              </button>
            </div>
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
                {d.next_run ? new Date(d.next_run * 1000).toLocaleString() : "\u2014"}
              </span>
            </div>
          </div>
          {d.last_error && (
            <p className="text-xs text-red bg-red/5 px-2 py-1 rounded">{d.last_error}</p>
          )}
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
          {task.creator_id} &rarr; {task.assignee_id || "?"}
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
            <>{item.creator_id} &rarr; {item.assignee_id}: {item.title}</>
          )}
        </span>
      </div>
      <span className="text-xs text-subtext shrink-0">{timeStr}</span>
    </div>
  );
});

// --- TeamRunProgress sub-component ---

const DIRECTOR_RUN_STATUS_COLORS: Record<DirectorRunStatus, string> = {
  pending: "bg-subtext",
  running: "bg-primary animate-pulse",
  completed: "bg-green",
  failed: "bg-red",
};

interface TeamRunProgressProps {
  run: ActiveTeamRun;
  onDismiss: () => void;
  onStop: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const TeamRunProgress = React.memo(function TeamRunProgress({
  run,
  onDismiss,
  onStop,
  t,
}: TeamRunProgressProps) {
  const directorEntries = Object.values(run.directors);
  const completedCount = directorEntries.filter(
    (d) => d.status === "completed" || d.status === "failed",
  ).length;
  const total = Math.max(run.directorCount, directorEntries.length);
  const allDone = completedCount >= total && total > 0;
  const isRunning = !allDone;
  const pct = total > 0 ? (completedCount / total) * 100 : 0;

  return (
    <div className="rounded-lg bg-primary/5 border border-primary/20 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          {allDone ? (
            <CheckCircle size={14} className="text-green shrink-0" />
          ) : (
            <Loader2 size={14} className="animate-spin text-primary shrink-0" />
          )}
          <span className="text-sm font-medium text-text truncate">
            {allDone
              ? t("directors.teamRunFinished", {
                  name: run.projectName,
                  success: directorEntries.filter((d) => d.status === "completed").length,
                  failed: directorEntries.filter((d) => d.status === "failed").length,
                })
              : t("directors.teamRunning")}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {isRunning && (
            <button
              onClick={onStop}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg text-red hover:bg-red/10 transition-colors"
              title={t("directors.stopTeam")}
            >
              <Square size={10} />
              {t("directors.stopTeam")}
            </button>
          )}
          {allDone && (
            <button
              onClick={onDismiss}
              className="text-text2 hover:text-text transition-colors p-0.5 rounded shrink-0"
              title={t("directors.dismissProgress")}
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="px-3 pb-1">
        <div className="h-1.5 bg-surface2 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-text2">
            {t("directors.teamProgress", { completed: completedCount, total })}
          </span>
          {run.completedTasks > 0 && (
            <span className="text-xs text-text2">
              {t("directors.teamProgressTasks", { count: run.completedTasks })}
            </span>
          )}
        </div>
      </div>

      {/* Director list */}
      {directorEntries.length > 0 && (
        <div className="px-3 pb-2.5 space-y-1">
          {directorEntries.map((d) => (
            <div
              key={d.id}
              className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-bg/50"
            >
              <div
                className={`w-2 h-2 rounded-full shrink-0 ${DIRECTOR_RUN_STATUS_COLORS[d.status]}`}
              />
              <span className="text-xs text-text flex-1 truncate">{d.name}</span>
              <span className="text-xs text-subtext shrink-0">
                {d.status === "running"
                  ? t("directors.runningDirector")
                  : d.status === "completed"
                    ? t("directors.completedDirector")
                    : d.status === "failed"
                      ? t("directors.failedDirector")
                      : t("directors.pendingDirector")}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

// --- DirectorDetailView sub-component ---

const INBOX_TYPE_ICONS: Record<string, typeof FileText> = {
  report: BarChart3,
  draft: FileText,
  analysis: BarChart3,
  code: Code,
  notification: Bell,
};

const INBOX_STATUS_COLORS: Record<string, string> = {
  unread: "bg-primary",
  read: "bg-subtext",
  approved: "bg-green",
  rejected: "bg-red",
  archived: "bg-subtext",
};

interface DirectorDetailViewProps {
  director: Director;
  authToken: string | null;
  onBack: () => void;
  onRun: () => void;
  onConfigure: () => void;
  onDelete: () => void;
  isRunning: boolean;
  isConfirmDelete: boolean;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const DirectorDetailView = React.memo(function DirectorDetailView({
  director: d,
  authToken,
  onBack,
  onRun,
  onConfigure,
  onDelete,
  isRunning,
  isConfirmDelete,
  t,
}: DirectorDetailViewProps) {
  const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
  const [loadingInbox, setLoadingInbox] = useState(false);

  useEffect(() => {
    if (!authToken) return;
    setLoadingInbox(true);
    fetchInbox(authToken, { director_id: d.id, limit: 5 })
      .then((data) => setInboxItems(data.items))
      .catch(() => {})
      .finally(() => setLoadingInbox(false));
  }, [authToken, d.id]);

  const needsSetup = d.setup_status === "needs_setup";
  const hasContext = (d.required_context ?? []).length > 0;
  const requiredFields = (d.required_context ?? []).filter((f) => f.required);
  const configuredRequired = requiredFields.filter(
    (f) => d.context_window[f.key]?.trim(),
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={onBack}
          className="mt-1 p-1.5 rounded-lg text-text2 hover:bg-surface2 transition-colors shrink-0"
          title={t("directors.detail.back")}
        >
          <ArrowLeft size={16} />
        </button>
        <span className="text-2xl shrink-0">{d.emoji}</span>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-text">{d.name}</h2>
          {d.description && (
            <p className="text-xs text-text2 mt-0.5">{d.description}</p>
          )}
        </div>
        <span className={`w-2.5 h-2.5 rounded-full mt-2 shrink-0 ${d.enabled ? "bg-green" : "bg-subtext"}`} />
      </div>

      {/* Info chips */}
      <div className="flex items-center gap-2 flex-wrap">
        {d.schedule ? (
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue/10 text-blue flex items-center gap-1">
            <Clock size={10} />
            {d.schedule}
          </span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded-full bg-surface2 text-subtext">
            {t("directors.manual")}
          </span>
        )}
        <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 ${
          d.permission_level === "yellow" ? "bg-yellow/10 text-yellow" : "bg-green/10 text-green"
        }`}>
          <Shield size={10} />
          {t("directors.detail.permLevel")}: {d.permission_level}
        </span>
        {d.can_delegate && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-mauve/10 text-mauve">
            {t("directors.canDelegate")}
          </span>
        )}
        {d.next_run && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-surface2 text-text2 flex items-center gap-1">
            <Clock size={10} />
            {new Date(d.next_run * 1000).toLocaleString()}
          </span>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-surface2/50">
          <span className="text-xs text-subtext block">{t("directors.runs", { count: d.run_count })}</span>
          <span className="text-lg font-semibold text-text">{d.run_count}</span>
        </div>
        <div className="p-3 rounded-lg bg-surface2/50">
          <span className="text-xs text-subtext block">{t("directors.totalCost")}</span>
          <span className="text-lg font-semibold text-text">${d.total_cost.toFixed(4)}</span>
        </div>
      </div>

      {/* Setup progress */}
      {hasContext && (
        <div className="p-3 rounded-lg bg-surface2/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text flex items-center gap-1.5">
              <Settings size={12} className="text-text2" />
              {t("directors.contextEditor")}
            </span>
            {requiredFields.length > 0 && (
              <span className={`text-xs ${needsSetup ? "text-yellow" : "text-green"}`}>
                {t("directors.detail.setupProgress", {
                  done: configuredRequired.length,
                  total: requiredFields.length,
                })}
              </span>
            )}
          </div>
          {requiredFields.length > 0 && (
            <div className="h-1.5 bg-surface2 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${needsSetup ? "bg-yellow" : "bg-green"}`}
                style={{ width: `${requiredFields.length > 0 ? (configuredRequired.length / requiredFields.length) * 100 : 0}%` }}
              />
            </div>
          )}
          <button
            onClick={onConfigure}
            className="text-xs text-primary hover:underline"
          >
            {t("directors.configure")}
          </button>
        </div>
      )}

      {/* Role prompt */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-text">{t("directors.detail.rolePrompt")}</span>
        <pre className="text-xs text-text2 bg-surface2/50 rounded-lg p-3 max-h-32 overflow-y-auto whitespace-pre-wrap font-mono">
          {d.role_prompt || "\u2014"}
        </pre>
      </div>

      {/* Last run result */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-text">{t("directors.detail.lastResult")}</span>
        {d.last_result ? (
          <div className="text-xs text-text2 bg-surface2/50 rounded-lg p-3 max-h-40 overflow-y-auto whitespace-pre-wrap">
            {d.last_run && (
              <span className="text-xs text-subtext block mb-1">
                {new Date(d.last_run * 1000).toLocaleString()}
              </span>
            )}
            {d.last_result}
          </div>
        ) : (
          <p className="text-xs text-subtext italic">{t("directors.detail.noResult")}</p>
        )}
        {d.last_error && (
          <p className="text-xs text-red bg-red/5 px-3 py-2 rounded-lg">
            {t("directors.detail.lastError")}: {d.last_error}
          </p>
        )}
      </div>

      {/* Related inbox items */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-text">{t("directors.detail.relatedInbox")}</span>
        {loadingInbox ? (
          <SkeletonList count={2} height="h-10" />
        ) : inboxItems.length === 0 ? (
          <p className="text-xs text-subtext italic py-2">{t("directors.noActivity")}</p>
        ) : (
          <div className="space-y-1">
            {inboxItems.map((item) => {
              const TypeIcon = INBOX_TYPE_ICONS[item.content_type] || Mail;
              const statusColor = INBOX_STATUS_COLORS[item.status] || "bg-subtext";
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface2/50 hover:bg-surface2 transition-colors"
                >
                  <TypeIcon size={12} className="text-text2 shrink-0" />
                  <span className="text-xs text-text flex-1 truncate">{item.title}</span>
                  <span className={`w-2 h-2 rounded-full shrink-0 ${statusColor}`} />
                  <span className="text-xs text-subtext shrink-0">
                    {new Date(item.created_at * 1000).toLocaleDateString()}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-2 border-t border-overlay">
        <button
          onClick={onRun}
          disabled={isRunning || needsSetup}
          className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-sm font-medium disabled:opacity-40"
          title={needsSetup ? t("directors.needsSetup") : t("directors.runNow")}
        >
          {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {t("directors.runNow")}
        </button>
        {hasContext && (
          <button
            onClick={onConfigure}
            className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-surface2 text-text2 hover:text-text hover:bg-surface2/80 transition-colors text-sm"
          >
            <Settings size={14} />
            {t("directors.configure")}
          </button>
        )}
        <button
          onClick={onDelete}
          className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-red hover:bg-red/10 transition-colors text-sm"
        >
          <Trash2 size={14} />
          {isConfirmDelete ? t("directors.deleteConfirm", { name: d.name }) : t("directors.delete")}
        </button>
      </div>
    </div>
  );
});
