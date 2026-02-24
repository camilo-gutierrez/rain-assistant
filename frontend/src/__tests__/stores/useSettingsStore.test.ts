import { describe, it, expect, beforeEach } from "vitest";
import { useSettingsStore } from "@/stores/useSettingsStore";

beforeEach(() => {
  useSettingsStore.setState({
    theme: "light",
    language: "es",
    voiceLang: "es",
    ttsEnabled: false,
    ttsAutoPlay: false,
    ttsVoice: "es-MX-DaliaNeural",
    aiProvider: "claude",
    aiModel: "auto",
    activeEgoId: "rain",
    voiceMode: "push-to-talk",
    vadSensitivity: 0.5,
    silenceTimeout: 800,
    providerKeys: {},
  });
});

describe("useSettingsStore", () => {
  describe("initial state", () => {
    it("starts with Spanish language and light theme", () => {
      const state = useSettingsStore.getState();
      expect(state.language).toBe("es");
      expect(state.theme).toBe("light");
      expect(state.aiProvider).toBe("claude");
      expect(state.aiModel).toBe("auto");
      expect(state.activeEgoId).toBe("rain");
    });
  });

  describe("setTheme()", () => {
    it("changes the theme", () => {
      useSettingsStore.getState().setTheme("dark");
      expect(useSettingsStore.getState().theme).toBe("dark");
    });
  });

  describe("setLanguage()", () => {
    it("changes the language", () => {
      useSettingsStore.getState().setLanguage("en");
      expect(useSettingsStore.getState().language).toBe("en");
    });
  });

  describe("TTS settings", () => {
    it("toggles TTS enabled", () => {
      useSettingsStore.getState().setTtsEnabled(true);
      expect(useSettingsStore.getState().ttsEnabled).toBe(true);
    });

    it("toggles TTS auto-play", () => {
      useSettingsStore.getState().setTtsAutoPlay(true);
      expect(useSettingsStore.getState().ttsAutoPlay).toBe(true);
    });

    it("changes TTS voice", () => {
      useSettingsStore.getState().setTtsVoice("en-US-GuyNeural");
      expect(useSettingsStore.getState().ttsVoice).toBe("en-US-GuyNeural");
    });
  });

  describe("AI provider settings", () => {
    it("changes AI provider", () => {
      useSettingsStore.getState().setAIProvider("openai");
      expect(useSettingsStore.getState().aiProvider).toBe("openai");
    });

    it("changes AI model", () => {
      useSettingsStore.getState().setAIModel("gpt-4o");
      expect(useSettingsStore.getState().aiModel).toBe("gpt-4o");
    });
  });

  describe("provider keys (memory-only)", () => {
    it("stores a provider key", () => {
      useSettingsStore.getState().setProviderKey("openai", "sk-test-key");
      expect(useSettingsStore.getState().getProviderKey("openai")).toBe("sk-test-key");
    });

    it("clears a provider key", () => {
      useSettingsStore.getState().setProviderKey("openai", "sk-test-key");
      useSettingsStore.getState().clearProviderKey("openai");
      expect(useSettingsStore.getState().getProviderKey("openai")).toBeNull();
    });

    it("returns null for unset provider keys", () => {
      expect(useSettingsStore.getState().getProviderKey("gemini")).toBeNull();
    });

    it("does not persist providerKeys to storage", () => {
      useSettingsStore.getState().setProviderKey("claude", "secret-key");
      const stored = localStorage.getItem("rain-settings");
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.providerKeys).toBeUndefined();
      }
    });
  });

  describe("voice settings", () => {
    it("changes voice mode", () => {
      useSettingsStore.getState().setVoiceMode("vad");
      expect(useSettingsStore.getState().voiceMode).toBe("vad");
    });

    it("changes VAD sensitivity", () => {
      useSettingsStore.getState().setVadSensitivity(0.8);
      expect(useSettingsStore.getState().vadSensitivity).toBe(0.8);
    });

    it("changes silence timeout", () => {
      useSettingsStore.getState().setSilenceTimeout(1200);
      expect(useSettingsStore.getState().silenceTimeout).toBe(1200);
    });
  });

  describe("alter ego", () => {
    it("changes active ego", () => {
      useSettingsStore.getState().setActiveEgoId("custom-ego");
      expect(useSettingsStore.getState().activeEgoId).toBe("custom-ego");
    });
  });
});
