"use client";

import { useState, useEffect, useCallback } from "react";
import { browseDirectory } from "@/lib/api";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { FileEntry } from "@/lib/types";

function formatSize(bytes: number): string {
  if (bytes === 0) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

export default function FileBrowserPanel() {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [currentPath, setCurrentPath] = useState("");
  const [loading, setLoading] = useState(true);

  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const setAgentBrowsePath = useAgentStore((s) => s.setAgentBrowsePath);
  const setAgentCwd = useAgentStore((s) => s.setAgentCwd);
  const authToken = useConnectionStore((s) => s.authToken);
  const send = useConnectionStore((s) => s.send);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const browsePath = activeAgent?.currentBrowsePath || "~";

  const loadDirectory = useCallback(
    async (path: string) => {
      setLoading(true);
      try {
        const data = await browseDirectory(path, authToken);
        setEntries(data.entries);
        setCurrentPath(data.current);
        if (activeAgentId) {
          setAgentBrowsePath(activeAgentId, data.current);
        }
      } catch (err) {
        console.error("Browse error:", err);
      } finally {
        setLoading(false);
      }
    },
    [authToken, activeAgentId, setAgentBrowsePath]
  );

  // Load initial directory
  useEffect(() => {
    loadDirectory(browsePath);
  }, [browsePath, loadDirectory]);

  const navigateTo = (path: string) => {
    loadDirectory(path);
  };

  const goUp = () => {
    // Go to parent directory
    const parts = currentPath.replace(/\\/g, "/").split("/").filter(Boolean);
    if (parts.length > 1) {
      parts.pop();
      const parent = parts.join("/");
      // On Windows, restore the drive letter format
      if (currentPath.includes(":\\") || currentPath.includes(":/")) {
        navigateTo(parent);
      } else {
        navigateTo("/" + parent);
      }
    }
  };

  const handleSelect = () => {
    if (!activeAgentId) return;

    // Set the CWD in the store
    setAgentCwd(activeAgentId, currentPath);

    // Tell server about the chosen directory
    send({ type: "set_cwd", path: currentPath, agent_id: activeAgentId });

    // Switch to chat
    setActivePanel("chat");
  };

  // Separate directories and files, sort alphabetically
  const dirs = entries.filter((e) => e.is_dir).sort((a, b) => a.name.localeCompare(b.name));
  const files = entries.filter((e) => !e.is_dir).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="flex-1 flex flex-col overflow-hidden p-4">
      {/* Header */}
      <div className="mb-4">
        <h2
          className="font-[family-name:var(--font-orbitron)] text-lg font-bold bg-clip-text text-transparent mb-2"
          style={{
            backgroundImage: "linear-gradient(135deg, var(--cyan), var(--magenta))",
          }}
        >
          {t("browser.title")}
        </h2>

        {/* Current path */}
        <p className="text-xs text-subtext font-[family-name:var(--font-jetbrains)] truncate">
          {currentPath}
        </p>
      </div>

      {/* Loading */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-text2 text-sm">
          {t("browser.loading")}
        </div>
      ) : (
        <>
          {/* File list */}
          <div className="flex-1 overflow-y-auto rounded-lg border border-overlay bg-surface">
            {/* Go up entry */}
            <button
              onClick={goUp}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface2 transition-colors text-left border-b border-overlay/50"
            >
              <span className="text-base">&#x1F4C1;</span>
              <span className="text-sm text-cyan font-[family-name:var(--font-jetbrains)]">..</span>
            </button>

            {/* Directories */}
            {dirs.map((entry) => (
              <button
                key={entry.path}
                onClick={() => navigateTo(entry.path)}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface2 transition-colors text-left border-b border-overlay/50"
              >
                <span className="text-base">&#x1F4C1;</span>
                <span className="flex-1 text-sm text-cyan font-[family-name:var(--font-jetbrains)] truncate">
                  {entry.name}
                </span>
              </button>
            ))}

            {/* Files */}
            {files.map((entry) => (
              <div
                key={entry.path}
                className="flex items-center gap-3 px-4 py-2.5 border-b border-overlay/50"
              >
                <span className="text-base">&#x1F4C4;</span>
                <span className="flex-1 text-sm text-text2 font-[family-name:var(--font-jetbrains)] truncate">
                  {entry.name}
                </span>
                <span className="text-xs text-subtext font-[family-name:var(--font-jetbrains)] shrink-0">
                  {formatSize(entry.size)}
                </span>
              </div>
            ))}

            {dirs.length === 0 && files.length === 0 && (
              <div className="p-4 text-center text-sm text-subtext">
                Empty directory
              </div>
            )}
          </div>

          {/* Select button */}
          <button
            onClick={handleSelect}
            className="mt-4 w-full py-3 rounded-lg font-[family-name:var(--font-orbitron)] text-sm font-bold text-white transition-all hover:shadow-[0_0_20px_var(--neon-glow)]"
            style={{
              background: "linear-gradient(135deg, var(--cyan), var(--mauve))",
            }}
          >
            {t("browser.selectBtn")}
          </button>
        </>
      )}
    </div>
  );
}
