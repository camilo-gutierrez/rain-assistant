"use client";

import { useEffect, useRef, useCallback } from "react";
import { useUIStore } from "@/stores/useUIStore";
import { ORIGINAL_TITLE } from "@/lib/constants";

export function useNotifications() {
  const tabFocused = useUIStore((s) => s.tabFocused);
  const setTabFocused = useUIStore((s) => s.setTabFocused);
  const incrementUnreadCount = useUIStore((s) => s.incrementUnreadCount);
  const unreadCount = useUIStore((s) => s.unreadCount);
  const swRegistrationRef = useRef<ServiceWorkerRegistration | null>(null);
  const enabledRef = useRef(false);
  const iconRef = useRef<string | null>(null);

  // Visibility / focus tracking
  useEffect(() => {
    const onVisChange = () => {
      const focused = !document.hidden;
      setTabFocused(focused);
      if (focused) document.title = ORIGINAL_TITLE;
    };
    const onFocus = () => {
      setTabFocused(true);
      document.title = ORIGINAL_TITLE;
    };
    const onBlur = () => setTabFocused(false);

    document.addEventListener("visibilitychange", onVisChange);
    window.addEventListener("focus", onFocus);
    window.addEventListener("blur", onBlur);

    return () => {
      document.removeEventListener("visibilitychange", onVisChange);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("blur", onBlur);
    };
  }, [setTabFocused]);

  // Request permission on first interaction
  useEffect(() => {
    const requestPermission = async () => {
      if (!("Notification" in window)) return;

      if ("serviceWorker" in navigator) {
        try {
          swRegistrationRef.current = await navigator.serviceWorker.register("/sw.js");
        } catch (e) {
          console.warn("SW registration failed:", e);
        }
      }

      if (Notification.permission === "granted") {
        enabledRef.current = true;
        return;
      }
      if (Notification.permission !== "denied") {
        const perm = await Notification.requestPermission();
        enabledRef.current = perm === "granted";
      }
    };

    const handler = () => {
      requestPermission();
      // Remove after first interaction
      ["click", "keydown", "touchstart"].forEach((evt) =>
        document.removeEventListener(evt, handler)
      );
    };

    ["click", "keydown", "touchstart"].forEach((evt) =>
      document.addEventListener(evt, handler, { once: true })
    );

    return () => {
      ["click", "keydown", "touchstart"].forEach((evt) =>
        document.removeEventListener(evt, handler)
      );
    };
  }, []);

  const generateRainIcon = useCallback(() => {
    if (iconRef.current) return iconRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d")!;
    ctx.beginPath();
    ctx.arc(32, 32, 30, 0, Math.PI * 2);
    ctx.fillStyle = "#0a0a14";
    ctx.fill();
    ctx.strokeStyle = "#00d4ff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "#00d4ff";
    ctx.font = "bold 32px Orbitron, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("R", 32, 34);
    iconRef.current = canvas.toDataURL();
    return iconRef.current;
  }, []);

  const sendNotification = useCallback(
    (title: string, body: string) => {
      if (!enabledRef.current || tabFocused) return;

      incrementUnreadCount();
      document.title = `(${unreadCount + 1}) ${ORIGINAL_TITLE}`;

      const options = {
        body: (body || "").slice(0, 150),
        icon: generateRainIcon(),
        tag: "rain-response",
        renotify: true,
      };

      if (swRegistrationRef.current) {
        swRegistrationRef.current.showNotification(title, options).catch((e) => {
          console.warn("SW notification failed:", e);
        });
        return;
      }

      try {
        const notification = new Notification(title, options);
        notification.onclick = () => {
          window.focus();
          notification.close();
        };
        setTimeout(() => notification.close(), 5000);
      } catch (e) {
        console.warn("Notification failed:", e);
      }
    },
    [tabFocused, unreadCount, incrementUnreadCount, generateRainIcon]
  );

  return { sendNotification };
}
