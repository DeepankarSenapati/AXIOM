import { validateWarRoomResponse } from "./warRoomEvidence.js";

export const REVIEW_DECISIONS = [
  { value: "investigate", label: "Needs more testing" },
  { value: "next_review", label: "Ready for another review" },
  { value: "undecided", label: "Undecided" },
];

// This is a local record of the review, not an authenticated audit or a
// recommendation. User notes are included only in the file they choose to save.
export function buildWarRoomCase(scenario, review, decision, notes) {
  if (!scenario || typeof scenario !== "object" || Array.isArray(scenario)) throw new Error("The scenario is unavailable.");
  if (!review || !["scripted", "claude"].includes(review.mode)) throw new Error("The review is unavailable.");
  validateWarRoomResponse(review, review.fingerprint, review.mode);
  if (!REVIEW_DECISIONS.some((item) => item.value === decision)) throw new Error("Choose a review outcome.");
  if (typeof notes !== "string" || notes.length > 500) throw new Error("Notes must be 500 characters or fewer.");
  return {
    format: "axiom-war-room-case-v1",
    notice: "Synthetic simulation. The review, fingerprint, and notes are not an independent audit, proof of execution, or trading advice.",
    scenario,
    fingerprint: review.fingerprint,
    engine_version: review.engine_version,
    review_mode: review.mode,
    model: review.model,
    perspectives: review.messages,
    evidence: review.evidence,
    limitations: review.limitations,
    human_review: { outcome: decision, notes },
  };
}
