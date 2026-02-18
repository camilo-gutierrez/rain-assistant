"use client";

import { useState, useRef, useEffect } from "react";
import { authenticate } from "@/lib/api";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { Lock, AlertTriangle, Timer } from "lucide-react";

export default function PinPanel() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [lockoutTime, setLockoutTime] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const setAuthToken = useConnectionStore((s) => s.setAuthToken);
  const connect = useConnectionStore((s) => s.connect);
  const setActivePanel = useUIStore((s) => s.setActivePanel);
  const { t } = useTranslation();

  useEffect(() => {
    inputRef.current?.focus();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (lockoutTime <= 0) return;

    timerRef.current = setInterval(() => {
      setLockoutTime((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          setError("");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [lockoutTime]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim() || submitting || lockoutTime > 0) return;

    setSubmitting(true);
    setError("");

    try {
      const res = await authenticate(pin.trim());

      if (res.token) {
        setAuthToken(res.token);
        setActivePanel("apiKey");
        connect();
      } else if (res.locked && res.remaining_seconds) {
        setLockoutTime(res.remaining_seconds);
        setError(t("pin.tooManyAttempts", { time: `${res.remaining_seconds}s` }));
        setPin("");
      } else if (res.remaining_attempts !== undefined) {
        if (res.remaining_attempts === 1) {
          setError(t("pin.incorrectRemainingOne"));
        } else {
          setError(
            t("pin.incorrectRemaining", { n: res.remaining_attempts })
          );
        }
        setPin("");
      } else {
        setError(res.error || t("pin.error"));
        setPin("");
      }
    } catch {
      setError(t("status.connectionError"));
    } finally {
      setSubmitting(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-[420px] flex flex-col items-center gap-6 p-8 bg-surface rounded-xl shadow-lg"
      >
        <h2 className="text-2xl font-bold text-text flex items-center gap-2.5">
          <Lock className="w-6 h-6 text-primary" />
          {t("pin.title")}
        </h2>

        <p className="text-sm text-text2 text-center">
          {t("pin.instruction")}
        </p>

        <input
          ref={inputRef}
          type="password"
          maxLength={6}
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="------"
          disabled={lockoutTime > 0}
          className="w-48 text-center text-2xl tracking-[0.5em] font-[family-name:var(--font-jetbrains)] bg-surface2 border border-overlay rounded-lg px-4 py-3 text-text placeholder:text-subtext focus-ring transition-all disabled:opacity-50"
        />

        {error && (
          <div className="w-full flex items-center gap-2.5 px-3.5 py-3 rounded-xl bg-red/10 border border-red/30">
            <AlertTriangle className="w-[18px] h-[18px] shrink-0 text-red" />
            <p className="text-sm text-red">{error}</p>
          </div>
        )}

        {lockoutTime > 0 && (
          <div className="w-full flex items-center gap-2.5 px-3.5 py-3 rounded-xl bg-yellow/10 border border-yellow/30">
            <Timer className="w-[18px] h-[18px] shrink-0 text-yellow" />
            <p className="text-sm text-yellow font-[family-name:var(--font-jetbrains)]">
              {lockoutTime}s
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={!pin.trim() || submitting || lockoutTime > 0}
          className="w-full min-h-[44px] py-3 rounded-lg text-sm font-semibold bg-primary text-on-primary transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-dark shadow-sm focus-ring"
        >
          {submitting ? "..." : t("pin.submit")}
        </button>
      </form>
    </div>
  );
}
