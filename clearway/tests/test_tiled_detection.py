"""Geometry and bounded-inference regressions; no external weights or images."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from api.tiled_detection import (
    TiledDetector, TilingConfig, TilingError, duplicates, map_tile_box, merge_detections, tile_regions,
)


def box(coords, score=.8, name="car"):
    return {"class_name": name, "native_class_name": name, "confidence": score, "xyxy": coords}


def test_tile_grid_covers_edges_and_bounds_number_before_inference():
    config = TilingConfig()
    regions = tile_regions(1920, 1080, config)
    assert len(regions) == 6
    assert regions[0] == (0, 0, 768, 768) and regions[-1] == (1152, 312, 1920, 1080)
    assert all(0 <= x1 < x2 <= 1920 and 0 <= y1 < y2 <= 1080 for x1, y1, x2, y2 in regions)
    # Every source pixel is covered; real edges don't depend on a padded crop.
    assert all(any(x1 <= x < x2 for x1, _, x2, _ in regions) for x in range(1920))
    assert all(any(y1 <= y < y2 for _, y1, _, y2 in regions) for y in range(1080))
    assert tile_regions(640, 480, config) == []
    with pytest.raises(TilingError, match="tile count"):
        tile_regions(8000, 8000, config)


def test_tile_coordinates_map_to_original_without_changing_class_or_confidence():
    candidate = box([.1, .2, .3, .4], name="van")
    mapped = map_tile_box(candidate, (576, 312, 1344, 1080), 1920, 1080, TilingConfig())
    assert mapped["xyxy"] == pytest.approx([(576+76.8)/1920, (312+153.6)/1080, (576+230.4)/1920, (312+307.2)/1080], abs=1e-6)
    assert mapped["class_name"] == mapped["native_class_name"] == "van"
    assert mapped["confidence"] == .8 and candidate["xyxy"] == [.1, .2, .3, .4]


def test_internal_crop_fragments_are_rejected_but_image_edge_objects_remain():
    config = TilingConfig()
    assert map_tile_box(box([.9, .2, 1, .4]), (0, 0, 768, 768), 1920, 1080, config) is None
    assert map_tile_box(box([0, .2, .1, .4]), (576, 0, 1344, 768), 1920, 1080, config) is None
    assert map_tile_box(box([0, .2, .1, .4]), (0, 0, 768, 768), 1920, 1080, config) is not None
    assert map_tile_box(box([.8, .8, 1, 1]), (1152, 312, 1920, 1080), 1920, 1080, config) is not None
    # The neighboring overlap sees the full vehicle discarded at the first seam.
    assert map_tile_box(box([.20, .2, .30, .4]), (576, 0, 1344, 768), 1920, 1080, config) is not None


def test_overlap_merge_keeps_best_vehicle_class_and_never_merges_person_with_car():
    candidates = [box([.1,.1,.3,.3], .7, "car"), box([.101,.102,.301,.302], .9, "van"),
                  box([.1,.1,.3,.3], .8, "person")]
    result = merge_detections(candidates, TilingConfig())
    assert [item["class_name"] for item in result] == ["van", "person"]
    assert len(candidates) == 3


def test_adjacent_occluded_vehicles_are_not_removed_by_containment_alone():
    config = TilingConfig()
    first = box([.1,.1,.3,.3])
    adjacent = box([.25,.12,.45,.32])
    small_inside_large = box([.25,.25,.3,.3])
    assert not duplicates(first, adjacent, config)
    assert not duplicates(first, small_inside_large, config)
    assert len(merge_detections([first, adjacent, small_inside_large], config)) == 3
    centered_fragment = box([.136,.136,.264,.264])
    assert duplicates(first, centered_fragment, config)


def test_tiler_uses_original_pixel_crops_and_filters_weak_boxes():
    np = pytest.importorskip("numpy")
    image = np.arange(1080*1920*3, dtype=np.uint32).reshape(1080,1920,3)
    shapes, starts = [], []
    class Detector:
        cv2 = SimpleNamespace()
        runtime_version = "test-only"
        def detect(self, frame):
            shapes.append(frame.shape)
            starts.append(int(frame[0,0,0]))
            return [box([.2,.2,.3,.3], .8), box([.5,.5,.6,.6], .49)]
    method = TiledDetector(Detector(), TilingConfig())
    result = method.detect(image)
    assert method.last_passes == 7
    assert shapes == [(1080,1920,3)] + [(768,768,3)] * 6
    assert starts == [0] + [int(image[y1,x1,0]) for x1,y1,_,_ in tile_regions(1920,1080,TilingConfig())]
    assert result and all(item["confidence"] >= .5 for item in result)
    assert all(all(0 <= value <= 1 for value in item["xyxy"]) for item in result)


def test_small_source_uses_one_pass_and_oversized_grid_uses_zero():
    np = pytest.importorskip("numpy")
    calls = []
    detector = SimpleNamespace(cv2=None, runtime_version="test", detect=lambda image: calls.append(image.shape) or [])
    method = TiledDetector(detector, TilingConfig())
    assert method.detect(np.zeros((480,640,3), dtype=np.uint8)) == []
    assert method.last_passes == 1 and len(calls) == 1
    fake_large = SimpleNamespace(shape=(8000,8000,3))
    with pytest.raises(TilingError):
        method.detect(fake_large)
    assert len(calls) == 1


@pytest.mark.parametrize("values", [
    {"tile_size": 1}, {"max_tiles": 17}, {"overlap": .9}, {"overlap": float("nan")},
    {"confidence_floor": .1}, {"merge_iou": "wrong"}, {"merge_containment": .1},
])
def test_invalid_tiling_parameters_are_rejected(values):
    with pytest.raises(TilingError):
        replace(TilingConfig(), **values)
