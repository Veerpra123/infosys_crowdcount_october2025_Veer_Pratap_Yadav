# services/video_stream.py
import os
import time
import cv2
import threading
import queue
from typing import Union, Optional

class VideoStream:
    """
    Minimal, robust frame grabber with a single latest-frame queue.

    Public API (unchanged):
      - VideoStream(src).start()
      - .read()  -> numpy frame (BGR)
      - .stop()

    Enhancements:
      - Loops video files automatically when reaching EOF
      - Optional target width/height (ENV or args)
      - Backoff sleep when capture fails
      - Safe queue handling to avoid memory growth
    """

    def __init__(
        self,
        src: Union[int, str] = 0,
        *,
        loop_video: bool = True,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ):
        # Allow env overrides (useful in Docker/production)
        env_w = os.getenv("STREAM_WIDTH")
        env_h = os.getenv("STREAM_HEIGHT")
        if width is None and env_w and env_w.isdigit():
            width = int(env_w)
        if height is None and env_h and env_h.isdigit():
            height = int(env_h)

        self.src = int(src) if isinstance(src, str) and src.isdigit() else src
        self.loop_video = loop_video
        self.target_width = width
        self.target_height = height

        self.cap: Optional[cv2.VideoCapture] = None
        self.q: "queue.Queue" = queue.Queue(maxsize=1)  # latest frame only
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._last_frame = None  # fallback if queue empty

    # -------- lifecycle --------
    def start(self):
        if self.running:
            return self
        self.running = True
        self._open_capture()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self.running = False
        # join thread quickly (don’t hang app shutdown)
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=0.5)
        except Exception:
            pass
        # release capture
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
        self.cap = None
        # drain queue
        try:
            while not self.q.empty():
                self.q.get_nowait()
        except Exception:
            pass

    # -------- capture helpers --------
    def _open_capture(self):
        self.cap = cv2.VideoCapture(self.src)
        if self.target_width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
        if self.target_height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)

    def _is_video_file(self) -> bool:
        return isinstance(self.src, str) and not self.src.isdigit()

    def _rewind_if_needed(self):
        # For video files, when we hit EOF, rewind to frame 0 to loop.
        if not self._is_video_file() or self.cap is None:
            return
        try:
            total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES) or 0)
            if total > 0 and pos >= total - 1:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        except Exception:
            # If driver doesn't support, just reopen
            self._reopen_capture()

    def _reopen_capture(self):
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
        time.sleep(0.05)
        self._open_capture()

    # -------- main loop --------
    def _loop(self):
        backoff = 0.01
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    self._reopen_capture()
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 0.2)
                    continue

                ok, frame = self.cap.read()
                if not ok or frame is None:
                    # EOF on file? loop if enabled
                    if self.loop_video and self._is_video_file():
                        self._rewind_if_needed()
                        continue
                    # For webcams or transient read failures, brief backoff
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 0.2)
                    continue

                # reset backoff after successful read
                backoff = 0.01

                # keep latest frame only
                if not self.q.empty():
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        pass
                self.q.put_nowait(frame)
                self._last_frame = frame
            except Exception:
                # avoid busy spin on unexpected errors
                time.sleep(0.05)
                continue

    # -------- consumer API --------
    def read(self):
        """
        Blocking read of the latest frame. If nothing is queued momentarily,
        returns the last good frame (if available) to prevent deadlocks.
        """
        try:
            frame = self.q.get(timeout=0.25)
            self._last_frame = frame
            return frame
        except queue.Empty:
            if self._last_frame is not None:
                return self._last_frame
            # As a last resort, try a direct read (non-queued)
            if self.cap is not None and self.cap.isOpened():
                ok, frame = self.cap.read()
                if ok and frame is not None:
                    self._last_frame = frame
                    return frame
            # If still no frame, return a black placeholder (keeps stream alive)
            return _black_frame()

def _black_frame(w: int = 640, h: int = 480):
    """Create a black frame as a last-resort placeholder."""
    import numpy as np
    return np.zeros((h, w, 3), dtype=np.uint8)
