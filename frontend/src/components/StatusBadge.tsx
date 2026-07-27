const TONE_BY_STATUS: Record<string, string> = {
  active: "tone-good",
  available: "tone-good",
  matched: "tone-good",
  received: "tone-good",
  ready: "tone-good",
  published: "tone-good",

  draft: "tone-neutral",
  expected: "tone-neutral",
  reserved: "tone-neutral",

  submitted: "tone-info",
  partially_received: "tone-warn",
  shortage: "tone-warn",
  discrepancy: "tone-warn",
  pending: "tone-warn",

  overage: "tone-warn",
  substitution: "tone-warn",
  damaged: "tone-bad",
  unresolved: "tone-bad",
  missing_photos: "tone-warn",
  needs_pricing: "tone-warn",
  needs_description: "tone-warn",

  cancelled: "tone-muted",
  archived: "tone-muted",
  closed: "tone-muted",
  retired: "tone-muted",
  depleted: "tone-muted",
};

const LABEL_OVERRIDES: Record<string, string> = {
  submitted: "Ordered",
  partially_received: "Partially Received",
};

function toLabel(value: string): string {
  if (LABEL_OVERRIDES[value]) return LABEL_OVERRIDES[value];
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function StatusBadge({ status }: { status: string }) {
  const tone = TONE_BY_STATUS[status] ?? "tone-neutral";
  return <span className={`badge ${tone}`}>{toLabel(status)}</span>;
}
