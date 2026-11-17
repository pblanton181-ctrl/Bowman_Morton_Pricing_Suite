import os
import time
import threading
import numpy as np
import mss
import imageio.v2 as imageio


class WindowVideoRecorder:
    """Thread-safe screen recorder capturing the app window into a crisp H.264 MP4."""

    def __init__(self, target_widget, out_path, fps=16):
        self.target = target_widget
        self.out_path = out_path
        self.fps = fps
        self._running = False
        self._thread = None
        self.frame_count = 0
        self.mon = {"left": 0, "top": 0, "width": 1920, "height": 1080}

    def start(self):
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        geo = self.target.frameGeometry()
        w = max(640, (geo.width() // 16) * 16)
        h = max(480, (geo.height() // 16) * 16)
        self.mon = {"left": max(0, int(geo.x())), "top": max(0, int(geo.y())), "width": int(w), "height": int(h)}
        self._running = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10.0)

    def _open_writer(self):
        for codec_name in ("libx264", "mpeg4"):
            try:
                w = imageio.get_writer(
                    self.out_path,
                    fps=self.fps,
                    codec=codec_name,
                    quality=8,
                    pixelformat="yuv420p",
                    macro_block_size=16,
                )
                print(f"[VIDEO] Recording started ({codec_name} @ {self.fps} FPS) -> {self.out_path}")
                return w
            except Exception as exc:
                print(f"[VIDEO WARN] {codec_name}: {exc}")
        return None

    def _record_loop(self):
        dt = 1.0 / max(1, self.fps)
        writer = self._open_writer()
        if writer is None:
            return
        with mss.MSS() as sct:
            while self._running:
                t0 = time.perf_counter()
                try:
                    raw = sct.grab(self.mon)
                    frame = np.asarray(raw)[:, :, :3][:, :, ::-1]
                    writer.append_data(frame)
                    self.frame_count += 1
                except Exception as exc:
                    print(f"[VIDEO ERR] {exc}")
                    break
                elapsed = time.perf_counter() - t0
                if elapsed < dt:
                    time.sleep(dt - elapsed)
        try:
            writer.close()
        except Exception as exc:
            print(f"[VIDEO ERR] close: {exc}")