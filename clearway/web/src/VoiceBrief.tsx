import { useEffect, useRef, useState } from "react";
import type { Incident } from "./types";

export function buildVoiceBrief(incident: Incident): string {
  const live = incident.source_mode === "live";
  const origin = live
    ? "A local visual rule raised this public-camera candidate. It is not a confirmed emergency."
    : incident.analysis_mode === "fixture"
      ? "Fixture observations, not model-generated analysis."
      : `${incident.analysis_mode === "cached" ? "Saved" : "Fresh"} model observations, subject to human review.`;
  const review =
    incident.review_status === "candidate"
      ? "Awaiting operator confirmation."
      : `Operator review status: ${incident.review_status}.`;
  const evidence = incident.evidence
    .map(
      (item) =>
        `At ${live ? "video clock " : ""}${item.timestamp_seconds} seconds: ${item.observation}`,
    )
    .join(" ");
  const location =
    incident.location.quality === "simulated"
      ? "Map placement is simulated. The filming location is unknown."
      : `Camera context: ${incident.location.label}. This is not a measured object location.`;
  const unknowns = incident.unknowns.length
    ? `Still unknown: ${incident.unknowns.join("; ")}.`
    : live
      ? "Cause and severity remain unverified."
      : "Original location and capture time remain unverified.";
  return `Clearway ${live ? "public-camera brief. Frozen evidence from a live feed." : "demonstration. Recorded footage."} ${origin} ${review} ${incident.title}. ${evidence} ${location} ${unknowns} This demonstration does not dispatch responders.`;
}

export function VoiceBrief({
  incident,
  disabled = false,
}: {
  incident: Incident;
  disabled?: boolean;
}) {
  const [speaking, setSpeaking] = useState(false);
  const [message, setMessage] = useState("");
  const active = useRef<SpeechSynthesisUtterance | null>(null);
  const supported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;
  const text = buildVoiceBrief(incident);

  useEffect(() => {
    const stop = () => {
      if (active.current) {
        active.current.onend = null;
        active.current.onerror = null;
        active.current = null;
        window.speechSynthesis.cancel();
      }
      setSpeaking(false);
    };
    stop();
    setMessage("");
    const onVisibility = () => {
      if (document.visibilityState === "hidden") stop();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
    };
  }, [text, incident.run_id, incident.id, disabled]);

  const toggle = () => {
    if (!supported || disabled) return;
    if (active.current) {
      active.current.onend = null;
      active.current.onerror = null;
      active.current = null;
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    setMessage("");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 1;
    const localVoice = window.speechSynthesis
      .getVoices()
      .find((voice) => voice.localService && voice.lang.startsWith("en"));
    if (localVoice) utterance.voice = localVoice;
    utterance.onend = () => {
      if (active.current !== utterance) return;
      active.current = null;
      setSpeaking(false);
    };
    utterance.onerror = () => {
      if (active.current !== utterance) return;
      active.current = null;
      setSpeaking(false);
      setMessage("Voice could not play. The complete brief remains below.");
    };
    active.current = utterance;
    setSpeaking(true);
    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      active.current = null;
      setSpeaking(false);
      setMessage("Voice could not play. The complete brief remains below.");
    }
  };

  return (
    <div className="voice-brief">
      <button
        className="voice-button"
        onClick={toggle}
        disabled={disabled || !supported}
        aria-pressed={speaking}
        data-testid="voice-brief"
      >
        <svg
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          {speaking ? (
            <rect x="6" y="6" width="12" height="12" rx="1" />
          ) : (
            <>
              <path d="M11 4 6 8H3v8h3l5 4V4Z" />
              <path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" />
            </>
          )}
        </svg>
        {speaking ? "Stop voice brief" : "Listen to brief"}
      </button>
      <span className="voice-caption" role="status">
        {message ||
          (supported
            ? "Reads this evidence and its unknowns."
            : "Voice unavailable in this browser.")}
      </span>
    </div>
  );
}
