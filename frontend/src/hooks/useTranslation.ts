"use client";

import { useCallback } from "react";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { translate } from "@/lib/translations";

export function useTranslation() {
  const language = useSettingsStore((s) => s.language);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      return translate(language, key, params);
    },
    [language]
  );

  return { t, language };
}
