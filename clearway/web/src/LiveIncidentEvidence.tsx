import { useEffect, useState } from "react";
import type { Incident } from "./types";
import { LiveDetectionCounts, LiveImageBoxes } from "./LiveImageDetections";

/** The server freezes this exact image and detection result together for this run. */
export function LiveIncidentEvidence({ incident }: { incident: Incident }) {
  const evidence = incident.live_evidence;
  const [image, setImage] = useState<{
    source: string;
    hash: string;
    url: string;
  } | null>(null);
  const [failedImage, setFailedImage] = useState<string | null>(null);
  const source = evidence?.image_url;
  const hash = evidence?.detections.image_sha256;
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | undefined;
    setImage(null);
    setFailedImage(null);
    if (source && hash)
      void (async () => {
        try {
          const response = await fetch(source, { signal: controller.signal });
          if (!response.ok) throw new Error("Evidence image unavailable");
          const bytes = await response.arrayBuffer();
          if (bytes.byteLength > 1_100_000)
            throw new Error("Evidence image too large");
          const digest = await crypto.subtle.digest("SHA-256", bytes);
          const actualHash = Array.from(new Uint8Array(digest), (byte) =>
            byte.toString(16).padStart(2, "0"),
          ).join("");
          if (actualHash !== hash)
            throw new Error("Evidence identity mismatch");
          if (controller.signal.aborted) return;
          objectUrl = URL.createObjectURL(
            new Blob([bytes], { type: "image/jpeg" }),
          );
          setImage({ source, hash, url: objectUrl });
        } catch {
          if (!controller.signal.aborted) setFailedImage(source);
        }
      })();
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [source, hash]);
  const verifiedImage =
    image &&
    image.source === source &&
    image.hash === hash &&
    failedImage !== source
      ? image
      : null;
  return (
    <section
      className="live-incident-evidence"
      aria-label="Live camera incident evidence"
    >
      <div className="live-incident-image">
        {verifiedImage && evidence ? (
          <>
            <img
              key={verifiedImage.url}
              src={verifiedImage.url}
              alt={`Frozen trigger frame from ${incident.live_source?.title ?? incident.source_id}`}
              onError={() => setFailedImage(evidence.image_url)}
            />
            <LiveImageBoxes detections={evidence.detections} labels={false} />
          </>
        ) : (
          <p className="live-incident-unavailable">
            {failedImage === source || !source
              ? "The trigger image is unavailable. Review the observations and remaining unknowns."
              : "Verifying saved trigger frame…"}
          </p>
        )}
        <span className="live-incident-image-label">
          PUBLIC CCTV · FROZEN EVIDENCE
        </span>
      </div>
      {evidence && (
        <div className="live-incident-facts">
          <LiveDetectionCounts detections={evidence.detections} />
          <dl>
            <div>
              <dt>Camera</dt>
              <dd>{incident.live_source?.title ?? incident.source_id}</dd>
            </div>
            <div>
              <dt>Received at</dt>
              <dd>
                <time dateTime={evidence.observed_at}>
                  {new Date(evidence.observed_at).toLocaleString()}
                </time>
              </dd>
            </div>
            <div>
              <dt>Rule window</dt>
              <dd>
                {evidence.window_seconds.toFixed(1)} seconds ·{" "}
                {evidence.rule.replaceAll("_", " ")}
              </dd>
            </div>
            <div>
              <dt>Video clock</dt>
              <dd>{evidence.media_time_seconds.toFixed(1)} seconds</dd>
            </div>
          </dl>
          <p>{evidence.summary}</p>
          <small>
            A local visual rule raised this candidate. Camera position is known;
            object position, cause and severity require review. Provider capture
            time may be delayed.
          </small>
        </div>
      )}
    </section>
  );
}
