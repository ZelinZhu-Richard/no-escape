// A conservative fixed-view check, not a general camera-motion detector.
// Only small grayscale background signatures are retained; no video frames.
export type ScenePatch = readonly [number, number, number, number];
export interface SceneSignature {
  version: "clearway-static-patches-v1";
  aspectRatio: number;
  patches: { rect: ScenePatch; samples: number[] }[];
}

const GRID = 8;
const MIN_STANDARD_DEVIATION = 4;
const MIN_CORRELATION = 0.88;
const MAX_MEAN_CHANGE = 60;
const MIN_CONTRAST_RATIO = 0.4;
const MAX_CONTRAST_RATIO = 2.5;
const OFFSETS = [-0.25, 0, 0.25];

function validRect(rect: ScenePatch): boolean {
  return Array.isArray(rect) && rect.length === 4 &&
    rect.every((value) => Number.isFinite(value) && value >= 0 && value <= 1) &&
    rect[0] < rect[2] && rect[1] < rect[3];
}

function moments(samples: readonly number[]) {
  if (samples.length !== GRID * GRID ||
      !samples.every((value) => Number.isFinite(value) && value >= 0 && value <= 255))
    return null;
  const mean = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  const centered = samples.map((value) => value - mean);
  const norm = Math.sqrt(centered.reduce((sum, value) => sum + value * value, 0));
  const deviation = norm / Math.sqrt(samples.length);
  return deviation >= MIN_STANDARD_DEVIATION
    ? { mean, centered, norm, deviation }
    : null;
}

/** Sample exactly 3–4 textured static-background rectangles in image space.
 * Invalid geometry, missing/transparent pixels or flat patches fail closed.
 * Input may be RGB or RGBA; its exact length determines the channel count.
 */
export function extractSceneSignature(
  pixels: ArrayLike<number>,
  width: number,
  height: number,
  patches: readonly ScenePatch[],
): SceneSignature | null {
  if (!Number.isInteger(width) || !Number.isInteger(height) ||
      width < GRID || height < GRID || width > 8192 || height > 8192 ||
      width * height > 16_000_000 || !pixels ||
      !Array.isArray(patches) || patches.length < 3 || patches.length > 4)
    return null;
  const channels = pixels.length / (width * height);
  if (channels !== 3 && channels !== 4) return null;
  const gray = (x: number, y: number) => {
    const offset = (y * width + x) * channels;
    const rgb = [pixels[offset], pixels[offset + 1], pixels[offset + 2]];
    if (!rgb.every((value) => Number.isFinite(value) && value >= 0 && value <= 255) ||
        (channels === 4 && pixels[offset + 3] !== 255))
      return NaN;
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  };
  const bilinear = (u: number, v: number) => {
    const x = u * (width - 1), y = v * (height - 1);
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const x1 = Math.min(width - 1, x0 + 1), y1 = Math.min(height - 1, y0 + 1);
    const dx = x - x0, dy = y - y0;
    return gray(x0, y0) * (1 - dx) * (1 - dy) +
      gray(x1, y0) * dx * (1 - dy) + gray(x0, y1) * (1 - dx) * dy +
      gray(x1, y1) * dx * dy;
  };
  const output: SceneSignature["patches"] = [];
  for (const rect of patches) {
    if (!validRect(rect) || (rect[2] - rect[0]) * width < GRID ||
        (rect[3] - rect[1]) * height < GRID)
      return null;
    const samples: number[] = [];
    for (let row = 0; row < GRID; row++) {
      for (let column = 0; column < GRID; column++) {
        let sum = 0;
        for (const dy of OFFSETS) {
          for (const dx of OFFSETS) {
            const u = rect[0] + (column + 0.5 + dx) / GRID * (rect[2] - rect[0]);
            const v = rect[1] + (row + 0.5 + dy) / GRID * (rect[3] - rect[1]);
            sum += bilinear(u, v);
          }
        }
        samples.push(Math.max(0, Math.min(255, sum / 9)));
      }
    }
    if (!moments(samples)) return null;
    output.push({ rect: [rect[0], rect[1], rect[2], rect[3]], samples });
  }
  return {
    version: "clearway-static-patches-v1",
    aspectRatio: width / height,
    patches: output,
  };
}

function validSignature(signature: SceneSignature | null | undefined): signature is SceneSignature {
  return !!signature && signature.version === "clearway-static-patches-v1" &&
    Number.isFinite(signature.aspectRatio) && signature.aspectRatio > 0 &&
    Array.isArray(signature.patches) &&
    signature.patches.length >= 3 && signature.patches.length <= 4 &&
    signature.patches.every((patch) => !!patch && validRect(patch.rect) &&
      Array.isArray(patch.samples) && moments(patch.samples) !== null);
}

/** Require all three patches, or at least three of four, to remain consistent.
 * Broad brightness/contrast tolerance handles modest lighting changes. A high
 * correlation does not prove an unchanged view; patterned backgrounds can
 * match after movement. Calibration must still be invalidated on known PTZ.
 */
export function matchSceneSignatures(
  current: SceneSignature | null | undefined,
  reference: SceneSignature | null | undefined,
): { matches: boolean; score: number | null } {
  const invalid = { matches: false, score: null };
  if (!validSignature(current) || !validSignature(reference) ||
      current.patches.length !== reference.patches.length ||
      Math.abs(current.aspectRatio / reference.aspectRatio - 1) > 0.01)
    return invalid;
  const scores: number[] = [];
  for (let index = 0; index < current.patches.length; index++) {
    const left = current.patches[index], right = reference.patches[index];
    if (left.rect.some((value, axis) => Math.abs(value - right.rect[axis]) > 1e-9))
      return invalid;
    const a = moments(left.samples)!, b = moments(right.samples)!;
    const contrast = a.deviation / b.deviation;
    if (Math.abs(a.mean - b.mean) > MAX_MEAN_CHANGE ||
        contrast < MIN_CONTRAST_RATIO || contrast > MAX_CONTRAST_RATIO) {
      scores.push(-1);
      continue;
    }
    const dot = a.centered.reduce((sum, value, i) => sum + value * b.centered[i], 0);
    scores.push(Math.max(-1, Math.min(1, dot / (a.norm * b.norm))));
  }
  scores.sort((a, b) => b - a);
  const score = scores[2];
  return { matches: score >= MIN_CORRELATION, score };
}
