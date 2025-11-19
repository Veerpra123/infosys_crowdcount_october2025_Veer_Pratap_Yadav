# services/detector.py
import threading
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import cv2
import numpy as np
from ultralytics import YOLO

# ---------------- Types ----------------
# detection: (x1, y1, x2, y2, conf)
Det = Tuple[int, int, int, int, float]
# track:     (x1, y1, x2, y2, track_id, conf)
Track = Tuple[int, int, int, int, int, float]


# ---------------- Simple IoU Tracker ----------------
class SimpleTracker:
    """
    Tiny greedy IoU tracker:
      - Assigns persistent integer IDs
      - Keeps last box for each active ID
      - Drops stale IDs after `max_age` frames without match
    """
    def __init__(self, iou_thresh: float = 0.35, max_age: int = 12):
        self.iou_thresh = iou_thresh
        self.max_age = max_age
        self.next_id = 1
        # id -> (x1,y1,x2,y2,age)
        self._tracks: Dict[int, Tuple[int, int, int, int, int]] = {}

    @staticmethod
    def _iou(a, b) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def update(self, dets: List[Det]) -> List[Track]:
        # age all tracks
        for tid in list(self._tracks.keys()):
            x1, y1, x2, y2, age = self._tracks[tid]
            self._tracks[tid] = (x1, y1, x2, y2, age + 1)

        used: set[int] = set()
        out: List[Track] = []

        for dx1, dy1, dx2, dy2, conf in dets:
            best_tid, best_iou = None, 0.0
            for tid, (tx1, ty1, tx2, ty2, age) in self._tracks.items():
                if tid in used:
                    continue
                i = self._iou((dx1, dy1, dx2, dy2), (tx1, ty1, tx2, ty2))
                if i > best_iou:
                    best_iou, best_tid = i, tid

            if best_tid is not None and best_iou >= self.iou_thresh:
                # update existing track
                self._tracks[best_tid] = (dx1, dy1, dx2, dy2, 0)
                used.add(best_tid)
                out.append((dx1, dy1, dx2, dy2, best_tid, conf))
            else:
                # create new track id
                tid = self.next_id
                self.next_id += 1
                self._tracks[tid] = (dx1, dy1, dx2, dy2, 0)
                used.add(tid)
                out.append((dx1, dy1, dx2, dy2, tid, conf))

        # drop stale
        for tid in list(self._tracks.keys()):
            if self._tracks[tid][4] > self.max_age:
                del self._tracks[tid]

        return out


# ---------------- Detector ----------------
@dataclass
class DetectorState:
    tracks: List[Track]
    frame_w: int
    frame_h: int


class Detector:
    """
    Thread-safe YOLOv8(person) + SimpleTracker
    Use:
        det = Detector()
        det.load()  # loads YOLO model (yolov8n.pt by default)
        annotated = det.process(frame)  # returns frame with boxes+ids drawn
        tracks = det.get_tracks()
    """
    def __init__(self, model_path: str = "yolov8n.pt", conf: float = 0.5):
        self.model_path = model_path
        self.conf = conf
        self._model: Optional[YOLO] = None
        self._tracker = SimpleTracker(iou_thresh=0.35, max_age=12)
        self._state = DetectorState(tracks=[], frame_w=640, frame_h=480)
        self._lock = threading.Lock()

    def load(self):
        if self._model is None:
            self._model = YOLO(self.model_path)

    def set_conf(self, conf: float):
        self.conf = float(conf)

    def _detect_people(self, frame) -> List[Det]:
        """Return person detections as list of (x1,y1,x2,y2,conf)."""
        results = self._model.predict(
            frame, classes=[0], conf=self.conf, verbose=False
        )
        dets: List[Det] = []
        if results and results[0].boxes is not None:
            for xyxy, cf in zip(results[0].boxes.xyxy.tolist(), results[0].boxes.conf.tolist()):
                x1, y1, x2, y2 = map(int, xyxy[:4])
                dets.append((x1, y1, x2, y2, float(cf)))
        return dets

    def process(self, frame) -> np.ndarray:
        """
        Run detection+tracking; draw boxes and IDs on the frame;
        update internal state; return annotated frame.
        """
        if self._model is None:
            self.load()

        h, w = frame.shape[:2]
        dets = self._detect_people(frame)
        tracks = self._tracker.update(dets)

        # draw
        for x1, y1, x2, y2, tid, conf in tracks:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID {tid}", (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        with self._lock:
            self._state = DetectorState(tracks=list(tracks), frame_w=w, frame_h=h)

        return frame

    def get_tracks(self) -> List[Track]:
        with self._lock:
            return list(self._state.tracks)

    def get_state(self) -> DetectorState:
        with self._lock:
            return self._state


# --------- Zone counting helpers (polygon) ---------
def _point_in_polygon(px: float, py: float, poly: List[Dict[str, float]]) -> bool:
    """
    Ray casting algorithm. poly = [{x:..., y:...}, ...] in original frame coords.
    Returns True if point is inside polygon.
    """
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(poly[i]["x"]), float(poly[i]["y"])
        xj, yj = float(poly[j]["x"]), float(poly[j]["y"])
        intersect = ((yi > py) != (yj > py)) and \
                    (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def unique_ids_in_zone(zone_points: List[Dict[str, float]], tracks: List[Track]) -> int:
    """
    Count unique track IDs whose bbox center lies inside the polygon zone.
    """
    tids = set()
    for x1, y1, x2, y2, tid, conf in tracks:
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        if _point_in_polygon(cx, cy, zone_points):
            tids.add(tid)
    return len(tids)
