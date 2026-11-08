import { describe, expect, it } from "vitest";
import {
  extractSceneSignature,
  matchSceneSignatures,
  type ScenePatch,
  type SceneSignature,
} from "../src/speedSceneGuard";

const width = 160, height = 120;
const patches: ScenePatch[] = [
  [0.04, 0.04, 0.4, 0.43],
  [0.56, 0.04, 0.96, 0.43],
  [0.04, 0.57, 0.4, 0.96],
  [0.56, 0.57, 0.96, 0.96],
];
const texture = (x: number, y: number) => Math.round(
  120 + 35 * Math.sin(x * 0.15) + 28 * Math.cos(y * 0.19) +
  18 * Math.sin(x * 0.09 + y * 0.17),
);
const image = (
  transform = (value: number, _x: number, _y: number) => value,
  channels = 4,
  w = width,
  h = height,
) => {
  const pixels = new Uint8ClampedArray(w * h * channels);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const value = transform(texture(x * width / w, y * height / h), x, y);
      const offset = (y * w + x) * channels;
      pixels[offset] = value;
      pixels[offset + 1] = value;
      pixels[offset + 2] = value;
      if (channels === 4) pixels[offset + 3] = 255;
    }
  }
  return pixels;
};
const signature = (pixels = image(), regions = patches) =>
  extractSceneSignature(pixels, width, height, regions)!;

describe("fixed camera background signature guard", () => {
  it("extracts bounded grayscale samples and matches RGB and RGBA without retaining frame pixels", () => {
    const rgba = signature();
    const rgb = signature(image(undefined, 3));
    expect(rgba.patches).toHaveLength(4);
    expect(rgba.patches.every((patch) => patch.samples.length === 64)).toBe(true);
    expect(matchSceneSignatures(rgba, rgb).matches).toBe(true);
    expect(matchSceneSignatures(rgba, rgb).score).toBeCloseTo(1);
    expect(Object.keys(rgba).sort()).toEqual(["aspectRatio", "patches", "version"]);
  });

  it("tolerates modest lighting changes and deterministic pixel noise", () => {
    const changed = signature(image((value, x, y) =>
      value * 0.8 + 28 + ((x * 13 + y * 7) % 9 - 4),
    ));
    const result = matchSceneSignatures(changed, signature());
    expect(result.matches).toBe(true);
    expect(result.score).toBeGreaterThan(0.98);
  });

  it("matches a proportionately resized view", () => {
    const doubled = extractSceneSignature(image(undefined, 4, width * 2, height * 2),
      width * 2, height * 2, patches);
    expect(matchSceneSignatures(doubled, signature()).matches).toBe(true);
  });

  it("rejects translation and mirrored background arrangement", () => {
    for (const transformed of [
      image((_value, x, y) => texture(x + 15, y + 10)),
      image((_value, x, y) => texture(width - x - 1, y)),
    ]) {
      const result = matchSceneSignatures(signature(transformed), signature());
      expect(result.matches).toBe(false);
      expect(result.score).toBeLessThan(0.88);
    }
  });

  it("requires three agreeing patches: one changed patch is tolerated, two are rejected", () => {
    const reference = signature();
    const altered = structuredClone(reference);
    altered.patches[0].samples.reverse();
    expect(matchSceneSignatures(altered, reference).matches).toBe(true);
    altered.patches[1].samples.reverse();
    expect(matchSceneSignatures(altered, reference).matches).toBe(false);
    const three = signature(image(), patches.slice(0, 3));
    const changedThree = structuredClone(three);
    changedThree.patches[0].samples.reverse();
    expect(matchSceneSignatures(changedThree, three).matches).toBe(false);
  });

  it("fails closed for unknown, malformed, flat or transparent image data", () => {
    expect(matchSceneSignatures(null, signature())).toEqual({ matches: false, score: null });
    expect(extractSceneSignature(image(), width + 1, height, patches)).toBeNull();
    expect(extractSceneSignature(image(), NaN, height, patches)).toBeNull();
    expect(signature(image(() => 128))).toBeNull();
    const transparent = image();
    for (let i = 3; i < transparent.length; i += 4) transparent[i] = 0;
    expect(signature(transparent)).toBeNull();
    expect(extractSceneSignature(image(), width, height, patches.slice(0, 2))).toBeNull();
    const broken = structuredClone(signature());
    broken.patches[0].samples[0] = NaN;
    expect(matchSceneSignatures(broken, signature())).toEqual({ matches: false, score: null });
    broken.patches[0].samples.fill(128);
    expect(matchSceneSignatures(broken, signature()).matches).toBe(false);
    expect(matchSceneSignatures({} as SceneSignature, signature()).matches).toBe(false);
  });

  it("fails closed for invalid patch bounds, small patches, changed rectangles or aspect ratio", () => {
    for (const rect of [
      [-0.01, 0, 0.4, 0.4], [0, 0, 1.01, 0.4], [0.4, 0, 0.3, 0.4],
      [0, 0, 0.001, 0.001], [0, NaN, 0.4, 0.4],
    ] as ScenePatch[]) {
      expect(signature(image(), [rect, ...patches.slice(1)])).toBeNull();
    }
    const changedRect = structuredClone(signature());
    changedRect.patches[0].rect = [0.05, 0.04, 0.4, 0.43];
    expect(matchSceneSignatures(changedRect, signature()).score).toBeNull();
    const stretched = { ...signature(), aspectRatio: 16 / 9 };
    expect(matchSceneSignatures(stretched, signature()).score).toBeNull();
  });

  it("rejects excessive brightness changes even with perfect normalized correlation", () => {
    const reference = signature();
    const changed = structuredClone(reference);
    changed.patches.forEach((patch) => {
      patch.samples = patch.samples.map((value) => value * 0.5 + 140);
    });
    expect(matchSceneSignatures(changed, reference).matches).toBe(false);
  });
});
