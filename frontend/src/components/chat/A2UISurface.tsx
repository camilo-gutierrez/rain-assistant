"use client";

import React, { useState, useCallback, useMemo } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { A2UISurfaceMessage, A2UIComponent, A2UISurface as SurfaceType } from "@/lib/types";
import {
  Check, X, Edit, Search, Home, Settings, Star, Heart, AlertTriangle,
  Info, HelpCircle, ArrowRight, ArrowLeft, ArrowUp, ArrowDown,
  Plus, Minus, Trash2, Copy, Eye, EyeOff, Download, Upload,
  Mail, Phone, MapPin, Calendar, Clock, User, Users, FileText,
  Folder, Image, Link, Globe, Lock, Unlock, Bell, BellOff,
  RefreshCw, Play, Pause, Square, ChevronRight, ChevronDown,
  Zap, Shield, Database, Code, Terminal, BookOpen,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Icon mapping (Material Icons names → Lucide equivalents)
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, LucideIcon> = {
  check: Check, close: X, edit: Edit, search: Search,
  home: Home, settings: Settings, star: Star, favorite: Heart,
  warning: AlertTriangle, info: Info, help: HelpCircle,
  arrow_forward: ArrowRight, arrow_back: ArrowLeft,
  arrow_upward: ArrowUp, arrow_downward: ArrowDown,
  add: Plus, remove: Minus, delete: Trash2, copy: Copy,
  visibility: Eye, visibility_off: EyeOff,
  download: Download, upload: Upload,
  email: Mail, phone: Phone, location_on: MapPin,
  calendar_today: Calendar, schedule: Clock,
  person: User, people: Users, group: Users,
  description: FileText, folder: Folder, image: Image,
  link: Link, language: Globe, lock: Lock, lock_open: Unlock,
  notifications: Bell, notifications_off: BellOff,
  refresh: RefreshCw, play_arrow: Play, pause: Pause, stop: Square,
  chevron_right: ChevronRight, expand_more: ChevronDown,
  bolt: Zap, security: Shield, storage: Database,
  code: Code, terminal: Terminal, menu_book: BookOpen,
};

function resolveIcon(name: string): LucideIcon | null {
  return ICON_MAP[name] || ICON_MAP[name.toLowerCase().replace(/ /g, "_")] || null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  readonly message: A2UISurfaceMessage;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function A2UISurface({ message }: Props) {
  const { surface } = message;
  const { t } = useTranslation();
  const send = useConnectionStore((s) => s.send);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);

  // Form state: fieldName → value
  const [fieldValues, setFieldValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const comp of Object.values(surface.components)) {
      if (comp.fieldName) {
        if (comp.type === "checkbox") {
          initial[comp.fieldName] = comp.checked ? "true" : "false";
        } else if (comp.type === "slider") {
          initial[comp.fieldName] = String(comp.value ?? comp.min ?? 0);
        } else if (comp.type === "text_field") {
          initial[comp.fieldName] = comp.value ?? "";
        }
      }
    }
    return initial;
  });

  const setField = useCallback((name: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleAction = useCallback(
    (actionName: string) => {
      if (!activeAgentId) return;
      const context: Record<string, unknown> = { ...fieldValues };
      send({
        type: "a2ui_user_action",
        agent_id: activeAgentId,
        surface_id: surface.id,
        action_name: actionName,
        context,
      });
    },
    [activeAgentId, fieldValues, send, surface.id],
  );

  // Recursive renderer
  const renderComponent = useCallback(
    (compId: string): React.ReactNode => {
      const comp = surface.components[compId];
      if (!comp) return null;

      switch (comp.type) {
        // Layout
        case "column":
          return (
            <div
              key={compId}
              className="flex flex-col"
              style={{ gap: comp.spacing ?? 8 }}
            >
              {comp.children?.map((childId) => (
                <React.Fragment key={childId}>
                  {renderComponent(childId)}
                </React.Fragment>
              ))}
            </div>
          );

        case "row":
          return (
            <div
              key={compId}
              className="flex flex-row flex-wrap items-center"
              style={{ gap: comp.spacing ?? 8 }}
            >
              {comp.children?.map((childId) => (
                <React.Fragment key={childId}>
                  {renderComponent(childId)}
                </React.Fragment>
              ))}
            </div>
          );

        // Display
        case "text": {
          const variantClasses: Record<string, string> = {
            h1: "text-xl font-bold text-text",
            h2: "text-lg font-semibold text-text",
            h3: "text-base font-semibold text-text",
            body: "text-sm text-text",
            caption: "text-xs text-subtext",
          };
          const cls = variantClasses[comp.variant || "body"] || variantClasses.body;
          return (
            <p key={compId} className={cls}>
              {comp.text}
            </p>
          );
        }

        case "image":
          return (
            <img
              key={compId}
              src={comp.url}
              alt={comp.alt || ""}
              className="rounded-lg max-w-full"
              style={{
                width: comp.width ? `${comp.width}px` : undefined,
                height: comp.height ? `${comp.height}px` : undefined,
              }}
            />
          );

        case "divider":
          return <hr key={compId} className="border-overlay my-2" />;

        case "icon": {
          const IconComp = comp.name ? resolveIcon(comp.name) : null;
          if (!IconComp) return null;
          return (
            <IconComp
              key={compId}
              size={comp.size ?? 20}
              className="text-text2"
            />
          );
        }

        // Interactive
        case "button": {
          const styleClasses: Record<string, string> = {
            filled: "px-4 py-2 rounded-lg bg-primary text-on-primary hover:opacity-90 font-medium",
            outlined: "px-4 py-2 rounded-lg border border-primary text-primary hover:bg-primary/10 font-medium",
            text: "px-3 py-1.5 rounded-lg text-primary hover:bg-primary/10",
          };
          const cls = styleClasses[comp.style || "filled"] || styleClasses.filled;
          return (
            <button
              key={compId}
              onClick={() => comp.action && handleAction(comp.action)}
              className={`${cls} text-sm transition-colors focus-ring`}
            >
              {comp.label}
            </button>
          );
        }

        case "text_field":
          return (
            <div key={compId} className="flex flex-col gap-1">
              {comp.label && (
                <label className="text-sm font-medium text-text">
                  {comp.label}
                </label>
              )}
              <input
                type="text"
                value={comp.fieldName ? (fieldValues[comp.fieldName] ?? "") : ""}
                onChange={(e) =>
                  comp.fieldName && setField(comp.fieldName, e.target.value)
                }
                placeholder={comp.hint}
                className="w-full px-3 py-2 rounded-lg bg-surface2/50 border border-overlay text-sm text-text placeholder:text-subtext focus-ring"
              />
            </div>
          );

        case "checkbox":
          return (
            <label
              key={compId}
              className="flex items-center gap-2 cursor-pointer text-sm text-text"
            >
              <input
                type="checkbox"
                checked={
                  comp.fieldName
                    ? fieldValues[comp.fieldName] === "true"
                    : comp.checked ?? false
                }
                onChange={(e) =>
                  comp.fieldName &&
                  setField(comp.fieldName, e.target.checked.toString())
                }
                className="w-4 h-4 rounded accent-primary"
              />
              {comp.label}
            </label>
          );

        case "slider":
          return (
            <div key={compId} className="flex flex-col gap-1">
              {comp.label && (
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-text">
                    {comp.label}
                  </label>
                  <span className="text-xs text-subtext tabular-nums">
                    {comp.fieldName
                      ? fieldValues[comp.fieldName]
                      : comp.value}
                  </span>
                </div>
              )}
              <input
                type="range"
                min={comp.min ?? 0}
                max={comp.max ?? 100}
                value={
                  comp.fieldName
                    ? Number(fieldValues[comp.fieldName] ?? comp.value ?? 0)
                    : comp.value ?? 0
                }
                onChange={(e) =>
                  comp.fieldName && setField(comp.fieldName, e.target.value)
                }
                className="w-full accent-primary"
              />
            </div>
          );

        // Container
        case "card":
          return (
            <div
              key={compId}
              className="rounded-xl border border-overlay bg-surface"
              style={{ padding: comp.padding ?? 16 }}
            >
              {comp.title && (
                <h3 className="text-sm font-semibold text-text mb-3">
                  {comp.title}
                </h3>
              )}
              <div className="flex flex-col gap-2">
                {comp.children?.map((childId) => (
                  <React.Fragment key={childId}>
                    {renderComponent(childId)}
                  </React.Fragment>
                ))}
              </div>
            </div>
          );

        // Data
        case "data_table":
          return (
            <div
              key={compId}
              className="overflow-x-auto rounded-lg border border-overlay"
            >
              <table className="w-full text-sm">
                {comp.columns && (
                  <thead>
                    <tr className="bg-surface2/50">
                      {comp.columns.map((col, i) => (
                        <th
                          key={i}
                          className="px-3 py-2 text-left font-medium text-text border-b border-overlay"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {comp.rows?.map((row, ri) => (
                    <tr
                      key={ri}
                      className="border-b border-overlay last:border-0"
                    >
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-2 text-text">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );

        // Feedback
        case "progress_bar":
          return (
            <div key={compId} className="flex flex-col gap-1">
              {comp.label && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text">{comp.label}</span>
                  <span className="text-xs text-subtext tabular-nums">
                    {comp.value ?? 0}%
                  </span>
                </div>
              )}
              <div className="w-full h-2 rounded-full bg-surface2 overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(0, Number(comp.value) || 0))}%` }}
                />
              </div>
            </div>
          );

        case "spacer":
          return (
            <div
              key={compId}
              style={{ height: comp.height ?? 16 }}
            />
          );

        default:
          return null;
      }
    },
    [surface.components, fieldValues, handleAction, setField],
  );

  const rootContent = useMemo(
    () => renderComponent(surface.root),
    [renderComponent, surface.root],
  );

  return (
    <div className="my-2 p-4 rounded-xl border border-primary/20 bg-surface shadow-sm animate-fade-in">
      {surface.title && (
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-overlay">
          <Zap size={14} className="text-primary" />
          <span className="text-sm font-semibold text-text">
            {surface.title}
          </span>
        </div>
      )}
      {rootContent}
    </div>
  );
}

export default React.memo(A2UISurface);
