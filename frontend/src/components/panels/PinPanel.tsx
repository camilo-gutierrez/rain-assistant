"use client";

import { useState, useRef, useEffect } from "react";
import { authenticate } from "@/lib/api";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";

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

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Lockout countdown
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
        className="w-full max-w-[420px] flex flex-col items-center gap-6 p-8 bg-surface rounded-2xl border border-overlay"
      >
        {/* Title */}
        <h2
          className="font-[family-name:var(--font-orbitron)] text-2xl font-bold bg-clip-text text-transparent"
          style={{
            backgroundImage: "linear-gradient(135deg, var(--cyan), var(--magenta))",
          }}
        >
          {t("pin.title")}
        </h2>

        {/* Instruction */}
        <p className="text-sm text-text2 text-center">
          {t("pin.instruction")}
        </p>

        {/* PIN input */}
        <input
          ref={inputRef}
          type="password"
          maxLength={6}
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="------"
          disabled={lockoutTime > 0}
          className="w-48 text-center text-2xl tracking-[0.5em] font-[family-name:var(--font-jetbrains)] bg-surface2 border border-overlay rounded-lg px-4 py-3 text-text placeholder:text-subtext focus:outline-none focus:border-cyan focus:shadow-[0_0_12px_var(--neon-glow)] transition-all disabled:opacity-50"
        />

        {/* Error message */}
        {error && (
          <p className="text-sm text-red text-center">{error}</p>
        )}

        {/* Lockout timer */}
        {lockoutTime > 0 && (
          <p className="text-xs text-yellow font-[family-name:var(--font-jetbrains)]">
            {lockoutTime}s
          </p>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={!pin.trim() || submitting || lockoutTime > 0}
          className="w-full py-3 rounded-lg font-[family-name:var(--font-orbitron)] text-sm font-bold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-[0_0_20px_var(--neon-glow)]"
          style={{
            background: "linear-gradient(135deg, var(--cyan), var(--mauve))",
          }}
        >
          {submitting ? "..." : t("pin.submit")}
        </button>
      </form>
    </div>
  );
}
