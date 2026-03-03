import { create } from "zustand";

export type DirectorRunStatus = "pending" | "running" | "completed" | "failed";

export interface DirectorRunEntry {
  id: string;
  name: string;
  status: DirectorRunStatus;
}

export interface ActiveTeamRun {
  projectId: string;
  projectName: string;
  directorCount: number;
  directors: Record<string, DirectorRunEntry>;
  completedTasks: number;
  startedAt: number;
}

interface DirectorRunState {
  activeRun: ActiveTeamRun | null;

  /** Initialize a new team run. First director is marked "running". */
  startRun: (
    projectId: string,
    projectName: string,
    directorCount: number,
    directors: Array<{ id: string; name: string }>,
  ) => void;

  /** Mark a director as completed/failed, advance the next to "running". */
  completeDirector: (directorId: string, directorName: string, success: boolean) => void;

  /** Increment the delegated-tasks counter. */
  incrementTasks: () => void;

  /** Mark the run as finished. Auto-clears after 8 seconds. */
  finishRun: () => void;

  /** Manually dismiss the progress panel. */
  clearRun: () => void;
}

export const useDirectorRunStore = create<DirectorRunState>()((set, get) => ({
  activeRun: null,

  startRun: (projectId, projectName, directorCount, directors) => {
    const directorsMap: Record<string, DirectorRunEntry> = {};
    for (const d of directors) {
      directorsMap[d.id] = { id: d.id, name: d.name, status: "pending" };
    }
    // Mark the first director as "running" (sequential execution)
    const firstId = directors[0]?.id;
    if (firstId) {
      directorsMap[firstId] = { ...directorsMap[firstId], status: "running" };
    }
    set({
      activeRun: {
        projectId,
        projectName,
        directorCount,
        directors: directorsMap,
        completedTasks: 0,
        startedAt: Date.now(),
      },
    });
  },

  completeDirector: (directorId, directorName, success) => {
    const run = get().activeRun;
    if (!run) return;

    const directors = { ...run.directors };

    // If director isn't tracked yet (WS arrived before HTTP), add it dynamically
    if (!directors[directorId]) {
      directors[directorId] = {
        id: directorId,
        name: directorName,
        status: success ? "completed" : "failed",
      };
    } else {
      directors[directorId] = {
        ...directors[directorId],
        status: success ? "completed" : "failed",
      };
    }

    // Mark the next pending director as "running" (sequential execution)
    const pendingIds = Object.keys(directors).filter(
      (id) => directors[id].status === "pending",
    );
    if (pendingIds.length > 0) {
      const nextId = pendingIds[0];
      directors[nextId] = { ...directors[nextId], status: "running" };
    }

    set({ activeRun: { ...run, directors } });
  },

  incrementTasks: () => {
    const run = get().activeRun;
    if (!run) return;
    set({ activeRun: { ...run, completedTasks: run.completedTasks + 1 } });
  },

  finishRun: () => {
    const run = get().activeRun;
    if (!run) return;

    // Ensure all directors are in a terminal state
    const directors = { ...run.directors };
    for (const id of Object.keys(directors)) {
      if (directors[id].status === "pending" || directors[id].status === "running") {
        directors[id] = { ...directors[id], status: "completed" };
      }
    }
    set({ activeRun: { ...run, directors } });

    // Auto-clear after 8 seconds so the summary is visible briefly
    const startedAt = run.startedAt;
    setTimeout(() => {
      const current = get().activeRun;
      if (current && current.startedAt === startedAt) {
        set({ activeRun: null });
      }
    }, 8000);
  },

  clearRun: () => set({ activeRun: null }),
}));
