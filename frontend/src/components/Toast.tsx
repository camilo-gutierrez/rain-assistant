"use client";

import { useEffect, useState } from "react";
import { useToastStore, type Toast } from "@/stores/useToastStore";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

const ICON_MAP = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const COLOR_MAP = {
  success: {
    bg: "bg-green/10 border-green/30",
    icon: "text-green",
    text: "text-green",
  },
  error: {
    bg: "bg-red/10 border-red/30",
    icon: "text-red",
    text: "text-red",
  },
  warning: {
    bg: "bg-yellow/10 border-yellow/30",
    icon: "text-yellow",
    text: "text-yellow",
  },
  info: {
    bg: "bg-blue/10 border-blue/30",
    icon: "text-blue",
    text: "text-blue",
  },
};

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [exiting, setExiting] = useState(false);
  const { t } = useTranslation();
  const Icon = ICON_MAP[toast.type];
  const colors = COLOR_MAP[toast.type];

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(onDismiss, 150);
  };

  // Auto-trigger exit animation before removal
  useEffect(() => {
    if (toast.duration > 0) {
      const timer = setTimeout(() => setExiting(true), toast.duration - 200);
      return () => clearTimeout(timer);
    }
  }, [toast.duration]);

  return (
    <div
      role="alert"
      className={`
        flex items-start gap-2.5 px-3.5 py-3 rounded-2xl border backdrop-blur-xl
        shadow-2xl max-w-sm w-full pointer-events-auto
        ${colors.bg}
        ${exiting ? "animate-toast-exit" : "animate-toast-enter"}
      `}
    >
      <Icon className={`w-[18px] h-[18px] shrink-0 mt-0.5 ${colors.icon}`} />
      <p className={`text-sm flex-1 leading-snug ${colors.text}`}>
        {toast.message}
      </p>
      {toast.dismissible && (
        <button
          onClick={handleDismiss}
          className="shrink-0 p-0.5 rounded-md hover:bg-overlay/40 transition-colors"
          aria-label={t("a11y.dismiss")}
        >
          <X className="w-3.5 h-3.5 text-subtext" />
        </button>
      )}
    </div>
  );
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="
        fixed z-[60] pointer-events-none
        bottom-20 right-4 left-auto
        sm:bottom-6 sm:right-6
        max-sm:left-4 max-sm:right-4
        flex flex-col items-end gap-2
      "
    >
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          toast={toast}
          onDismiss={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
}
