import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import platform

from recorder import AudioRecorder, list_input_devices
from transcriber import Transcriber
import claude_client

# Cross-platform font selection
_os = platform.system()
if _os == "Darwin":
    _FONT_UI = "Helvetica Neue"
    _FONT_MONO = "Menlo"
elif _os == "Windows":
    _FONT_UI = "Segoe UI"
    _FONT_MONO = "Consolas"
else:
    _FONT_UI = "DejaVu Sans"
    _FONT_MONO = "DejaVu Sans Mono"


class RainAssistantApp:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber(model_size="base", language="es")
        self._model_loaded = False
        self._processing = False

        self.root = tk.Tk()
        self.root.title("Rain Assistant")
        self.root.geometry("700x650")
        self.root.configure(bg="#1e1e2e")
        self.root.minsize(500, 450)

        self._input_devices = list_input_devices()

        self._build_ui()

    def _build_ui(self):
        # Title
        title = tk.Label(
            self.root,
            text="Rain Assistant",
            font=(_FONT_UI, 18, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        title.pack(pady=(15, 5))

        # Status label
        self.status_var = tk.StringVar(value="Listo. Presiona el boton para hablar.")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=(_FONT_UI, 10),
            fg="#a6adc8",
            bg="#1e1e2e",
        )
        self.status_label.pack(pady=(0, 5))

        # Microphone selector
        mic_frame = tk.Frame(self.root, bg="#1e1e2e")
        mic_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        mic_label = tk.Label(
            mic_frame,
            text="Microfono:",
            font=(_FONT_UI, 10),
            fg="#a6adc8",
            bg="#1e1e2e",
        )
        mic_label.pack(side=tk.LEFT, padx=(0, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Mic.TCombobox",
            fieldbackground="#313244",
            background="#313244",
            foreground="#cdd6f4",
            arrowcolor="#cdd6f4",
        )

        device_names = [f"{name}" for _, name in self._input_devices]
        self.mic_var = tk.StringVar()
        self.mic_combo = ttk.Combobox(
            mic_frame,
            textvariable=self.mic_var,
            values=device_names,
            state="readonly",
            style="Mic.TCombobox",
            font=(_FONT_UI, 9),
        )
        self.mic_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if device_names:
            self.mic_combo.current(0)
            self._on_mic_change(None)

        self.mic_combo.bind("<<ComboboxSelected>>", self._on_mic_change)

        # Chat area
        chat_frame = tk.Frame(self.root, bg="#1e1e2e")
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        self.chat_area = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=(_FONT_MONO, 11),
            bg="#181825",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            relief=tk.FLAT,
            padx=12,
            pady=12,
            state=tk.DISABLED,
            cursor="arrow",
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for styling
        self.chat_area.tag_configure(
            "user_name", foreground="#89b4fa", font=(_FONT_UI, 11, "bold")
        )
        self.chat_area.tag_configure(
            "claude_name", foreground="#a6e3a1", font=(_FONT_UI, 11, "bold")
        )
        self.chat_area.tag_configure(
            "user_msg", foreground="#cdd6f4", font=(_FONT_MONO, 11)
        )
        self.chat_area.tag_configure(
            "claude_msg", foreground="#bac2de", font=(_FONT_MONO, 11)
        )
        self.chat_area.tag_configure(
            "system_msg",
            foreground="#6c7086",
            font=(_FONT_UI, 10, "italic"),
        )

        # Bottom controls
        controls_frame = tk.Frame(self.root, bg="#1e1e2e")
        controls_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.record_btn = tk.Button(
            controls_frame,
            text="Mantener para hablar",
            font=(_FONT_UI, 12, "bold"),
            bg="#89b4fa",
            fg="#1e1e2e",
            activebackground="#74c7ec",
            activeforeground="#1e1e2e",
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=10,
        )
        self.record_btn.pack(fill=tk.X)

        # Bind press/release for push-to-talk
        self.record_btn.bind("<ButtonPress-1>", self._on_press)
        self.record_btn.bind("<ButtonRelease-1>", self._on_release)

        # Also bind spacebar as push-to-talk
        self.root.bind("<KeyPress-space>", self._on_press)
        self.root.bind("<KeyRelease-space>", self._on_release)

        self._space_pressed = False

    def _on_mic_change(self, event):
        idx = self.mic_combo.current()
        if 0 <= idx < len(self._input_devices):
            device_index = self._input_devices[idx][0]
            self.recorder.set_device(device_index)
            self._set_status(f"Microfono: {self._input_devices[idx][1]}")

    def _append_chat(self, sender, message, sender_tag, msg_tag):
        self.chat_area.configure(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{sender}: ", sender_tag)
        self.chat_area.insert(tk.END, f"{message}\n\n", msg_tag)
        self.chat_area.configure(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def _append_system(self, message):
        self.chat_area.configure(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{message}\n", "system_msg")
        self.chat_area.configure(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def _set_status(self, text):
        self.status_var.set(text)

    def _on_press(self, event=None):
        if self._processing:
            return

        if isinstance(event, tk.Event) and event.keysym == "space":
            if self._space_pressed:
                return
            self._space_pressed = True

        if self.recorder.is_recording:
            return

        try:
            self.recorder.start_recording()
            self.record_btn.configure(bg="#f38ba8", text="Grabando... suelta para enviar")
            self._set_status("Grabando audio...")
        except Exception as e:
            self._set_status(f"Error al grabar: {e}")

    def _on_release(self, event=None):
        if isinstance(event, tk.Event) and event.keysym == "space":
            self._space_pressed = False

        if not self.recorder.is_recording:
            return

        self._processing = True
        self.record_btn.configure(
            bg="#6c7086", text="Procesando...", state=tk.DISABLED
        )
        self._set_status("Deteniendo grabacion...")

        thread = threading.Thread(target=self._process_recording, daemon=True)
        thread.start()

    def _process_recording(self):
        # Stop recording
        audio_path = self.recorder.stop_recording()
        if not audio_path:
            self.root.after(0, self._reset_button)
            self.root.after(
                0,
                self._set_status,
                "No se detecto audio. Manten presionado al menos 1 segundo.",
            )
            return

        # Transcribe
        self.root.after(0, self._set_status, "Transcribiendo con Whisper...")
        if not self._model_loaded:
            self.root.after(
                0,
                self._append_system,
                "Cargando modelo de Whisper (solo la primera vez)...",
            )
        try:
            text = self.transcriber.transcribe(audio_path)
            self._model_loaded = True
        except Exception as e:
            self.root.after(0, self._set_status, f"Error de transcripcion: {e}")
            self.root.after(0, self._reset_button)
            return

        if not text:
            self.root.after(0, self._set_status, "No se reconocio texto.")
            self.root.after(0, self._reset_button)
            return

        # Show user message
        self.root.after(
            0, self._append_chat, "Tu", text, "user_name", "user_msg"
        )
        self.root.after(0, self._set_status, "Claude esta pensando...")

        # Send to Claude
        try:
            response = claude_client.send_message(text)
        except Exception as e:
            response = f"[Error]: {e}"

        # Show Claude response
        self.root.after(
            0, self._append_chat, "Claude", response, "claude_name", "claude_msg"
        )
        self.root.after(0, self._set_status, "Listo. Presiona el boton para hablar.")
        self.root.after(0, self._reset_button)

    def _reset_button(self):
        self._processing = False
        self.record_btn.configure(
            bg="#89b4fa",
            text="Mantener para hablar",
            state=tk.NORMAL,
        )

    def run(self):
        self._append_system(
            "Bienvenido a Rain Assistant. Selecciona tu microfono arriba "
            "y manten presionado el boton (o barra espaciadora) para hablar."
        )
        self.root.mainloop()


if __name__ == "__main__":
    app = RainAssistantApp()
    app.run()
