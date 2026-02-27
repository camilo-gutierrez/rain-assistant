"use client";

import { useState, useRef, useCallback } from "react";
import type { ComputerScreenshotMessage } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";

interface Props {
  readonly message: ComputerScreenshotMessage;
  readonly interactive?: boolean;
  readonly onClickHint?: (x: number, y: number) => void;
}

export default function ScreenshotViewer({ message, interactive, onClickHint }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [clickMarkers, setClickMarkers] = useState<{ x: number; y: number; id: number }[]>([]);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const markerIdRef = useRef(0);
  const { t } = useTranslation();

  const mediaType = message.mediaType || "image/png";
  const isUnchanged = message.changed === false;

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
          className="inline-block border-0 bg-transparent p-0"
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
        </button>
      )}
    </div>
  );
}
