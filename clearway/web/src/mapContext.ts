export interface CameraContextPoint {
  id: string;
  name: string;
  description: string;
  latitude: number;
  longitude: number;
  quality: "official_inventory";
  status: "metadata_only";
}

export interface CameraContext {
  status: "available" | "unavailable";
  mode: "inventory_snapshot";
  fetched_at: string | null;
  source_updated_at: string | null;
  stale: boolean;
  attribution: string;
  source_url: string | null;
  points: CameraContextPoint[];
}

// Do not turn malformed or ambiguous inventory into apparently live map data.
export function readCameraContext(value: unknown): CameraContext | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  if (raw.mode !== "inventory_snapshot" || !["available", "unavailable"].includes(String(raw.status))
    || !Array.isArray(raw.points) || raw.points.length > 100) return null;
  const points: CameraContextPoint[] = [];
  const ids = new Set<string>();
  for (const item of raw.points) {
    if (!item || typeof item !== "object") continue;
    const point = item as Record<string, unknown>;
    if (typeof point.id !== "string" || !point.id || ids.has(point.id)
      || typeof point.name !== "string" || typeof point.description !== "string"
      || typeof point.latitude !== "number" || !Number.isFinite(point.latitude) || Math.abs(point.latitude) > 90
      || typeof point.longitude !== "number" || !Number.isFinite(point.longitude) || Math.abs(point.longitude) > 180
      || point.quality !== "official_inventory" || point.status !== "metadata_only") continue;
    points.push(point as unknown as CameraContextPoint);
    ids.add(point.id);
  }
  let sourceUrl: string | null = null;
  if (typeof raw.source_url === "string") {
    try {
      const parsed = new URL(raw.source_url);
      if (parsed.protocol === "https:" && !parsed.username && !parsed.password) sourceUrl = parsed.href;
    } catch { /* Missing source link does not establish a source. */ }
  }
  return {
    status: raw.status as CameraContext["status"], mode: "inventory_snapshot",
    fetched_at: typeof raw.fetched_at === "string" && Number.isFinite(Date.parse(raw.fetched_at)) ? raw.fetched_at : null,
    source_updated_at: typeof raw.source_updated_at === "string" && Number.isFinite(Date.parse(raw.source_updated_at)) ? raw.source_updated_at : null,
    stale: raw.stale !== false,
    attribution: typeof raw.attribution === "string" ? raw.attribution : "Inventory source unavailable",
    source_url: sourceUrl,
    points: raw.status === "available" ? points : [],
  };
}
