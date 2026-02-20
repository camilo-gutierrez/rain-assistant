/**
 * Voice message handler — routes voice-related WS messages.
 *
 * Follows the same pattern as useToolMessages.ts, usePermissionMessages.ts, etc.
 * Called from useWebSocket's main message router.
 */

import { useVoiceModeStore } from "@/hooks/useVoiceMode";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import type { WSReceiveMessage } from "@/lib/types";

const VOICE_TYPES = new Set([
  "vad_event",
  "wake_word_detected",
  "talk_state_changed",
  "voice_transcription",
  "partial_transcription",
  "voice_mode_changed",
]);

export function handleVoiceMessage(
  msg: WSReceiveMessage,
  agentId: string
): boolean {
  if (!VOICE_TYPES.has(msg.type)) return false;

  const store = useVoiceModeStore.getState();

  switch (msg.type) {
    case "vad_event": {
      const event = msg.event;
      if (event === "speech_start") {
        store.setVoiceState("recording");
      } else if (event === "speech_end") {
        store.setVoiceState("transcribing");
      } else if (event === "no_speech") {
        store.setVoiceState("listening");
      }
      return true;
    }

    case "wake_word_detected":
      store.setWakeWordConfidence(msg.confidence);
      store.setVoiceState("listening");
      return true;

    case "talk_state_changed":
      store.setVoiceState(msg.state);
      return true;

    case "voice_transcription": {
      if (msg.is_final && msg.text) {
        store.setLastTranscription(msg.text);
        store.setPartialTranscription("");

        // Auto-send as user message
        const agentStore = useAgentStore.getState();
        agentStore.appendMessage(agentId, {
          id: `voice-${Date.now()}`,
          type: "user",
          text: msg.text,
          timestamp: Date.now(),
          animate: false,
        });
        useConnectionStore.getState().send({
          type: "send_message",
          text: msg.text,
          agent_id: agentId,
        });
        agentStore.setAgentStatus(agentId, "working");
        store.setVoiceState("processing");
      }
      return true;
    }

    case "partial_transcription":
      store.setPartialTranscription(msg.text);
      if (msg.is_final) {
        store.setLastTranscription(msg.text);
        store.setPartialTranscription("");
      }
      return true;

    case "voice_mode_changed":
      return true;

    default:
      return false;
  }
}
