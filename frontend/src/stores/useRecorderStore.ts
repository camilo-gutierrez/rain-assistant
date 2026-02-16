import { create } from "zustand";

interface RecorderState {
  mediaRecorder: MediaRecorder | null;
  audioChunks: Blob[];
  isRecording: boolean;

  setMediaRecorder: (recorder: MediaRecorder | null) => void;
  addAudioChunk: (chunk: Blob) => void;
  clearAudioChunks: () => void;
  setIsRecording: (val: boolean) => void;
}

export const useRecorderStore = create<RecorderState>()((set) => ({
  mediaRecorder: null,
  audioChunks: [],
  isRecording: false,

  setMediaRecorder: (mediaRecorder) => set({ mediaRecorder }),
  addAudioChunk: (chunk) =>
    set((state) => ({ audioChunks: [...state.audioChunks, chunk] })),
  clearAudioChunks: () => set({ audioChunks: [] }),
  setIsRecording: (isRecording) => set({ isRecording }),
}));
