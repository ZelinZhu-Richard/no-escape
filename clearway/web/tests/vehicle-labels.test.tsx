import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LiveImageBoxes } from "../src/LiveImageDetections";
import type { ImageDetections, LiveImageBox } from "../src/liveCameras";

const car: LiveImageBox = {
  class_name: "car",
  confidence: 0.873,
  xyxy: [0.2, 0.3, 0.35, 0.5],
  track_id: "bt-session-17",
  observation: "high",
  confirmed: true,
};
const detections = (boxes = [car]): ImageDetections => ({
  status: "available",
  analysis_mode: "fresh",
  image_sha256: "ab".repeat(32),
  image_width: 640,
  image_height: 480,
  boxes,
  vehicle_count: boxes.filter((box) => box.class_name !== "person").length,
  person_count: boxes.filter((box) => box.class_name === "person").length,
  model: { name: "YOLO11s", version: "test" },
  provenance: {
    kind: "local_yolo_image",
    fixture: false,
    image_sha256: "ab".repeat(32),
    analyzed_at: "2026-11-07T23:00:00Z",
  },
  inference_ms: 50,
});
let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  (globalThis as typeof globalThis & {
    IS_REACT_ACT_ENVIRONMENT: boolean;
  }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
const textLines = () => [...container.querySelectorAll("text")]
  .map((element) => element.textContent);

describe("vehicle confidence and speed labels", () => {
  it("labels actual detector confidence beside the box without implying a speed", async () => {
    await act(async () => root.render(<LiveImageBoxes detections={detections()} />));
    expect(textLines()).toEqual(["87%"]);
    expect(container.querySelector("title")?.textContent).toBe(
      "car #17; detector confidence 87%",
    );
    const label = container.querySelector(".detection-label-bg")!;
    expect(Number(label.getAttribute("x"))).toBeGreaterThan(car.xyxy[2] * 640);
    expect(Number(label.getAttribute("y"))).toBe(car.xyxy[1] * 480);
    expect(Number(container.querySelector("text")!.getAttribute("font-size")))
      .toBeLessThan(640 / 30);
  });

  it("joins speed to its exact track ID and distinguishes estimates from detector confidence", async () => {
    const other = { ...car, track_id: "bt-session-18", confidence: 0.21 };
    await act(async () => root.render(
      <LiveImageBoxes detections={detections([car, other])} speeds={{
        [car.track_id!]: { mph: 37.8, reason: "estimated" },
        [other.track_id]: { mph: null, reason: "collecting observations" },
      }} />,
    ));
    expect(textLines()).toEqual([
      "21% · —",
      "87%", "est 38 mph",
    ]);
    expect(container.querySelector('[data-track-id="bt-session-17"] title')?.textContent)
      .toBe("car #17; detector confidence 87%; estimated speed 38 mph");
    expect(container.querySelector('[data-track-id="bt-session-18"] title')?.textContent)
      .toContain("speed unavailable: collecting observations");
  });

  it("never substitutes another ID's speed or attaches vehicle speed to a person", async () => {
    const person = { ...car, class_name: "person", track_id: "bt-session-20" };
    const untracked = { ...car, track_id: undefined };
    await act(async () => root.render(
      <LiveImageBoxes detections={detections([car, person, untracked])} speeds={{
        "bt-other-17": { mph: 52, reason: "estimated" },
        [person.track_id]: { mph: 12, reason: "invalid vehicle input" },
      }} />,
    ));
    expect(textLines()).toEqual([
      "87% · —",
      "87%",
      "87% · —",
    ]);
    expect(container.querySelector('.detection-person title')?.textContent)
      .not.toContain("speed");
  });

  it.each([NaN, Infinity, -1])("does not render an invalid numeric speed: %s", async (mph) => {
    await act(async () => root.render(
      <LiveImageBoxes detections={detections()} speeds={{
        [car.track_id!]: { mph, reason: "invalid" },
      }} />,
    ));
    expect(textLines()).toEqual(["87% · —"]);
    expect(textLines().join(" ")).not.toContain("mph");
  });

  it("keeps side labels inside the image and uses the left side at the right edge", async () => {
    const edge = { ...car, xyxy: [0.85, 0.96, 1, 1] as LiveImageBox["xyxy"] };
    await act(async () => root.render(
      <LiveImageBoxes detections={detections([edge])} speeds={{
        [edge.track_id!]: { mph: 0, reason: "estimated" },
      }} />,
    ));
    const label = container.querySelector(".detection-label-bg")!;
    const x = Number(label.getAttribute("x"));
    const y = Number(label.getAttribute("y"));
    const width = Number(label.getAttribute("width"));
    const height = Number(label.getAttribute("height"));
    expect(x).toBeGreaterThanOrEqual(0);
    expect(y).toBeGreaterThanOrEqual(0);
    expect(x + width).toBeLessThan(edge.xyxy[0] * 640);
    expect(y + height).toBeLessThanOrEqual(480);
    expect(textLines()).toContain("est 0 mph");
  });

  it("preserves boxes and exclusion markings when labels are hidden", async () => {
    const data = detections();
    data.excluded_regions = [{ id: "title", xyxy: [0, 0, 0.4, 0.1] }];
    await act(async () => root.render(
      <LiveImageBoxes detections={data} labels={false} speeds={{
        [car.track_id!]: { mph: 38, reason: "estimated" },
      }} />,
    ));
    expect(textLines()).toEqual([]);
    expect(container.querySelector(".detection-label-bg")).toBeNull();
    expect(container.querySelectorAll(".detection-box")).toHaveLength(1);
    expect(container.querySelectorAll(".live-excluded-region")).toHaveLength(1);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
