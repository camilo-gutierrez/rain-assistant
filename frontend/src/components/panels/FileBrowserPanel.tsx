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
  const setAgentPanel = useAgentStore((s) => s.setAgentPanel);
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

  useEffect(() => {
    loadDirectory(browsePath);
  }, [browsePath, loadDirectory]);

  const navigateTo = (path: string) => {
    loadDirectory(path);
  };

  const goUp = () => {
    const parts = currentPath.replace(/\\/g, "/").split("/").filter(Boolean);
    if (parts.length > 1) {
      parts.pop();
      const parent = parts.join("/");
      if (currentPath.includes(":\\") || currentPath.includes(":/")) {
        navigateTo(parent);
      } else {
        navigateTo("/" + parent);
      }
    }
  };

  const handleSelect = () => {
    if (!activeAgentId) return;
    setAgentCwd(activeAgentId, currentPath);
    send({ type: "set_cwd", path: currentPath, agent_id: activeAgentId });
    setAgentPanel(activeAgentId, "chat");
    setActivePanel("chat");
  };

  const dirs = entries.filter((e) => e.is_dir).sort((a, b) => a.name.localeCompare(b.name));
  const files = entries.filter((e) => !e.is_dir).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="flex-1 flex flex-col overflow-hidden p-4">
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-text mb-1">
          {t("browser.title")}
        </h2>
        <p className="text-xs text-subtext font-[family-name:var(--font-jetbrains)] truncate">
          {currentPath}
        </p>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-text2 text-sm">
          {t("browser.loading")}
        </div>
      ) : (
        <>
          {/* File list */}
          <div className="flex-1 overflow-y-auto rounded-lg bg-surface shadow-sm">
            {/* Go up */}
            <button
              onClick={goUp}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface2 transition-colors text-left border-b border-overlay/50"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary shrink-0">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <span className="text-sm text-primary font-medium">..</span>
            </button>

            {/* Directories */}
            {dirs.map((entry) => (
              <button
                key={entry.path}
                onClick={() => navigateTo(entry.path)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface2 transition-colors text-left border-b border-overlay/50"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary shrink-0">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                </svg>
                <span className="flex-1 text-sm text-primary font-medium truncate">
                  {entry.name}
                </span>
              </button>
            ))}

            {/* Files */}
            {files.map((entry) => (
              <div
                key={entry.path}
                className="flex items-center gap-3 px-4 py-3 border-b border-overlay/50"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-subtext shrink-0">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <span className="flex-1 text-sm text-text2 truncate">
                  {entry.name}
                </span>
                <span className="text-xs text-subtext shrink-0">
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
            className="mt-4 w-full py-3 rounded-lg text-sm font-semibold bg-primary text-on-primary transition-all hover:bg-primary-dark shadow-sm"
          >
            {t("browser.selectBtn")}
          </button>
        </>
      )}
    </div>
  );
}
