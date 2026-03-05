"use client";

import { useState, useRef, useCallback, useMemo } from "react";
import type { ComputerScreenshotMessage, AnyMessage } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";

interface Props {
  readonly message: ComputerScreenshotMessage;
  readonly messages?: AnyMessage[];
  readonly interactive?: boolean;
  readonly onClickHint?: (x: number, y: number) => void;
}

export default function ScreenshotViewer({ message, messages, interactive, onClickHint }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [showDiff, setShowDiff] = useState(false);
  const [clickMarkers, setClickMarkers] = useState<{ x: number; y: number; id: number }[]>([]);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const markerIdRef = useRef(0);
  const { t } = useTranslation();

  const mediaType = message.mediaType || "image/png";
  const isUnchanged = message.changed === false;

  // Find the previous screenshot in messages for diff overlay
  const previousScreenshot = useMemo(() => {
    if (!messages) return null;
    const thisIndex = messages.findIndex((m) => m.id === message.id);
    if (thisIndex <= 0) return null;
    // Search backwards for the most recent computer_screenshot before this one
    for (let i = thisIndex - 1; i >= 0; i--) {
      if (messages[i].type === "computer_screenshot") {
        return messages[i] as ComputerScreenshotMessage;
      }
    }
    return null;
  }, [messages, message.id]);

  const hasPreviousScreenshot = previousScreenshot !== null;

  const handleImageClick = useCallback(
    (e: React.MouseEvent) => {
      if (!interactive || !imgRef.current || !onClickHint) return;

      const rect = imgRef.current.getBoundingClientRect();
      const relX = (e.clientX - rect.left) / rect.width;
      const relY = (e.clientY - rect.top) / rect.height;
      const x = Math.round(relX * imgRef.current.naturalWidth);
      const y = Math.round(relY * imgRef.current.naturalHeight);

      const markerId = ++markerIdRef.current;
      setClickMarkers((prev) => [...prev.slice(-4), { x: relX * 100, y: relY * 100, id: markerId }]);
      setTimeout(() => setClickMarkers((prev) => prev.filter((m) => m.id !== markerId)), 1500);

      onClickHint(x, y);
    },
    [interactive, onClickHint],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!interactive || !imgRef.current) {
        setCursor(null);
        return;
      }
      const rect = imgRef.current.getBoundingClientRect();
      setCursor({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    },
    [interactive],
  );

  const handleMouseLeave = useCallback(() => {
    setCursor(null);
  }, []);

  // Diff overlay element (shared between interactive and non-interactive modes)
  const diffOverlay = showDiff && previousScreenshot ? (
    <img
      src={`data:${previousScreenshot.mediaType || "image/png"};base64,${previousScreenshot.image}`}
      alt={t("cu.diffOverlay")}
      className="absolute inset-0 w-full h-full rounded-lg pointer-events-none"
      style={{
        mixBlendMode: "difference",
        opacity: 0.7,
        ...(zoom > 1 ? { transform: `scale(${zoom})`, transformOrigin: "top left" } : {}),
      }}
    />
  ) : null;

  return (
    <div className="flex flex-col gap-1 my-1 animate-fade-in">
      <div className="flex items-center gap-2 text-xs text-subtext">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple/10 text-purple font-medium">
          📸 {message.description}
        </span>
        {message.iteration > 0 && (
          <span className="text-subtext/60">{t("cu.iteration")} {message.iteration}</span>
        )}
        {isUnchanged && (
          <span className="px-2 py-0.5 rounded-full bg-surface2 text-subtext text-xs">
            {t("cu.screenshotUnchanged")}
          </span>
        )}
        {hasPreviousScreenshot && (
          <button
            onClick={() => setShowDiff((d) => !d)}
            className={`px-2 py-0.5 rounded-full text-xs font-medium focus-ring transition-colors ${
              showDiff
                ? "bg-primary/20 text-primary border border-primary/30"
                : "bg-surface2 text-subtext hover:text-text"
            }`}
          >
            {t("cu.diffToggle")}
          </button>
        )}
        {interactive && (
          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={() => setZoom((z) => Math.max(1, z - 0.5))}
              className="px-1.5 py-0.5 rounded bg-surface2 text-subtext hover:text-text focus-ring text-xs"
              disabled={zoom <= 1}
            >
              {t("cu.zoomOut")}
            </button>
            <span className="text-subtext text-xs tabular-nums">{zoom}x</span>
            <button
              onClick={() => setZoom((z) => Math.min(3, z + 0.5))}
              className="px-1.5 py-0.5 rounded bg-surface2 text-subtext hover:text-text focus-ring text-xs"
              disabled={zoom >= 3}
            >
              {t("cu.zoomIn")}
            </button>
          </div>
        )}
      </div>
      {interactive ? (
        <button
          type="button"
          className="relative inline-block border-0 bg-transparent p-0"
          style={{ cursor: "crosshair" }}
          onClick={handleImageClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <img
            ref={imgRef}
            src={`data:${mediaType};base64,${message.image}`}
            alt={message.description}
            className="rounded-lg border border-overlay transition-all hover:border-primary/40 max-w-full"
            style={zoom > 1 ? { transform: `scale(${zoom})`, transformOrigin: "top left" } : undefined}
          />
          {diffOverlay}
          {cursor && (
            <>
              <div
                className="absolute pointer-events-none bg-primary/40"
                style={{ left: cursor.x, top: 0, width: 1, height: "100%" }}
              />
              <div
                className="absolute pointer-events-none bg-primary/40"
                style={{ left: 0, top: cursor.y, width: "100%", height: 1 }}
              />
            </>
          )}
          {clickMarkers.map((m) => (
            <div
              key={m.id}
              className="absolute pointer-events-none"
              style={{ left: `${m.x}%`, top: `${m.y}%`, transform: "translate(-50%, -50%)" }}
            >
              <div className="w-4 h-4 rounded-full border-2 border-red bg-red/20 animate-ping" />
            </div>
          ))}
        </button>
      ) : (
        <button
          type="button"
          className="relative inline-block border-0 bg-transparent p-0"
          onClick={() => setExpanded(!expanded)}
        >
          <img
            ref={imgRef}
            src={`data:${mediaType};base64,${message.image}`}
            alt={message.description}
            className={`rounded-lg border border-overlay cursor-pointer transition-all hover:border-primary/40 ${
              expanded ? "max-w-full" : "max-w-sm"
            }`}
          />
          {diffOverlay}
        </button>
      )}
    </div>
  );
}
