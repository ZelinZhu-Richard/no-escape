"""Synthetic association/lifecycle tests, not tracking-accuracy measurements."""
from copy import deepcopy
import hashlib
import itertools
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from api.live_tracking import (
    LiveTrackingService, _linear_assignment, MAX_CANDIDATES, MAX_SESSIONS,
    MAX_TRACKS, LOST_TTL_SECONDS,
)


def box(x=.2, confidence=.8, kind="car"):
    return {"class_name": kind, "confidence": confidence, "xyxy": [x, .3, x+.1, .5]}


@pytest.fixture
def setup():
    ticks = [100.0]
    service = LiveTrackingService(monotonic=lambda: ticks[0])
    context = {"run_id": str(uuid4()), "camera_id": "caltrans-d4-49", "stream_id": str(uuid4()), "media_time_seconds": 0.0}
    return service, ticks, context


def payload(context, candidates, nonce, **overrides):
    digest = hashlib.sha256(str(nonce).encode()).hexdigest()
    return {"status": "available", "analysis_mode": "fresh", "camera_id": context["camera_id"],
            "image_sha256": digest, "image_width": 640, "image_height": 480,
            "confidence_threshold": .4, "boxes": deepcopy([item for item in candidates if item["confidence"] >= .4]),
            "tracking_candidates": deepcopy(candidates),
            "provenance": {"kind": "local_yolo_image", "fixture": False, "image_sha256": digest,
                           "configuration_sha256": "a"*64}, **overrides}


def sample(setup, second, candidates=None, *, wall=None, nonce=None, mutate=None, context=None):
    service, ticks, default = setup
    context = {**(context or default), "media_time_seconds": second}
    ticks[0] = 100 + (second if wall is None else wall)
    result = payload(context, [box()] if candidates is None else candidates, second if nonce is None else nonce)
    if mutate:
        mutate(result)
    before = deepcopy(result)
    output = service.process(context, result)
    assert result == before  # Never rewrite raw alert evidence or candidates.
    return output


def test_two_stage_low_recovery_retains_id_and_actual_low_observation(setup):
    first = sample(setup, 0)
    item = first["tracks"][0]
    assert first["algorithm"] == "ByteTrack" and first["status"] == "available"
    assert item["observation"] == "high" and item["confirmed"] is True
    weak = box(.205, .2)
    second = sample(setup, .125, [weak])
    recovered = second["tracks"][0]
    assert recovered["track_id"] == item["track_id"]
    assert recovered["xyxy"] == weak["xyxy"] and recovered["confidence"] == .2
    assert recovered["observation"] == "low_recovery" and recovered["confirmed"] is True
    third = sample(setup, .25, [box(.21)])
    assert third["tracks"][0]["track_id"] == item["track_id"]
    assert third["tracks"][0]["observation"] == "high"


def test_unmatched_low_never_starts_track_or_becomes_prediction_evidence(setup):
    assert sample(setup, 0, [box(confidence=.2)])["tracks"] == []
    first = sample(setup, .125)
    assert first["tracks"][0]["confirmed"] is False
    # A tentative one-observation track requires another HIGH observation.
    assert sample(setup, .25, [box(confidence=.2)])["tracks"] == []
    assert sample(setup, .375, [box(.7, .2)])["tracks"] == []


def test_high_unmatched_observations_remain_visible_and_confirm_on_next_high(setup):
    sample(setup, 0, [])
    high = box(.6, .42)
    first = sample(setup, .125, [high])["tracks"][0]
    assert first["xyxy"] == high["xyxy"] and first["confidence"] == .42
    assert first["confirmed"] is False
    second = sample(setup, .25, [high])["tracks"][0]
    assert second["track_id"] == first["track_id"] and second["confirmed"] is True


def test_lost_tracks_emit_nothing_and_only_high_can_reacquire(setup):
    identifier = sample(setup, 0)["tracks"][0]["track_id"]
    empty = sample(setup, .125, [])
    assert empty["tracks"] == [] and empty["prediction_only_tracks_returned"] == 0
    assert sample(setup, .25, [box(confidence=.2)])["tracks"] == []
    recovered = sample(setup, .375)["tracks"][0]
    assert recovered["track_id"] == identifier
    assert recovered["observation"] == "high"


def test_class_aware_association_never_transfers_a_car_id_to_person_or_van(setup):
    car = sample(setup, 0)["tracks"][0]["track_id"]
    assert sample(setup, .125, [box(confidence=.2, kind="person")])["tracks"] == []
    person = sample(setup, .25, [box(kind="person")])["tracks"][0]["track_id"]
    assert person != car
    van = sample(setup, .375, [box(kind="van")])["tracks"][0]["track_id"]
    assert van not in (person, car)


def test_assignment_is_globally_optimal_not_greedy():
    np = pytest.importorskip("numpy")
    matches, missing_rows, missing_columns = _linear_assignment(np.array([[.1, .2], [.11, .9]]), .8, np)
    assert set(matches) == {(0, 1), (1, 0)}
    assert missing_rows == missing_columns == []


def test_assignment_unmatched_cost_matches_bruteforce_small_rectangles():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(8)
    for n, m in ((1, 3), (3, 1), (3, 4), (4, 3), (4, 4)):
        for _ in range(10):
            cost = rng.random((n, m))
            matches, unmatched, _ = _linear_assignment(cost, .7, np)
            actual = sum(cost[i, j] for i, j in matches) + len(unmatched)*.7
            best = float("inf")
            for choices in itertools.product(range(-1, m), repeat=n):
                columns = [j for j in choices if j >= 0]
                if len(columns) != len(set(columns)):
                    continue
                if any(j >= 0 and cost[i, j] > .7 for i, j in enumerate(choices)):
                    continue
                best = min(best, sum(.7 if j < 0 else cost[i, j] for i, j in enumerate(choices)))
            assert actual == pytest.approx(best)


def test_multiple_same_class_observations_keep_one_to_one_ids_and_current_geometry(setup):
    first = sample(setup, 0, [box(.1), box(.6)])
    initial = {round(t["xyxy"][0], 2): t["track_id"] for t in first["tracks"]}
    current = [box(.61), box(.11)]  # Input order is not identity.
    tracked = sample(setup, .125, current)["tracks"]
    assert len({t["track_id"] for t in tracked}) == 2
    for track in tracked:
        expected = initial[.6 if track["xyxy"][0] > .5 else .1]
        assert track["track_id"] == expected
        assert track["xyxy"] in [b["xyxy"] for b in current]


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: r["provenance"].update(configuration_sha256="b"*64), "configuration_changed"),
    (lambda r: r.update(image_width=800), "image_shape_changed"),
    (lambda r: r.update(confidence_threshold=.5), "threshold_changed"),
])
def test_configuration_shape_and_threshold_changes_never_reuse_ids(setup, mutation, reason):
    old = sample(setup, 0)["tracks"][0]["track_id"]
    result = sample(setup, .125, mutate=mutation)
    assert result["reset_reason"] == reason
    assert result["tracks"][0]["track_id"] != old


@pytest.mark.parametrize("media,wall,reason", [
    (0, .125, "clock_discontinuity"), (.125, 0, "clock_discontinuity"),
    (1.1, 1.1, "timing_gap"), (.125, .9, "timing_gap"),
])
def test_seek_duplicate_time_clock_skew_and_gap_reset(setup, media, wall, reason):
    old = sample(setup, 0)["tracks"][0]["track_id"]
    result = sample(setup, media, wall=wall, nonce="new-image")
    assert result["reset_reason"] == reason
    assert result["tracks"][0]["track_id"] != old


def test_frozen_or_replayed_image_bytes_reset_and_remain_suppressed(setup):
    old = sample(setup, 0, nonce="frozen")["tracks"][0]["track_id"]
    for second in (.125, .25, .375, .5):
        result = sample(setup, second, nonce="frozen")
        assert result["reset_reason"] == "duplicate_frame" and result["tracks"] == []
    new = sample(setup, .625, nonce="different")["tracks"][0]["track_id"]
    assert new != old
    # Replaying an earlier image within the bounded history also resets.
    assert sample(setup, .75, nonce="frozen")["tracks"] == []


def test_frozen_image_at_unchanged_or_reversed_media_time_stays_suppressed(setup):
    sample(setup, 1, wall=0, nonce="frozen")
    for second, wall in ((1, .125), (1, .25), (.5, .375), (.5, .5)):
        result = sample(setup, second, wall=wall, nonce="frozen")
        assert result["reset_reason"] == "duplicate_frame" and result["tracks"] == []
    assert len(sample(setup, .625, wall=.625, nonce="new")["tracks"]) == 1


@pytest.mark.parametrize("field", ["run_id", "camera_id", "stream_id"])
def test_session_context_changes_do_not_share_identity(setup, field):
    old = sample(setup, 0)["tracks"][0]["track_id"]
    context = {**setup[2], field: "caltrans-d4-37" if field == "camera_id" else str(uuid4())}
    result = sample(setup, .125, context=context)
    assert result["tracks"][0]["track_id"] != old
    assert result[field] == context[field]


def test_track_age_uses_both_media_and_wall_time_and_drops_lost_identity(setup):
    old = sample(setup, 0)["tracks"][0]["track_id"]
    for second in (.125, .25, .5, .75):
        assert sample(setup, second, [])["tracks"] == []
    result = sample(setup, LOST_TTL_SECONDS+.125)
    assert result["tracks"][0]["track_id"] != old
    assert result["reset_reason"] is None


@pytest.mark.parametrize("mutate", [
    lambda r: r.pop("tracking_candidates"),
    lambda r: r.update(tracking_candidates=[box()]*(MAX_CANDIDATES+1)),
    lambda r: r.update(tracking_candidates=[box(confidence=.09)]),
    lambda r: r.update(tracking_candidates=[box(kind="person identity")]),
    lambda r: r.update(tracking_candidates=[{**box(), "xyxy": [0, 0, 2, 1]}]),
    lambda r: r.update(image_sha256="wrong"),
    lambda r: r["provenance"].update(fixture=True),
    lambda r: r.update(camera_id="another-camera"),
    lambda r: r.update(image_width=0),
    lambda r: r.update(image_width=4096, image_height=4096),
    lambda r: r.update(confidence_threshold=float("nan")),
])
def test_invalid_input_fails_soft_clears_history_and_never_fabricates_tracks(setup, mutate):
    old = sample(setup, 0)["tracks"][0]["track_id"]
    invalid = sample(setup, .125, mutate=mutate)
    assert invalid["status"] == "unavailable" and invalid["tracks"] == []
    assert sample(setup, .25)["tracks"][0]["track_id"] != old


def test_invalid_frame_for_one_session_does_not_reset_another_camera(setup):
    other = {**setup[2], "camera_id": "caltrans-d4-37"}
    identifier = sample(setup, 0, context=other)["tracks"][0]["track_id"]
    sample(setup, .125, mutate=lambda r: r.pop("tracking_candidates"))
    assert sample(setup, .25, context=other)["tracks"][0]["track_id"] == identifier


def test_high_observations_missing_from_low_pool_are_preserved_without_mutation(setup):
    result = sample(setup, 0, mutate=lambda r: r.update(tracking_candidates=[]))
    assert len(result["tracks"]) == 1 and result["tracks"][0]["observation"] == "high"


def test_state_and_returned_values_are_bounded_and_detached(setup):
    service, _, context = setup
    first = sample(setup, 0)
    first["tracks"][0]["xyxy"][0] = .99
    assert sample(setup, .125)["tracks"][0]["xyxy"] == box()["xyxy"]
    for index in range(MAX_SESSIONS + 2):
        sample(setup, .25+index*.001, context={**context, "camera_id": f"camera-{index}"})
    assert len(service._sessions) == MAX_SESSIONS
    assert all(len(entry["engine"].tracks) <= MAX_TRACKS for entry in service._sessions.values())
    service.reset()
    assert not service._sessions


def test_optional_numpy_is_not_needed_to_import_module():
    source_root = str(Path(__file__).resolve().parents[1])
    script = "import sys; sys.path.insert(0, " + repr(source_root) + "); from api.live_tracking import LiveTrackingService; LiveTrackingService()"
    result = subprocess.run([sys.executable, "-S", "-c", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_missing_numpy_returns_unavailable_without_breaking_detector_result(setup, monkeypatch):
    import builtins
    original = builtins.__import__
    def without_numpy(name, *args, **kwargs):
        if name == "numpy":
            raise ImportError("optional runtime unavailable")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", without_numpy)
    result = sample(setup, 0)
    assert result["status"] == "unavailable" and result["tracks"] == []


def fast_box(x=.3, y=.7, confidence=.8, kind="car", width=.06, height=.08):
    return {"class_name": kind, "confidence": confidence, "xyxy": [x, y, x+width, y+height]}


@pytest.fixture
def tva43(setup):
    setup[2]["camera_id"] = "caltrans-d4-285"
    return setup


def test_tva43_sparse_fast_vehicle_keeps_id_using_only_current_high_observations(tva43):
    first = sample(tva43, 0, [fast_box()])
    identifier = first["tracks"][0]["track_id"]
    recoveries = 0
    for index in range(1, 8):
        current = fast_box(.3 + .025*index, .7 - .04*index)
        result = sample(tva43, index/6, [current])
        assert result["association_policy"] == "bytetrack-tva43-gated-geometry-v1"
        assert result["prediction_only_tracks_returned"] == 0
        assert result["tracks"][0]["track_id"] == identifier
        assert result["tracks"][0]["xyxy"] == current["xyxy"]
        assert result["tracks"][0]["confidence"] == current["confidence"]
        assert result["tracks"][0]["observation"] == "high"
        assert result["tracks"][0]["confirmed"] is True
        recoveries += result["geometry_recoveries"]
    assert recoveries >= 1


def test_tva43_can_confirm_a_uniquely_matched_fast_tentative_vehicle(tva43):
    sample(tva43, 0, [])
    first = sample(tva43, .125, [fast_box()])["tracks"][0]
    assert first["confirmed"] is False
    second = sample(tva43, .25, [fast_box(.325, .66)])
    assert second["tracks"][0]["track_id"] == first["track_id"]
    assert second["tracks"][0]["association"] == "gated_geometry"
    assert second["tracks"][0]["confirmed"] is True


def test_tva43_recorded_sparse_pair_recovers_without_reducing_detector_confidence(tva43):
    # Development coordinates from one visibly continuous near-road vehicle;
    # this regression does not establish population identity/speed accuracy.
    first = {"class_name": "car", "confidence": .8592162132263184,
             "xyxy": [.504897, .835600, .568129, .918890]}
    second = {"class_name": "car", "confidence": .8687207698822021,
              "xyxy": [.530423, .791728, .587271, .865820]}
    previous = sample(tva43, 0, [first], mutate=lambda r: r.update(image_height=427))["tracks"][0]
    result = sample(tva43, .167, [second], mutate=lambda r: r.update(image_height=427))
    assert result["geometry_recoveries"] == 1
    current = result["tracks"][0]
    assert current["track_id"] == previous["track_id"]
    assert current["xyxy"] == second["xyxy"] and current["confidence"] == second["confidence"]


@pytest.mark.parametrize("prior,current", [
    ([fast_box(.37, .5)], [fast_box(.32, .5), fast_box(.42, .5)]),
    ([fast_box(.37, .5), fast_box(.47, .5)], [fast_box(.42, .5)]),
    ([fast_box(.37, .5), fast_box(.47, .5)], [fast_box(.418, .5), fast_box(.422, .5)]),
])
def test_tva43_rejects_row_column_and_crossing_ambiguity_instead_of_guessing(tva43, prior, current):
    previous = {t["track_id"] for t in sample(tva43, 0, prior)["tracks"]}
    result = sample(tva43, .125, list(reversed(current)))
    assert result["geometry_recoveries"] == 0
    assert all(t["track_id"] not in previous and not t["confirmed"] for t in result["tracks"])


@pytest.mark.parametrize("candidate", [
    fast_box(.325, .66, kind="van"),
    fast_box(.325, .66, confidence=.2),
    fast_box(.325, .66, width=.02),
    fast_box(.5, .5),
])
def test_tva43_recovery_refuses_wrong_class_low_scores_size_jumps_and_distant_boxes(tva43, candidate):
    previous = sample(tva43, 0, [fast_box()])["tracks"][0]["track_id"]
    result = sample(tva43, .125, [candidate])
    assert result["geometry_recoveries"] == 0
    assert all(t["track_id"] != previous for t in result["tracks"])


@pytest.mark.parametrize("media,wall", [(.3, .3), (.125, .3)])
def test_tva43_recovery_refuses_media_or_wall_gaps_over_a_quarter_second(tva43, media, wall):
    previous = sample(tva43, 0, [fast_box()])["tracks"][0]["track_id"]
    result = sample(tva43, media, [fast_box(.325, .66)], wall=wall)
    assert result["geometry_recoveries"] == 0
    assert result["tracks"][0]["track_id"] != previous


def test_tva43_recovery_never_reconnects_a_lost_track(tva43):
    previous = sample(tva43, 0, [fast_box()])["tracks"][0]["track_id"]
    assert sample(tva43, .125, [])["tracks"] == []
    result = sample(tva43, .25, [fast_box(.325, .66)])
    assert result["geometry_recoveries"] == 0
    assert result["tracks"][0]["track_id"] != previous


def test_tva43_normal_match_has_priority_and_low_recovery_is_unchanged(tva43):
    original = fast_box()
    previous = sample(tva43, 0, [original])["tracks"][0]["track_id"]
    result = sample(tva43, .125, [fast_box(.35), original])
    matched = next(t for t in result["tracks"] if t["track_id"] == previous)
    assert matched["association"] == "bytetrack" and matched["xyxy"] == original["xyxy"]
    assert result["geometry_recoveries"] == 0
    weak = {**original, "confidence": .2}
    result = sample(tva43, .25, [weak])
    assert result["tracks"][0]["track_id"] == previous
    assert result["tracks"][0]["observation"] == "low_recovery"
    assert result["geometry_recoveries"] == 0


def test_geometry_recovery_does_not_change_other_cameras(setup):
    previous = sample(setup, 0, [fast_box()])["tracks"][0]["track_id"]
    result = sample(setup, 1/6, [fast_box(.325, .66)])
    assert result["association_policy"] == "bytetrack-iou-v1"
    assert result["geometry_recoveries"] == 0
    assert result["tracks"][0]["track_id"] != previous
    assert "association" not in result["tracks"][0]


def test_tva43_geometry_recovery_survives_duplicate_frame_engine_reset(tva43):
    sample(tva43, 0, [fast_box()], nonce="same")
    assert sample(tva43, .125, [fast_box()], nonce="same")["tracks"] == []
    first = sample(tva43, .25, [fast_box()], nonce="fresh")["tracks"][0]
    result = sample(tva43, .375, [fast_box(.325, .66)], nonce="another")
    assert result["tracks"][0]["track_id"] == first["track_id"]
    assert result["geometry_recoveries"] == 1
