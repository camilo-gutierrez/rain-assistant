import { describe, it, expect, beforeEach } from "vitest";
import { useRecorderStore } from "@/stores/useRecorderStore";

beforeEach(() => {
  useRecorderStore.setState({
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
  });
});

describe("useRecorderStore", () => {
  describe("initial state", () => {
    it("starts with no recorder and not recording", () => {
      const state = useRecorderStore.getState();
      expect(state.mediaRecorder).toBeNull();
      expect(state.audioChunks).toEqual([]);
      expect(state.isRecording).toBe(false);
    });
  });

  describe("setIsRecording()", () => {
    it("sets recording state", () => {
      useRecorderStore.getState().setIsRecording(true);
      expect(useRecorderStore.getState().isRecording).toBe(true);

      useRecorderStore.getState().setIsRecording(false);
      expect(useRecorderStore.getState().isRecording).toBe(false);
    });
  });

  describe("addAudioChunk()", () => {
    it("adds audio chunks to the array", () => {
      const chunk1 = new Blob(["chunk1"], { type: "audio/webm" });
      const chunk2 = new Blob(["chunk2"], { type: "audio/webm" });

      useRecorderStore.getState().addAudioChunk(chunk1);
      expect(useRecorderStore.getState().audioChunks).toHaveLength(1);

      useRecorderStore.getState().addAudioChunk(chunk2);
      expect(useRecorderStore.getState().audioChunks).toHaveLength(2);
    });
  });

  describe("clearAudioChunks()", () => {
    it("clears all audio chunks", () => {
      const chunk = new Blob(["data"], { type: "audio/webm" });
      useRecorderStore.getState().addAudioChunk(chunk);
      useRecorderStore.getState().addAudioChunk(chunk);
      expect(useRecorderStore.getState().audioChunks).toHaveLength(2);

      useRecorderStore.getState().clearAudioChunks();
      expect(useRecorderStore.getState().audioChunks).toEqual([]);
    });
  });

  describe("setMediaRecorder()", () => {
    it("stores and clears a media recorder", () => {
      const mockRecorder = {} as MediaRecorder;
      useRecorderStore.getState().setMediaRecorder(mockRecorder);
      expect(useRecorderStore.getState().mediaRecorder).toBe(mockRecorder);

      useRecorderStore.getState().setMediaRecorder(null);
      expect(useRecorderStore.getState().mediaRecorder).toBeNull();
    });
  });
});
