import io
import queue
import threading
import sounddevice as sd
import soundfile as sf
import numpy as np

class AudioRecorder:
    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self.recording = False
        self.q = queue.Queue()
        self.stream = None
        self.frames = []

    def _callback(self, indata, frames, time, status):
        if self.recording:
            self.q.put(indata.copy())

    def start(self):
        """Starts recording audio from default microphone."""
        self.frames = []
        while not self.q.empty():
            self.q.get_nowait()

        self.recording = True
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype='int16',
            callback=self._callback
        )
        self.stream.start()

    def stop(self) -> bytes:
        """Stops recording and returns WAV file bytes."""
        self.recording = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        # Gather all buffered frames
        while not self.q.empty():
            self.frames.append(self.q.get_nowait())

        if not self.frames:
            return b""

        audio_data = np.concatenate(self.frames, axis=0)

        # Write to in-memory WAV buffer
        buf = io.BytesIO()
        sf.write(buf, audio_data, self.samplerate, format='WAV', subtype='PCM_16')
        return buf.getvalue()
