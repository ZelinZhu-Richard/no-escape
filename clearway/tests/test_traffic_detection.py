from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.traffic_detection import (
    DEFAULT_PROFILE, PROFILES, TrafficDetectionError, TrafficDetector,
    install_profile, prepare_input, selected_profile, validate_model_io,
)


def write_config(data_dir, **fields):
    folder = data_dir / "models"
    folder.mkdir(exist_ok=True)
    path = folder / "live-detector.json"
    path.write_text(json.dumps({"schema_version": 1, "profile": DEFAULT_PROFILE, **fields}))
    return path


def test_default_live_profile_is_medium_and_replay_profile_is_separate(tmp_path):
    from api.detection import MODEL_NAME, MODEL_SHA256
    live = selected_profile(tmp_path)
    assert live.id == "yolox-m640"
    assert live.name == "YOLOX-M" and live.input_size == 640
    assert live.license == "Apache-2.0" and live.confidence == 0.3
    assert MODEL_NAME == "YOLOX-Tiny" and MODEL_SHA256 != live.sha256
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("fields", [
    {"schema_version": True}, {"schema_version": 2}, {"profile": "unapproved-model"},
    {"profile": ["not-a-string"]}, {"weights_sha256": "not-the-pinned-digest"},
    {"profile": "yolo11s-visdrone640"},
    {"profile": "yolo11s-visdrone640", "agpl_choice_accepted": "true"},
])
def test_bad_or_unacknowledged_configuration_does_not_fall_back(tmp_path, fields):
    write_config(tmp_path, **fields)
    with pytest.raises(TrafficDetectionError):
        selected_profile(tmp_path)


def test_optional_profile_requires_explicit_selection_and_preserves_taxonomy(tmp_path):
    write_config(tmp_path, profile="yolo11s-visdrone640", agpl_choice_accepted=True)
    profile = selected_profile(tmp_path)
    assert profile.license == "AGPL-3.0"
    assert profile.confidence == 0.4
    assert dict(profile.display_classes)[4] == "van"
    assert dict(profile.display_classes)[6] == "tricycle"
    assert dict(profile.display_classes)[7] == "awning-tricycle"
    assert dict(profile.display_classes)[0] == dict(profile.display_classes)[1] == "person"
    assert dict(profile.native_classes)[1] == "people"


def test_symlink_and_oversized_configuration_are_rejected(tmp_path):
    path = write_config(tmp_path)
    target = tmp_path / "other.json"
    path.replace(target)
    path.symlink_to(target)
    with pytest.raises(TrafficDetectionError):
        selected_profile(tmp_path)
    path.unlink()
    path.write_text(" " * 4097)
    with pytest.raises(TrafficDetectionError):
        selected_profile(tmp_path)


def fixture_profile(monkeypatch, contents=b"explicit-test-model"):
    profile = replace(PROFILES[DEFAULT_PROFILE], sha256=hashlib.sha256(contents).hexdigest())
    monkeypatch.setitem(PROFILES, DEFAULT_PROFILE, profile)
    return profile, contents


def test_setup_from_file_verifies_digest_and_atomically_selects_without_network(tmp_path, monkeypatch):
    profile, contents = fixture_profile(monkeypatch)
    source = tmp_path / "source.onnx"
    source.write_bytes(contents)
    data_dir = tmp_path / "data"
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: pytest.fail("No implicit model download"))
    assert install_profile(data_dir, profile.id, from_file=source) == profile
    assert (data_dir / "models" / profile.filename).read_bytes() == contents
    assert selected_profile(data_dir) == profile
    assert not list((data_dir / "models").glob("*.tmp"))


def test_setup_does_not_download_without_an_explicit_flag(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: pytest.fail("No implicit model download"))
    with pytest.raises(TrafficDetectionError, match="explicit --download"):
        install_profile(tmp_path, DEFAULT_PROFILE)
    assert not (tmp_path / "models" / "live-detector.json").exists()


def test_explicit_download_uses_pinned_url_and_digest(tmp_path, monkeypatch):
    profile, contents = fixture_profile(monkeypatch)
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return io.BytesIO(contents)
    monkeypatch.setattr("urllib.request.urlopen", fetch)
    install_profile(tmp_path, profile.id, download=True)
    assert calls == [profile.download_url]
    assert selected_profile(tmp_path).sha256 == hashlib.sha256(contents).hexdigest()


def test_bad_checksum_preserves_previous_configuration_and_removes_partial_file(tmp_path, monkeypatch):
    profile, _ = fixture_profile(monkeypatch)
    prior = write_config(tmp_path)
    old_config = prior.read_bytes()
    source = tmp_path / "wrong.onnx"
    source.write_bytes(b"wrong model")
    with pytest.raises(TrafficDetectionError, match="checksum"):
        install_profile(tmp_path, profile.id, from_file=source)
    assert prior.read_bytes() == old_config
    assert not (tmp_path / "models" / profile.filename).exists()
    assert not list((tmp_path / "models").glob("*.tmp"))


def test_optional_setup_is_blocked_before_copy_or_download_without_license_choice(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: pytest.fail("No unapproved optional download"))
    with pytest.raises(TrafficDetectionError, match="accept-agpl"):
        install_profile(tmp_path, "yolo11s-visdrone640", download=True)
    assert list(tmp_path.iterdir()) == []


class SessionInfo:
    def __init__(self, input_shape, output_shape):
        self.input = SimpleNamespace(name="images", shape=input_shape, type="tensor(float)")
        self.output = SimpleNamespace(name="output", shape=output_shape, type="tensor(float)")

    def get_inputs(self):
        return [self.input]

    def get_outputs(self):
        return [self.output]


def test_model_tensor_interfaces_are_profile_specific():
    validate_model_io(SessionInfo([1, 3, 640, 640], [1, 8400, 85]), PROFILES[DEFAULT_PROFILE])
    validate_model_io(SessionInfo(["batch", 3, "height", "width"], ["batch", 14, "anchors"]), PROFILES["yolo11s-visdrone640"])
    with pytest.raises(TrafficDetectionError, match="shape"):
        validate_model_io(SessionInfo([1, 3, 416, 416], [1, 3549, 85]), PROFILES[DEFAULT_PROFILE])
    with pytest.raises(TrafficDetectionError, match="shape"):
        validate_model_io(SessionInfo([1, 3, 640, 640], [1, 85, 8400]), PROFILES[DEFAULT_PROFILE])
    with pytest.raises(TrafficDetectionError, match="shape"):
        validate_model_io(SessionInfo([1, "channels", 640, 640], [1, 14, 8400]), PROFILES["yolo11s-visdrone640"])


def vision_modules():
    return pytest.importorskip("cv2"), pytest.importorskip("numpy")


def test_preprocessing_profiles_preserve_their_actual_color_range_and_padding():
    cv2, np = vision_modules()
    image = np.full((2, 4, 3), [10, 20, 30], dtype=np.uint8)
    raw, transform = prepare_input(image, PROFILES[DEFAULT_PROFILE], cv2, np)
    assert raw.shape == (1, 3, 640, 640)
    assert raw[0, :, 0, 0] == pytest.approx([10, 20, 30])  # BGR, no normalization
    assert raw[0, :, 500, 0] == pytest.approx([114, 114, 114])
    assert transform == (160, 0, 0)
    rgb, centered = prepare_input(image, PROFILES["yolo11s-visdrone640"], cv2, np)
    assert rgb[0, :, 160, 0] == pytest.approx([30 / 255, 20 / 255, 10 / 255])
    assert rgb[0, :, 0, 0] == pytest.approx([114 / 255] * 3)
    assert centered == (160, 0, 160)


def tensor_detector(profile_id, output):
    cv2, np = vision_modules()
    profile = PROFILES[profile_id]
    detector = TrafficDetector.__new__(TrafficDetector)
    detector.profile, detector.cv2, detector.np, detector.input_name = profile, cv2, np, "images"
    detector.grids = np.concatenate([np.stack(np.meshgrid(np.arange(640 // s), np.arange(640 // s)), axis=-1).reshape(-1, 2) for s in (8, 16, 32)])
    detector.strides = np.concatenate([np.full(((640 // s) ** 2, 1), s) for s in (8, 16, 32)])
    detector.session = SimpleNamespace(run=lambda *_: [output])
    return detector


def test_yolox_grid_decode_multiplies_objectness_and_suppresses_duplicate_vehicle():
    _, np = vision_modules()
    output = np.zeros((1, 8400, 85), dtype=np.float32)
    output[0, 0, :4] = [40, 20, np.log(160 / 8), np.log(80 / 8)]
    output[0, 0, 4] = 0.8
    output[0, 0, 5 + 2] = 0.9
    output[0, 1, :4] = [39, 20, np.log(160 / 8), np.log(80 / 8)]
    output[0, 1, 4] = 0.8
    output[0, 1, 5 + 7] = 0.8
    boxes = tensor_detector(DEFAULT_PROFILE, output).detect(np.zeros((320, 640, 3), dtype=np.uint8))
    assert len(boxes) == 1
    assert boxes[0]["class_name"] == boxes[0]["native_class_name"] == "car"
    assert boxes[0]["confidence"] == pytest.approx(0.72)
    assert boxes[0]["xyxy"] == pytest.approx([0.375, 0.375, 0.625, 0.625])


def test_visdrone_uses_decoded_pixel_boxes_without_grid_or_objectness_and_removes_center_padding():
    _, np = vision_modules()
    output = np.zeros((1, 14, 8400), dtype=np.float32)
    output[0, :4, 0] = [320, 320, 160, 80]
    output[0, 4 + 4, 0] = 0.81  # van is its own class
    output[0, :4, 1] = [100, 250, 40, 60]
    output[0, 4 + 1, 1] = 0.7  # native people maps to generic person
    boxes = tensor_detector("yolo11s-visdrone640", output).detect(np.zeros((320, 640, 3), dtype=np.uint8))
    assert len(boxes) == 2
    assert boxes[0]["class_name"] == boxes[0]["native_class_name"] == "van"
    assert boxes[0]["confidence"] == pytest.approx(0.81)
    assert boxes[0]["xyxy"] == pytest.approx([0.375, 0.375, 0.625, 0.625])
    assert boxes[1]["class_name"] == "person" and boxes[1]["native_class_name"] == "people"


def test_visdrone_filters_low_confidence_candidates_before_nms():
    _, np = vision_modules()
    output = np.zeros((1, 14, 8400), dtype=np.float32)
    for index, confidence in enumerate((0.352, 0.39, 0.41)):
        output[0, :4, index] = [100 + 150 * index, 320, 40, 40]
        output[0, 4 + 3, index] = confidence
    boxes = tensor_detector("yolo11s-visdrone640", output).detect(np.zeros((640, 640, 3), dtype=np.uint8))
    assert len(boxes) == 1
    assert boxes[0]["confidence"] == pytest.approx(0.41)
    assert boxes[0]["xyxy"] == pytest.approx([380 / 640, 300 / 640, 420 / 640, 340 / 640])


def test_decoded_boxes_clip_to_source_image_and_discard_padding_only_boxes():
    _, np = vision_modules()
    output = np.zeros((1, 14, 8400), dtype=np.float32)
    output[0, :4, 0] = [0, 170, 100, 80]  # crosses image left/top after unpadding
    output[0, 4 + 3, 0] = 0.8
    output[0, :4, 1] = [500, 40, 40, 30]  # entirely inside upper letterbox padding
    output[0, 4 + 3, 1] = 0.7
    boxes = tensor_detector("yolo11s-visdrone640", output).detect(np.zeros((320, 640, 3), dtype=np.uint8))
    assert len(boxes) == 1
    assert boxes[0]["xyxy"] == pytest.approx([0, 0, 50 / 640, 50 / 320])


@pytest.mark.parametrize("failure", ["shape", "nan", "score", "negative_box"])
def test_invalid_output_tensors_never_create_live_boxes(failure):
    _, np = vision_modules()
    output = np.zeros((1, 14, 8400), dtype=np.float32)
    if failure == "shape":
        output = output[:, :, :4]
    elif failure == "nan":
        output[0, 0, 0] = np.nan
    elif failure == "score":
        output[0, 4, 0] = 2
    elif failure == "negative_box":
        output[0, :4, 0] = [320, 320, -2, 3]
        output[0, 4 + 3, 0] = 0.9
    with pytest.raises(TrafficDetectionError):
        tensor_detector("yolo11s-visdrone640", output).detect(np.zeros((320, 640, 3), dtype=np.uint8))


def test_weight_mismatch_is_rejected_without_network_or_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: pytest.fail("Runtime must not download weights"))
    weights = tmp_path / "wrong.onnx"
    weights.write_bytes(b"not the selected graph")
    with pytest.raises(TrafficDetectionError, match="Pinned live weights"):
        TrafficDetector(weights, PROFILES[DEFAULT_PROFILE])
