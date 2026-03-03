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
  fetchDirectorTemplates,
  fetchTeamTemplates,
  createDirector,
  createProject,
  updateDirector,
  fetchDirectorTasks,
  fetchDirectorActivity,
  fetchProjects,
} from "@/lib/api";
import type {
  Director,
  DirectorTemplate,
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
  Download,
  FolderOpen,
  Users,
  CheckCircle,
  X,
} from "lucide-react";
import EmptyState from "@/components/EmptyState";
import { SkeletonList } from "@/components/Skeleton";

type Tab = "directors" | "templates" | "tasks" | "activity";
type TemplateSubTab = "individual" | "teams";

export default function DirectorsPanel() {
  const { t } = useTranslation();
  const authToken = useConnectionStore((s) => s.authToken);

  const [tab, setTab] = useState<Tab>("directors");
  const [templateSubTab, setTemplateSubTab] = useState<TemplateSubTab>("individual");
  const [directors, setDirectors] = useState<Director[]>([]);
  const [templates, setTemplates] = useState<DirectorTemplate[]>([]);
  const [tasks, setTasks] = useState<DirectorTask[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [teamTemplates, setTeamTemplates] = useState<TeamTemplate[]>([]);
  const [creatingProjectId, setCreatingProjectId] = useState<string | null>(null);
  const [expandedTeamId, setExpandedTeamId] = useState<string | null>(null);

  // Team run state from store (replaces local teamRunning boolean)
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
      const [tmplData, teamData] = await Promise.all([
        fetchDirectorTemplates(authToken),
        fetchTeamTemplates(authToken),
      ]);
      setTemplates(tmplData.templates);
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

  // Auto-refresh data when a team run finishes (activeRun → null)
  const prevRunRef = useRef(activeRun);
  useEffect(() => {
    if (prevRunRef.current && !activeRun) {
      // Run just finished and was cleared — refresh data
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

  async function handleInstallTemplate(tmpl: DirectorTemplate, projectId?: string) {
    if (!authToken) return;
    setInstallingId(tmpl.id);
    try {
      const data = await createDirector({
        id: projectId ? `${projectId}_${tmpl.id}` : tmpl.id,
        name: tmpl.name,
        emoji: tmpl.emoji,
        description: tmpl.description,
        role_prompt: tmpl.role_prompt,
        schedule: tmpl.schedule,
        tools_allowed: tmpl.tools_allowed,
        plugins_allowed: tmpl.plugins_allowed,
        permission_level: tmpl.permission_level as "green" | "yellow",
        can_delegate: tmpl.can_delegate,
        project_id: projectId || activeProjectId || "default",
      } as Parameters<typeof createDirector>[0], authToken);
      setDirectors((prev) => [...prev, data.director]);
      setTab("directors");
    } catch {
      // silent
    } finally {
      setInstallingId(null);
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
      // Initialize run store from HTTP response (if WS hasn't beaten us)
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
      // silent — HTTP failed, no WS events will come
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "directors", label: t("directors.title") },
    { key: "templates", label: t("directors.templates") },
    { key: "tasks", label: t("directors.taskQueue") },
    { key: "activity", label: t("directors.activity") },
  ];

  const directorIds = new Set(directors.map((d) => d.id));

  const activeProject = projects.find((p) => p.id === activeProjectId);

  return (
    <div className="p-4 space-y-4">
      {/* Project Switcher */}
      {projects.length > 0 && (
        <div className="flex items-center gap-2">
          <FolderOpen size={14} className="text-text2 shrink-0" />
          <select
            value={activeProjectId}
            onChange={(e) => setActiveProjectId(e.target.value)}
            className="flex-1 text-xs bg-surface2/50 border border-border rounded-md px-2 py-1.5 text-text focus:outline-none focus:ring-1 focus:ring-primary"
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
                <TeamRunProgress run={activeRun} onDismiss={clearRun} t={t} />
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
          {/* Inner sub-tabs: Individual | Teams */}
          <div className="flex gap-1 bg-surface2/30 rounded-lg p-0.5">
            {(
              [
                { key: "individual" as TemplateSubTab, label: t("directors.individualTemplates") },
                { key: "teams" as TemplateSubTab, label: t("directors.teamTemplates") },
              ] as const
            ).map((st) => (
              <button
                key={st.key}
                onClick={() => setTemplateSubTab(st.key)}
                className={`flex-1 text-xs font-medium py-1.5 px-2 rounded-md transition-colors ${
                  templateSubTab === st.key
                    ? "bg-surface text-text shadow-sm"
                    : "text-subtext hover:text-text2"
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>

          {loading ? (
            <SkeletonList count={3} height="h-20" />
          ) : templateSubTab === "individual" ? (
            /* Individual Directors sub-tab */
            templates.length === 0 ? (
              <EmptyState icon={Bot} title={t("directors.noTemplates")} />
            ) : (
              <div className="space-y-2">
                {activeProject && (
                  <span className="text-xs text-subtext px-1">
                    {t("projects.installTo", { name: `${activeProject.emoji} ${activeProject.name}` })}
                  </span>
                )}
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
            )
          ) : (
            /* Teams sub-tab */
            teamTemplates.length === 0 ? (
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
            )
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
  t: (key: string, params?: Record<string, string | number>) => string;
}

const TeamRunProgress = React.memo(function TeamRunProgress({
  run,
  onDismiss,
  t,
}: TeamRunProgressProps) {
  const directorEntries = Object.values(run.directors);
  const completedCount = directorEntries.filter(
    (d) => d.status === "completed" || d.status === "failed",
  ).length;
  const total = Math.max(run.directorCount, directorEntries.length);
  const allDone = completedCount >= total && total > 0;
  const pct = total > 0 ? (completedCount / total) * 100 : 0;

  return (
    <div className="rounded-lg bg-primary/5 border border-primary/20 overflow-hidden animate-[fade-in_0.2s_ease-out]">
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
