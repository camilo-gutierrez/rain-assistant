"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { authenticate, fetchDevicesWithPin, revokeDeviceWithPin, revokeAllWithPin } from "@/lib/api";
import { getDeviceId, getDeviceName } from "@/lib/device";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useUIStore } from "@/stores/useUIStore";
import { useTranslation } from "@/hooks/useTranslation";
import { Lock, AlertTriangle, Timer, Monitor, Smartphone, ArrowLeftRight, Trash2, X } from "lucide-react";
import type { DeviceInfo } from "@/lib/types";

function formatTime(ts: number, t: (key: string) => string): string {
  const d = new Date(ts * 1000);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return t("devices.justNow");
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`;
}

export default function PinPanel() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [lockoutTime, setLockoutTime] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Device replacement flow
  const [pendingPin, setPendingPin] = useState<string | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [maxDevices, setMaxDevices] = useState(2);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [confirmDevice, setConfirmDevice] = useState<DeviceInfo | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<DeviceInfo | null>(null);
  const [confirmRevokeAll, setConfirmRevokeAll] = useState(false);

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

  const completeLogin = useCallback((token: string) => {
    setAuthToken(token);
    setActivePanel("apiKey");
    connect();
  }, [setAuthToken, setActivePanel, connect]);

  const showDeviceSheet = useCallback(async (savedPin: string) => {
    setLoadingDevices(true);
    const result = await fetchDevicesWithPin(savedPin);
    setLoadingDevices(false);

    if (!result) {
      setError(t("devices.loadError"));
      setPendingPin(null);
      inputRef.current?.focus();
      return;
    }

    setDevices(result.devices);
    setMaxDevices(result.max_devices);
    setPendingPin(savedPin);
  }, [t]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim() || submitting || lockoutTime > 0) return;

    setSubmitting(true);
    setError("");

    try {
      const deviceId = getDeviceId();
      const deviceName = getDeviceName();
      const res = await authenticate(pin.trim(), deviceId, deviceName);

      if (res.token) {
        completeLogin(res.token);
      } else if (res.error === "device_limit_reached") {
        const savedPin = pin.trim();
        setPin("");
        await showDeviceSheet(savedPin);
      } else if (res.locked && res.remaining_seconds) {
        setLockoutTime(res.remaining_seconds);
        setError(t("pin.tooManyAttempts", { time: `${res.remaining_seconds}s` }));
        setPin("");
      } else if (res.remaining_attempts !== undefined) {
        if (res.remaining_attempts === 1) {
          setError(t("pin.incorrectRemainingOne"));
        } else {
          setError(t("pin.incorrectRemaining", { n: res.remaining_attempts }));
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
      if (!pendingPin) inputRef.current?.focus();
    }
  };

  const handleReplace = async (deviceId: string) => {
    if (!pendingPin) return;
    setSubmitting(true);
    setConfirmDevice(null);
    setError("");

    try {
      const res = await authenticate(
        pendingPin,
        getDeviceId(),
        getDeviceName(),
        deviceId,
      );
      if (res.token) {
        setPendingPin(null);
        completeLogin(res.token);
      } else {
        setError(res.error || t("pin.error"));
        setPendingPin(null);
      }
    } catch {
      setError(t("status.connectionError"));
      setPendingPin(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevokeAll = async () => {
    if (!pendingPin) return;
    setSubmitting(true);
    setConfirmRevokeAll(false);
    setError("");

    try {
      const ok = await revokeAllWithPin(pendingPin);
      if (!ok) {
        setError(t("devices.revokeAllError"));
        setSubmitting(false);
        return;
      }
      // Now authenticate fresh
      const res = await authenticate(
        pendingPin,
        getDeviceId(),
        getDeviceName(),
      );
      if (res.token) {
        setPendingPin(null);
        completeLogin(res.token);
      } else {
        setError(res.error || t("pin.error"));
        setPendingPin(null);
      }
    } catch {
      setError(t("status.connectionError"));
      setPendingPin(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteDevice = async (deviceId: string) => {
    if (!pendingPin) return;
    setSubmitting(true);
    setConfirmDelete(null);
    setError("");

    try {
      const ok = await revokeDeviceWithPin(pendingPin, deviceId);
      if (!ok) {
        setError(t("devices.revokeAllError"));
        setSubmitting(false);
        return;
      }
      const remaining = devices.filter((d) => d.device_id !== deviceId);
      setDevices(remaining);

      // If now under limit, auto-login
      if (remaining.length < maxDevices) {
        const res = await authenticate(
          pendingPin,
          getDeviceId(),
          getDeviceName(),
        );
        if (res.token) {
          setPendingPin(null);
          completeLogin(res.token);
        } else {
          setSubmitting(false);
        }
      } else {
        setSubmitting(false);
      }
    } catch {
      setError(t("status.connectionError"));
      setSubmitting(false);
    }
  };

  const cancelDeviceFlow = () => {
    setPendingPin(null);
    setDevices([]);
    setConfirmDevice(null);
    setConfirmDelete(null);
    setConfirmRevokeAll(false);
    setError("");
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  // === Device replacement modal ===
  if (pendingPin && !loadingDevices) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-[480px] flex flex-col bg-surface rounded-xl shadow-lg overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 pt-6 pb-2">
            <div className="flex items-center gap-3">
              <Monitor className="w-6 h-6 text-primary" />
              <h2 className="text-lg font-bold text-text">
                {t("devices.replaceTitle")}
              </h2>
            </div>
            <button
              onClick={cancelDeviceFlow}
              className="p-1.5 rounded-lg hover:bg-surface2 transition-colors"
            >
              <X className="w-5 h-5 text-subtext" />
            </button>
          </div>

          <p className="px-6 pb-4 text-sm text-text2">
            {t("devices.replaceSubtitle", { max: maxDevices })}
          </p>

          {error && (
            <div className="mx-6 mb-3 flex items-center gap-2.5 px-3.5 py-3 rounded-xl bg-red/10 border border-red/30">
              <AlertTriangle className="w-[18px] h-[18px] shrink-0 text-red" />
              <p className="text-sm text-red">{error}</p>
            </div>
          )}

          {/* Device list */}
          <div className="flex-1 overflow-y-auto max-h-[320px] px-3">
            {devices.map((device) => {
              const isMobile = /mobile|android|iphone|telegram/i.test(device.device_name);
              return (
                <div
                  key={device.device_id}
                  className="flex items-center gap-3 px-3 py-3 mx-1 mb-1 rounded-lg hover:bg-surface2 transition-colors"
                >
                  <div className="w-9 h-9 rounded-full bg-overlay/30 flex items-center justify-center shrink-0">
                    {isMobile
                      ? <Smartphone className="w-[18px] h-[18px] text-primary" />
                      : <Monitor className="w-[18px] h-[18px] text-primary" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {device.device_name || "Unknown"}
                    </p>
                    <p className="text-xs text-subtext truncate">
                      {device.client_ip} · {t("devices.lastActive")} {formatTime(device.last_activity, t)}
                    </p>
                  </div>
                  <button
                    onClick={() => setConfirmDelete(device)}
                    disabled={submitting}
                    className="shrink-0 p-1.5 rounded-lg text-red hover:bg-red/10 transition-colors disabled:opacity-40"
                    title={t("devices.revoke")}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setConfirmDevice(device)}
                    disabled={submitting}
                    className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-40"
                  >
                    <ArrowLeftRight className="w-3.5 h-3.5" />
                    {t("devices.replace")}
                  </button>
                </div>
              );
            })}
          </div>

          {/* Actions */}
          <div className="px-6 py-4 flex flex-col gap-2 border-t border-overlay/30">
            <button
              onClick={() => setConfirmRevokeAll(true)}
              disabled={submitting}
              className="w-full min-h-[44px] py-3 rounded-lg text-sm font-semibold bg-red text-on-primary transition-all hover:opacity-90 shadow-sm focus-ring flex items-center justify-center gap-2 disabled:opacity-40"
            >
              <Trash2 className="w-4 h-4" />
              {t("devices.revokeAll")}
            </button>
            <button
              onClick={cancelDeviceFlow}
              disabled={submitting}
              className="w-full min-h-[40px] py-2.5 rounded-lg text-sm font-medium text-text2 border border-overlay hover:bg-surface2 transition-colors disabled:opacity-40"
            >
              {t("pin.cancel")}
            </button>
          </div>

          {/* Confirm delete single device */}
          {confirmDelete && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
              <div className="w-full max-w-[380px] bg-surface rounded-xl p-6 shadow-xl flex flex-col gap-4">
                <div className="flex items-center gap-3">
                  <Trash2 className="w-6 h-6 text-red" />
                  <h3 className="text-base font-bold text-text">
                    {t("devices.revoke")}
                  </h3>
                </div>
                <p className="text-sm text-text2">
                  {t("devices.revokeConfirm")}
                </p>
                <p className="text-sm font-medium text-text">
                  {confirmDelete.device_name || "Unknown"} — {confirmDelete.client_ip}
                </p>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setConfirmDelete(null)}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-text2 border border-overlay hover:bg-surface2 transition-colors"
                  >
                    {t("pin.cancel")}
                  </button>
                  <button
                    onClick={() => handleDeleteDevice(confirmDelete.device_id)}
                    className="px-4 py-2 rounded-lg text-sm font-semibold bg-red text-on-primary hover:opacity-90 transition-all"
                  >
                    {t("devices.revoke")}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Confirm replace single device */}
          {confirmDevice && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
              <div className="w-full max-w-[380px] bg-surface rounded-xl p-6 shadow-xl flex flex-col gap-4">
                <div className="flex items-center gap-3">
                  <ArrowLeftRight className="w-6 h-6 text-red" />
                  <h3 className="text-base font-bold text-text">
                    {t("devices.replaceConfirmTitle")}
                  </h3>
                </div>
                <p className="text-sm text-text2">
                  {t("devices.replaceConfirmBody", {
                    name: confirmDevice.device_name || "Unknown",
                  })}
                </p>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setConfirmDevice(null)}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-text2 border border-overlay hover:bg-surface2 transition-colors"
                  >
                    {t("pin.cancel")}
                  </button>
                  <button
                    onClick={() => handleReplace(confirmDevice.device_id)}
                    className="px-4 py-2 rounded-lg text-sm font-semibold bg-red text-on-primary hover:opacity-90 transition-all"
                  >
                    {t("devices.replace")}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Confirm revoke all */}
          {confirmRevokeAll && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
              <div className="w-full max-w-[380px] bg-surface rounded-xl p-6 shadow-xl flex flex-col gap-4">
                <div className="flex items-center gap-3">
                  <Trash2 className="w-6 h-6 text-red" />
                  <h3 className="text-base font-bold text-text">
                    {t("devices.revokeAllConfirmTitle")}
                  </h3>
                </div>
                <p className="text-sm text-text2">
                  {t("devices.revokeAllConfirmBody")}
                </p>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setConfirmRevokeAll(false)}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-text2 border border-overlay hover:bg-surface2 transition-colors"
                  >
                    {t("pin.cancel")}
                  </button>
                  <button
                    onClick={handleRevokeAll}
                    className="px-4 py-2 rounded-lg text-sm font-semibold bg-red text-on-primary hover:opacity-90 transition-all"
                  >
                    {t("devices.revokeAll")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // === Standard PIN form ===
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
          maxLength={20}
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="------"
          disabled={lockoutTime > 0 || loadingDevices}
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
          disabled={!pin.trim() || submitting || lockoutTime > 0 || loadingDevices}
          className="w-full min-h-[44px] py-3 rounded-lg text-sm font-semibold bg-primary text-on-primary transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-dark shadow-sm focus-ring"
        >
          {submitting || loadingDevices ? "..." : t("pin.submit")}
        </button>
      </form>
    </div>
  );
}
