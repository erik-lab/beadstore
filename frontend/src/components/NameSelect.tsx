import { useEffect, useRef, useState } from "react";

const OTHER_VALUE = "__other__";

/**
 * Pick an existing name from a dropdown, or type a new one.
 *
 * Inventory import stages names rather than IDs, so this works in names
 * throughout. It exists because a free-text box is no help when the import
 * flags a value as new: the whole point is to be able to open the list and
 * find what it should have matched.
 *
 * A value that isn't in the list is kept as a selected option of its own,
 * labelled "(new)", so an imported spelling is never silently dropped just
 * because nothing matches it.
 */
export function NameSelect({
  value,
  options,
  onChange,
  disabled,
  blankLabel = "None",
  newLabel = "Type a different name...",
  id,
}: {
  value: string;
  /** Existing names, as offered in the dropdown. */
  options: string[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Label for the empty choice. */
  blankLabel?: string;
  newLabel?: string;
  id?: string;
}) {
  const [typing, setTyping] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  // Focus the box the moment "type a different name" is chosen, so the choice
  // flows straight into typing without a second click.
  useEffect(() => {
    if (typing) inputRef.current?.focus();
  }, [typing]);

  // Matched case-insensitively, but the select has to be given the option's
  // own spelling or the browser shows it as blank. Imports arrive in whatever
  // case the source used, so "beads" has to select the "Beads" option.
  const canonical = options.find((option) => option.toLowerCase() === value.toLowerCase());
  const unmatched = value !== "" && canonical === undefined;

  function commitTyped() {
    setTyping(false);
    const trimmed = draft.trim();
    if (trimmed !== value) onChange(trimmed);
  }

  if (typing) {
    return (
      <div className="line-row" style={{ gap: 4 }}>
        <input
          ref={inputRef}
          id={id}
          value={draft}
          disabled={disabled}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitTyped}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commitTyped();
            }
            if (e.key === "Escape") {
              setDraft(value);
              setTyping(false);
            }
          }}
        />
        <button
          type="button"
          className="btn-secondary"
          // onMouseDown, not onClick: the input's onBlur would otherwise fire
          // first and commit the very text this is meant to abandon.
          onMouseDown={(e) => {
            e.preventDefault();
            setDraft(value);
            setTyping(false);
          }}
          disabled={disabled}
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <select
      id={id}
      value={canonical ?? (unmatched ? value : "")}
      disabled={disabled}
      onChange={(e) => {
        if (e.target.value === OTHER_VALUE) {
          setDraft(value);
          setTyping(true);
          return;
        }
        onChange(e.target.value);
      }}
    >
      <option value="">{blankLabel}</option>
      {unmatched && <option value={value}>{value} (new)</option>}
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
      <option value={OTHER_VALUE}>{newLabel}</option>
    </select>
  );
}
