import sounddevice as sd
import numpy as np
import wave
import tempfile
import threading
import os


def list_input_devices():
    """Return a list of (index, name) for available input devices."""
    devices = sd.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            name = dev["name"]
            input_devices.append((i, name))
    return input_devices


class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1, device_index=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self._recording = False
        self._frames = []
        self._lock = threading.Lock()
        self._stream = None

    @property
    def is_recording(self):
        return self._recording

    def set_device(self, device_index):
        self.device_index = device_index

    def _audio_callback(self, indata, frames, time_info, status):
        if self._recording:
            with self._lock:
                self._frames.append(indata.copy())

    def start_recording(self):
        if self._recording:
            return
        with self._lock:
            self._frames = []
        self._recording = True
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device_index,
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
        except Exception as e:
            self._recording = False
            raise e

    def stop_recording(self):
        if not self._recording:
            return None
        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._frames:
                return None
            audio_data = np.concatenate(self._frames, axis=0)

        if len(audio_data) < self.sample_rate * 0.3:
            return None

        temp_dir = tempfile.gettempdir()
        audio_path = os.path.join(temp_dir, "rain_recording.wav")

        with wave.open(audio_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())

        return audio_path
