/**
 * Handler for director_event WebSocket messages.
 *
 * Updates the DirectorRunStore with real-time execution progress
 * and shows toasts for key events (start, failure, completion).
 */

import { useDirectorRunStore } from "@/stores/useDirectorRunStore";
import { useToastStore } from "@/stores/useToastStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { translate } from "@/lib/translations";
import type { WSReceiveMessage } from "@/lib/types";

/**
 * Handle a director_event message.
 * Returns true if the message was handled, false otherwise.
 */
export function handleDirectorMessage(
  msg: WSReceiveMessage,
  _agentId: string,
): boolean {
  if (msg.type !== "director_event") return false;

  const store = useDirectorRunStore.getState();
  const lang = useSettingsStore.getState().language;

  switch (msg.event) {
    case "team_run_start": {
      // Only initialize if no active run (HTTP callback may have beaten us)
      if (!store.activeRun) {
        store.startRun(msg.project_id, msg.project_name, msg.director_count, []);
      }
      useToastStore.getState().addToast({
        type: "info",
        message: translate(lang, "directors.teamRunStarted", {
          name: msg.project_name,
          count: msg.director_count,
        }),
      });
      return true;
    }

    case "run_complete": {
      store.completeDirector(msg.director_id, msg.director_name, msg.success);

      // Toast only on failures (successes are shown via status dots)
      if (!msg.success) {
        useToastStore.getState().addToast({
          type: "error",
          message: translate(lang, "directors.directorFailed", {
            name: msg.director_name,
          }),
        });
      }
      return true;
    }

    case "task_complete": {
      store.incrementTasks();
      return true;
    }

    case "team_run_complete": {
      store.finishRun();
      const successCount = msg.results.filter((r) => r.success).length;
      const failCount = msg.results.length - successCount;
      useToastStore.getState().addToast({
        type: failCount === 0 ? "success" : "warning",
        message: translate(lang, "directors.teamRunFinished", {
          name: msg.project_name,
          success: successCount,
          failed: failCount,
        }),
        duration: 6000,
      });
      return true;
    }

    default:
      return false;
  }
}
