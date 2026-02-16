"use client";

import { useCallback, useEffect } from "react";
import { useRecorderStore } from "@/stores/useRecorderStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { uploadAudio } from "@/lib/api";

// Module-level singleton — shared across all hook instances.
// The mic is acquired on-demand per recording and released immediately after.
let sharedRecorder: MediaRecorder | null = null;
let sharedStream: MediaStream | null = null;
let sharedChunks: Blob[] = [];

/** Stop all tracks and free the microphone */
function releaseStream() {
  sharedStream?.getTracks().forEach((t) => t.stop());
  sharedStream = null;
  sharedRecorder = null;
}

/** Detect best supported audio mimeType */
function detectMimeType() {
  if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus"))
    return "audio/webm;codecs=opus";
  if (MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
  if (MediaRecorder.isTypeSupported("audio/mp4")) return "audio/mp4";
  return "";
}

/**
 * Lazy-acquisition audio recorder.
 * The microphone is requested only when the user starts recording
 * and released immediately after each recording ends, so the mic
 * stays free for other applications between recordings.
 */
export function useAudioRecorder() {
  const isRecording = useRecorderStore((s) => s.isRecording);
  const setIsRecording = useRecorderStore((s) => s.setIsRecording);

  /**
   * Acquire mic, create MediaRecorder and start recording.
   * Returns immediately if already recording or agent is busy.
   */
  const startRecording = useCallback(async () => {
    const agentStore = useAgentStore.getState();
    const agent = agentStore.getActiveAgent();
    if (
      useRecorderStore.getState().isRecording ||
      agent?.isProcessing ||
      !agent?.cwd
    )
      return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      sharedStream = stream;

      const mimeType = detectMimeType();
      const options = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, options);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) sharedChunks.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(sharedChunks, { type: recorder.mimeType });
        sharedChunks = [];

        // Release mic immediately after recording ends
        releaseStream();

        if (blob.size < 3000) {
          useConnectionStore.getState().setStatusText("Recording too short");
          return;
        }

        await sendAudio(blob);
      };

      sharedRecorder = recorder;
      sharedChunks = [];
      recorder.start(100);
      setIsRecording(true);
    } catch (err) {
      console.error("Mic access error:", err);
      releaseStream();
      useConnectionStore.getState().setStatusText("Microphone access denied");
    }
  }, [setIsRecording]);

  /** Stop current recording (triggers onstop → releaseStream) */
  const stopRecording = useCallback(() => {
    if (
      !useRecorderStore.getState().isRecording ||
      !sharedRecorder ||
      sharedRecorder.state === "inactive"
    )
      return;

    sharedRecorder.stop();
    setIsRecording(false);
  }, [setIsRecording]);

  // ── Auto-release on visibility loss / blur ──────────────────────
  useEffect(() => {
    const abort = () => {
      if (!useRecorderStore.getState().isRecording) return;
      if (sharedRecorder && sharedRecorder.state !== "inactive") {
        sharedRecorder.stop();
      }
      useRecorderStore.getState().setIsRecording(false);
      // releaseStream is called inside recorder.onstop
    };

    const onVisChange = () => {
      if (document.hidden) abort();
    };

    document.addEventListener("visibilitychange", onVisChange);
    window.addEventListener("blur", abort);

    return () => {
      document.removeEventListener("visibilitychange", onVisChange);
      window.removeEventListener("blur", abort);
      releaseStream();
    };
  }, []);

  return { startRecording, stopRecording, isRecording };
}

// ── Helper: upload transcribed audio ──────────────────────────────
async function sendAudio(blob: Blob) {
  const agentStore = useAgentStore.getState();
  const connStore = useConnectionStore.getState();
  const agent = agentStore.getActiveAgent();

  if (!agent || !agent.cwd) {
    connStore.setStatusText("Select a project directory first");
    return;
  }

  connStore.setStatusText("Transcribing...");

  try {
    const data = await uploadAudio(blob, connStore.authToken);

    if (data.text && data.text.trim()) {
      const activeId = agentStore.activeAgentId!;
      agentStore.appendMessage(activeId, {
        id: crypto.randomUUID(),
        type: "user",
        text: data.text.trim(),
        timestamp: Date.now(),
        animate: true,
      });

      const sent = connStore.send({
        type: "send_message",
        text: data.text.trim(),
        agent_id: activeId,
      });

      if (sent) {
        agentStore.setProcessing(activeId, true);
        agentStore.setAgentStatus(activeId, "working");
      } else {
        agentStore.appendMessage(activeId, {
          id: crypto.randomUUID(),
          type: "system",
          text: "Could not send — connection lost.",
          timestamp: Date.now(),
          animate: true,
        });
      }
    } else {
      connStore.setStatusText("No speech detected");
    }
  } catch {
    connStore.setStatusText("Transcription failed");
  }
}
