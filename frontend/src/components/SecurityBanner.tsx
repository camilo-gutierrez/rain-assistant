"use client";

import { useState } from "react";
import { isSecureContext } from "@/lib/constants";
import { useTranslation } from "@/hooks/useTranslation";
import { AlertTriangle, X } from "lucide-react";

export default function SecurityBanner() {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(false);

  if (typeof window === "undefined" || isSecureContext() || dismissed) return null;

  return (
    <div className="w-full bg-yellow/15 border-b border-yellow/30 px-4 py-2 flex items-center justify-center gap-2 text-sm text-yellow">
      <AlertTriangle size={16} className="shrink-0" />
      <span>{t("security.httpWarning")}</span>
      <button
        onClick={() => setDismissed(true)}
        className="ml-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-full hover:bg-yellow/15 transition-colors focus-ring"
        aria-label={t("security.dismiss")}
        title={t("security.dismiss")}
      >
        <X size={16} />
      </button>
    </div>
  );
}
