import { useState } from "react";

/**
 * Small (i) icon shown next to a page element. Hovering shows the browser's
 * native tooltip (via `title`); clicking/tapping toggles a small popover so
 * it also works on touch devices where hover doesn't apply.
 */
export function InfoHint({ text }: { text: string | undefined }) {
  const [open, setOpen] = useState(false);

  if (!text) return null;

  return (
    <span className="info-hint">
      <button
        type="button"
        className="info-hint-icon"
        title={text}
        aria-label="More information"
        onClick={() => setOpen((prev) => !prev)}
      >
        i
      </button>
      {open && (
        <span className="info-hint-popover" role="tooltip">
          {text}
        </span>
      )}
    </span>
  );
}
