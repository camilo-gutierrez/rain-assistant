"use client";

import { useRef, useCallback } from "react";
import { useRecorderStore } from "@/stores/useRecorderStore";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { uploadAudio } from "@/lib/api";

export function useAudioRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const isRecording = useRecorderStore((s) => s.isRecording);
  const setIsRecording = useRecorderStore((s) => s.setIsRecording);

  const initAudio = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/mp4")
        ? "audio/mp4"
        : "";

      const options = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, options);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];

        if (blob.size < 3000) {
          const connStore = useConnectionStore.getState();
          connStore.setStatusText("Recording too short");
          setIsRecording(false);
          return;
        }

        await sendAudio(blob);
      };

      recorderRef.current = recorder;
      return true;
    } catch (err) {
      console.error("Audio init error:", err);
      return false;
    }
  }, [setIsRecording]);

  const startRecording = useCallback(() => {
    const agentStore = useAgentStore.getState();
    const agent = agentStore.getActiveAgent();
    if (isRecording || (agent && agent.isProcessing) || !recorderRef.current) return;

    chunksRef.current = [];
    recorderRef.current.start(100);
    setIsRecording(true);
  }, [isRecording, setIsRecording]);

  const stopRecording = useCallback(() => {
    if (!isRecording || !recorderRef.current) return;
    recorderRef.current.stop();
    setIsRecording(false);
  }, [isRecording, setIsRecording]);

  return { initAudio, startRecording, stopRecording, isRecording };
}

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
      // Append user message
      agentStore.appendMessage(activeId, {
        id: crypto.randomUUID(),
        type: "user",
        text: data.text.trim(),
        timestamp: Date.now(),
        animate: true,
      });

      // Send to server
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
