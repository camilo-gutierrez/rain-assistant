"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useTranslation } from "@/hooks/useTranslation";
import { updateDirector } from "@/lib/api";
import type { Director, ContextFieldMeta } from "@/lib/types";
import { X, Loader2, AlertTriangle } from "lucide-react";

interface Props {
  director: Director;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Modal dialog for editing a director's context_window fields.
 * Renders a dynamic form based on the director's required_context metadata.
 */
export default function DirectorContextEditor({
  director,
  onClose,
  onSaved,
}: Props) {
  const { t, language } = useTranslation();
  const token = useConnectionStore((s) => s.authToken);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const backdropRef = useRef<HTMLDivElement>(null);

  // Initialize values from context_window
  useEffect(() => {
    const initial: Record<string, string> = {};
    for (const field of director.required_context ?? []) {
      const raw = director.context_window[field.key];
      if (raw != null) {
        if (field.type === "tags") {
          try {
            const arr = JSON.parse(raw);
            initial[field.key] = Array.isArray(arr) ? arr.join(", ") : raw;
          } catch {
            initial[field.key] = raw;
          }
        } else {
          initial[field.key] = raw;
        }
      } else {
        initial[field.key] = field.default || "";
      }
    }
    // Extra keys not in required_context
    const knownKeys = new Set((director.required_context ?? []).map((f) => f.key));
    for (const [key, val] of Object.entries(director.context_window)) {
      if (!knownKeys.has(key)) {
        initial[key] = val;
      }
    }
    setValues(initial);
  }, [director]);

  const setValue = useCallback((key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  const handleSave = useCallback(async () => {
    // Validate required fields
    for (const field of director.required_context ?? []) {
      if (field.required && !values[field.key]?.trim()) {
        setError(`${getLabel(field)}: ${t("directors.fieldRequired")}`);
        return;
      }
    }

    setSaving(true);
    setError("");

    try {
      // Build context_window
      const ctx: Record<string, string> = {};
      for (const field of director.required_context ?? []) {
        const val = values[field.key]?.trim() || "";
        if (!val) continue;

        if (field.type === "tags") {
          const tags = val
            .split(/[,\n]/)
            .map((s) => s.trim())
            .filter(Boolean);
          ctx[field.key] = JSON.stringify(tags);
        } else {
          ctx[field.key] = val;
        }
      }

      // Preserve extra keys
      const knownKeys = new Set((director.required_context ?? []).map((f) => f.key));
      for (const [key, val] of Object.entries(director.context_window)) {
        if (!knownKeys.has(key)) {
          ctx[key] = values[key]?.trim() || val;
        }
      }

      await updateDirector(director.id, { context_window: ctx } as Partial<Director>, token);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [director, values, token, onSaved, t]);

  const getLabel = (field: ContextFieldMeta) =>
    language === "es" && field.label_es ? field.label_es : field.label;

  const getHint = (field: ContextFieldMeta) =>
    language === "es" && field.hint_es ? field.hint_es : field.hint;

  // Group fields
  const groups: Record<string, ContextFieldMeta[]> = {};
  for (const field of director.required_context ?? []) {
    const g = field.group || "general";
    if (!groups[g]) groups[g] = [];
    groups[g].push(field);
  }

  const groupLabel = (g: string) =>
    t(`directors.contextGroups.${g}`) || g;

  const groupIcon = (g: string) => {
    switch (g) {
      case "profile":
        return "\u{1F464}";
      case "search":
        return "\u{1F50D}";
      case "filters":
        return "\u{2699}\u{FE0F}";
      default:
        return "\u{1F4CB}";
    }
  };

  const inputClasses =
    "w-full px-3 py-2 rounded-lg bg-surface2/50 border border-border text-sm text-text placeholder:text-subtext focus:outline-none focus:ring-2 focus:ring-primary";

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === backdropRef.current && onClose()}
    >
      <div className="bg-bg rounded-2xl shadow-2xl w-full max-w-xl max-h-[85vh] flex flex-col m-4 border border-border">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
          <span className="text-2xl">{director.emoji}</span>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-text truncate">
              {director.name}
            </h2>
            <p className="text-xs text-text2">
              {t("directors.contextEditor")}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface2 text-text2 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Needs setup banner */}
        {director.setup_status === "needs_setup" && (
          <div className="mx-5 mt-4 p-3 rounded-xl bg-yellow/10 border border-yellow/30 flex items-start gap-2">
            <AlertTriangle size={14} className="text-yellow shrink-0 mt-0.5" />
            <p className="text-xs text-yellow">
              {t("directors.needsSetupHint").replace(
                "{fields}",
                (director.missing_fields ?? []).join(", ")
              )}
            </p>
          </div>
        )}

        {/* Fields */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {Object.entries(groups).map(([group, fields]) => (
            <div key={group}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm">{groupIcon(group)}</span>
                <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                  {groupLabel(group)}
                </span>
                <div className="flex-1 h-px bg-border" />
              </div>
              {fields.map((field) => (
                <div key={field.key} className="mb-4">
                  <label className="block text-sm font-medium text-text mb-1">
                    {getLabel(field)}
                    {field.required && (
                      <span className="text-red ml-1">*</span>
                    )}
                  </label>
                  {field.type === "textarea" ? (
                    <textarea
                      value={values[field.key] || ""}
                      onChange={(e) => setValue(field.key, e.target.value)}
                      placeholder={getHint(field)}
                      rows={4}
                      className={`${inputClasses} resize-y`}
                    />
                  ) : field.type === "tags" ? (
                    <div>
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {(values[field.key] || "")
                          .split(/[,\n]/)
                          .map((s) => s.trim())
                          .filter(Boolean)
                          .map((tag, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface2 text-xs text-text"
                            >
                              {tag}
                              <button
                                onClick={() => {
                                  const tags = (values[field.key] || "")
                                    .split(/[,\n]/)
                                    .map((s) => s.trim())
                                    .filter(Boolean);
                                  tags.splice(i, 1);
                                  setValue(field.key, tags.join(", "));
                                }}
                                className="text-subtext hover:text-red transition-colors"
                              >
                                <X size={12} />
                              </button>
                            </span>
                          ))}
                      </div>
                      <input
                        type="text"
                        placeholder={getHint(field)}
                        className={inputClasses}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === ",") {
                            e.preventDefault();
                            const input = e.currentTarget;
                            const val = input.value.trim();
                            if (val) {
                              const existing = values[field.key] || "";
                              setValue(
                                field.key,
                                existing ? `${existing}, ${val}` : val
                              );
                              input.value = "";
                            }
                          }
                        }}
                      />
                    </div>
                  ) : field.type === "number" ? (
                    <input
                      type="number"
                      value={values[field.key] || ""}
                      onChange={(e) => setValue(field.key, e.target.value)}
                      placeholder={getHint(field)}
                      className={inputClasses}
                    />
                  ) : field.type === "select" ? (
                    <select
                      value={values[field.key] || ""}
                      onChange={(e) => setValue(field.key, e.target.value)}
                      className={inputClasses}
                    >
                      <option value="">{getHint(field)}</option>
                      {field.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : field.type === "toggle" ? (
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={values[field.key] === "true"}
                        onChange={(e) =>
                          setValue(field.key, e.target.checked.toString())
                        }
                        className="w-4 h-4 rounded accent-primary"
                      />
                      <span className="text-sm text-text2">
                        {getHint(field)}
                      </span>
                    </label>
                  ) : (
                    <input
                      type="text"
                      value={values[field.key] || ""}
                      onChange={(e) => setValue(field.key, e.target.value)}
                      placeholder={getHint(field)}
                      className={inputClasses}
                    />
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border flex items-center gap-3">
          {error && (
            <p className="flex-1 text-xs text-red truncate">{error}</p>
          )}
          <div className="flex-1" />
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-text2 hover:bg-surface2 transition-colors"
          >
            {t("directors.cancel") || "Cancel"}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-primary text-on-primary hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transition-colors"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {t("directors.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
