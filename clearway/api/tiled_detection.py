"""Bounded spatial tiling of original pixels; no invented or temporal boxes.

The supplied detector retains its pinned model/preprocessing contract. This
module crops decoded pixels, maps its real boxes back to the source, rejects
internal-edge fragments, and suppresses overlapping duplicate hypotheses.
Person and vehicle hypotheses are never suppressed against one another.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


class TilingError(ValueError):
    pass


@dataclass(frozen=True)
class TilingConfig:
    tile_size: int = 768
    confidence_floor: float = 0.50
    overlap: float = 0.25
    max_tiles: int = 16
    internal_edge_margin_pixels: int = 4
    merge_iou: float = 0.45
    merge_containment: float = 0.85
    max_containment_area_ratio: float = 2.5
    max_containment_center_fraction: float = 0.4

    def __post_init__(self):
        numeric = (self.confidence_floor, self.overlap, self.merge_iou, self.merge_containment,
                   self.max_containment_area_ratio, self.max_containment_center_fraction)
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in numeric):
            raise TilingError("Invalid bounded tiling configuration.")
        if (type(self.tile_size) is not int or not 320 <= self.tile_size <= 2048
                or not math.isfinite(self.confidence_floor) or not .4 <= self.confidence_floor <= .9
                or not math.isfinite(self.overlap) or not 0 <= self.overlap <= .5
                or type(self.max_tiles) is not int or not 1 <= self.max_tiles <= 16
                or type(self.internal_edge_margin_pixels) is not int or not 0 <= self.internal_edge_margin_pixels <= 16
                or not 0.1 <= self.merge_iou <= 0.9 or not 0.5 <= self.merge_containment <= 1
                or not 1 <= self.max_containment_area_ratio <= 4
                or not 0 <= self.max_containment_center_fraction <= .5):
            raise TilingError("Invalid bounded tiling configuration.")

    def metadata(self):
        return {"mode": "tiled", "version": "original-pixel-tiles-v1", "full_frame_pass": True,
                "merge_groups": "person-vs-vehicles", **asdict(self)}


def _starts(length: int, tile: int, overlap: float) -> list[int]:
    if length <= tile:
        return [0]
    stride = max(1, int(tile * (1 - overlap)))
    starts = list(range(0, length - tile + 1, stride))
    if starts[-1] != length - tile:
        starts.append(length - tile)
    return starts


def tile_regions(width: int, height: int, config: TilingConfig) -> list[tuple[int, int, int, int]]:
    if type(width) is not int or type(height) is not int or not 1 <= min(width, height) or max(width, height) > 16384:
        raise TilingError("Invalid image dimensions.")
    # A small source already fits the model pass. Do not infer it twice.
    if width <= config.tile_size and height <= config.tile_size:
        return []
    horizontal, vertical = _starts(width, config.tile_size, config.overlap), _starts(height, config.tile_size, config.overlap)
    if len(horizontal) * len(vertical) > config.max_tiles:
        raise TilingError("Image needs more than the permitted tile count; select larger tiles or full-frame preparation.")
    return [(x, y, min(width, x + config.tile_size), min(height, y + config.tile_size)) for y in vertical for x in horizontal]


def map_tile_box(box: dict, region: tuple[int, int, int, int], width: int, height: int,
                 config: TilingConfig) -> dict | None:
    x0, y0, x_end, y_end = region
    coords = box["xyxy"]
    if (len(coords) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in coords)
            or coords[0] >= coords[2] or coords[1] >= coords[3]):
        raise TilingError("Invalid normalized detector box.")
    tile_width, tile_height = x_end - x0, y_end - y0
    x1, y1, x2, y2 = coords[0] * tile_width, coords[1] * tile_height, coords[2] * tile_width, coords[3] * tile_height
    margin = config.internal_edge_margin_pixels
    # Keep objects clipped by the actual image edge. Overlapping neighbors and
    # the full-frame pass cover fragments clipped only by a crop boundary.
    if ((x0 > 0 and x1 <= margin) or (y0 > 0 and y1 <= margin)
            or (x_end < width and x2 >= tile_width - margin)
            or (y_end < height and y2 >= tile_height - margin)):
        return None
    return {**box, "xyxy": [round((x0 + x1) / width, 6), round((y0 + y1) / height, 6),
                             round((x0 + x2) / width, 6), round((y0 + y2) / height, 6)]}


def _overlap(first, second):
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    area_a, area_b = (ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1)
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    return intersection, area_a, area_b


def duplicates(first: dict, second: dict, config: TilingConfig) -> bool:
    if (first["class_name"] == "person") != (second["class_name"] == "person"):
        return False
    a, b = first["xyxy"], second["xyxy"]
    intersection, area_a, area_b = _overlap(a, b)
    if min(area_a, area_b) <= 0:
        raise TilingError("Degenerate candidate box.")
    if intersection / (area_a + area_b - intersection) >= config.merge_iou:
        return True
    # Reject a contained fragment only when size and center also agree. Nearby
    # small vehicles inside a large imprecise box must not vanish by IoS alone.
    if intersection / min(area_a, area_b) < config.merge_containment or max(area_a, area_b) / min(area_a, area_b) > config.max_containment_area_ratio:
        return False
    distance = math.hypot((a[0] + a[2] - b[0] - b[2]) / 2, (a[1] + a[3] - b[1] - b[3]) / 2)
    small_diagonal = min(math.hypot(a[2] - a[0], a[3] - a[1]), math.hypot(b[2] - b[0], b[3] - b[1]))
    return distance <= config.max_containment_center_fraction * small_diagonal


def merge_detections(boxes: list[dict], config: TilingConfig) -> list[dict]:
    if len(boxes) > (config.max_tiles + 1) * 300:
        raise TilingError("Too many detector candidates.")
    selected = []
    for candidate in sorted(boxes, key=lambda box: -box["confidence"]):
        if not any(duplicates(candidate, prior, config) for prior in selected):
            selected.append(candidate)
        if len(selected) >= 300:
            break
    return selected


class TiledDetector:
    def __init__(self, detector, config: TilingConfig):
        self.detector, self.config = detector, config
        self.cv2 = detector.cv2
        self.runtime_version = detector.runtime_version
        self.last_passes = 0

    def detect(self, image) -> list[dict]:
        height, width = map(int, image.shape[:2])
        regions = tile_regions(width, height, self.config)
        # Raising this post-NMS cutoff cannot let a lower-scored candidate
        # suppress a retained one. The underlying pinned model keeps its own
        # input/decoding threshold; this additional cutoff is in cache metadata.
        candidates = [box for box in self.detector.detect(image) if box["confidence"] >= self.config.confidence_floor]
        self.last_passes = 1
        for region in regions:
            x1, y1, x2, y2 = region
            for box in self.detector.detect(image[y1:y2, x1:x2]):
                if box["confidence"] < self.config.confidence_floor:
                    continue
                mapped = map_tile_box(box, region, width, height, self.config)
                if mapped is not None:
                    candidates.append(mapped)
            self.last_passes += 1
        return merge_detections(candidates, self.config)
