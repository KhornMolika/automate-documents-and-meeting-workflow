import collections
import logging

logger = logging.getLogger(__name__)


class WebRTCVoiceActivityDetector:
    """
    Applies WebRTC VAD to audio frames to prune silence and background noise.
    """
    def __init__(self, mode: int = 2, sample_rate: int = 16000, frame_duration_ms: int = 30):
        self.mode = mode
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000) * 2  # 16-bit PCM = 2 bytes/sample
        self._vad = None
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(mode)
        except ImportError:
            logger.warning("webrtcvad not installed, passing through all audio frames without pruning.")

    def is_speech(self, frame_bytes: bytes) -> bool:
        if not self._vad:
            return True
        try:
            return self._vad.is_speech(frame_bytes, self.sample_rate)
        except Exception:
            return True

    def filter_silence(self, pcm_bytes: bytes) -> bytes:
        """
        Splits PCM bytes into frames and discards silence.

        If the chunk contains almost no speech, return empty bytes so the ASR
        models never see noise (Whisper can hallucinate text on noise).
        """
        if not self._vad:
            return pcm_bytes

        speech_frames = []
        for i in range(0, len(pcm_bytes) - self.frame_size + 1, self.frame_size):
            frame = pcm_bytes[i:i + self.frame_size]
            if self.is_speech(frame):
                speech_frames.append(frame)

        total_frames = len(pcm_bytes) // self.frame_size
        minimum_frames = max(2, int(total_frames * 0.15))
        if len(speech_frames) < minimum_frames:
            return b""
        return b"".join(speech_frames)
