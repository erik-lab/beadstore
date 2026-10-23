# Inventory Intake (Import Inventory)

## The requirement

Patti sources inventory from whatever the supplier or the moment hands her:
vendor spreadsheets, order emails, Word documents, PDF invoices, photos of
packing slips, and notes she writes (or says) to herself. Her ask:

- accept input from **any** of those sources
- take a **best-efforts** pass at populating a preliminary set of records
- **flag what's missing**
- let her **edit before anything is committed** to the database
- let her **speak** an entry and have it parsed the same way as a document

## The shape of the solution

One funnel, not one importer per format.

```
spreadsheet ─┐
Word doc ────┤
pasted note ─┼──→ extract to text ──┐
dictation ───┘                      ├──→ one AI parse ──→ draft rows ──→ review/edit ──→ commit
PDF / photo ────────────────────────┘                      (staged)        (gaps flagged)   │
                                     (sent to the model natively)                           ▼
                                                                            products + inventory_units
```

Every source becomes either text or a native document/image block, and then
goes through **the same parser** into the same staging tables. That's what
makes "speak an entry and have it parsed like a document" true rather than a
separate feature: dictation is transcribed in the browser and posted as text.

### Why staging tables rather than a draft in the browser

Parsed records are parked in `inventory_intake_batches` / `inventory_intake_rows`
until explicitly committed. The alternative — hold the draft in the browser and
post finished records — was rejected because:

- a 60-row spreadsheet review is not a single sitting; it has to survive a
  closed tab, and a different device
- the gap flags have to be computed by the same code that enforces them at
  commit, or they drift
- a partial commit (12 rows good, 3 still murky) needs somewhere for the 3 to
  live

### Why names, not IDs, in the staging rows

The parser produces words ("Fire Mountain Gems"), and the reviewer edits
words. Resolving those to `category_id` / `vendor_id` / `location_id` /
`product_id` happens once, at commit, where it can fail per row with a
readable reason. `unit_type` is a plain string in staging for the same reason:
a bad guess should reach the review screen to be corrected, not fail an insert.

## Gap flagging

`compute_missing_fields()` is the single source of truth, recomputed on every
write and **never accepted from the client**. A row with no missing fields is
a row that will commit. Required:

| Field | Why |
|---|---|
| `product_name` | unless the row matched an existing product |
| `category_name` | `products.category_id` is NOT NULL; skipped when matched |
| `quantity` | must be > 0 |
| `unit_type` | must be a real `UnitType` value |
| `received_date` | `inventory_units.received_date` is NOT NULL |

Anything else the parser didn't find is simply absent — it doesn't block a
commit, because a bead with no recorded finish is still a bead.

The model is instructed to emit `null` rather than guess. A null becomes a
flagged gap, which is useful; a plausible-looking invention is not.

## Per-field match indicators

The batch-level `will_create` list says *that* a new vendor would appear; it
doesn't say *which row* has the odd spelling. So each row also carries a
per-field verdict (`name_matches`) for the four names that resolve to master
data — product, category, vendor, location:

| Verdict | Shown as | Means |
|---|---|---|
| `existing` | muted "on file" | matches something already on file, case-insensitively |
| `new` | amber "new" + amber field text | nothing matches, so committing creates it |
| `ambiguous` | red "matches more than one" | the name matches 2+ active products, so it can't be auto-matched |

A blank field gets no verdict rather than a misleading "new".

`new` is deliberately *not* styled as an error — creating a new vendor is
often exactly right. It's colored, not outlined, to distinguish it from the
"needed" outline that marks a genuine blocker.

Resolved in **bulk**: a handful of statements for the whole batch rather than
four queries per row, so a 200-row review doesn't become a thousand round
trips. Products are counted rather than just matched, because two products
sharing a name is ambiguity for the reviewer to settle.

### Re-matching on edit

For the indicator to be honest, correcting a name has to re-run the match —
otherwise fixing "8mm Rnd Czech Gls" to "8mm Round Czech Glass" would change
the text while the badge kept saying "new", and the commit would create a
duplicate product anyway. So:

- Editing `product_name` or `category_name` re-resolves `matched_product_id`.
  A renamed row gives up a previous *auto*-match, since that match described a
  different name. An explicit `matched_product_id` sent in the same request
  wins.
- A bulk category fill re-resolves only rows that aren't already tied to a
  product — filling in a category shouldn't undo a deliberate pick. This is
  genuinely useful: a source with no category column can't have its product
  names scoped until the category is set.

## Commit semantics

- Each row commits in **its own savepoint**, so one bad row can't discard the
  rest of the import. Failures come back with `commit_error` set and stay in
  the batch for another try.
- Error text is written *outside* the savepoints — a rollback would otherwise
  undo the very explanation the reviewer needs.
- An exact name match against an existing active product (within the category,
  case-insensitive) sets `matched_product_id`, so re-importing a familiar item
  **adds stock** instead of creating a near-duplicate product. Two matches is
  ambiguity, and is left for the reviewer rather than resolved by guessing.
- Categories, vendors and locations are matched case-insensitively and created
  if absent. Because that's how you end up with "Fire Mtn Gems" *and* "Fire
  Mountain Gems", the review screen lists exactly what would be created
  (`will_create`) before the commit, so a typo gets fixed instead of enshrined.
- Subtypes are scoped to a category and curated, so an unrecognized one becomes
  `custom_subtype` — the same thing the product form does for "Other".
- A SKU already in use is dropped rather than failing the row: the stock is the
  point, the code is a bonus, and `products.sku` is UNIQUE.

## Staging and the audit log

`AuditMixin` does two jobs: stamping who touched a record, and writing the
audit trail. Staging rows want only the first — a 100-row import plus its edits
would bury the entries that matter. Both intake models set `__audit__ = False`
(a new opt-out honored by the `before_flush` listener) and still get
`created_by`/`updated_by`. The products and inventory units a commit creates
are audited as usual, which is the record that matters.

## Voice

Transcription is **browser-side**, via the Web Speech API, not a server audio
upload:

- the audio never leaves her machine
- no audio upload, storage or transcription service to pay for or secure
- the result is plain text, so it goes through the identical parser

The trade-off is browser support: Chrome, Edge and Safari yes, **Firefox no**.
The page checks for the API and, when it's absent, says so and points at the
text box — which costs nothing, because the text box is already there for
pasting. Dictation is continuous with interim results, so she can speak several
items in one go and watch the words land, then tidy the wording before parsing.

A batch dictated this way is recorded as `source_kind='voice'`, and the parser
gets an extra hint that the source may be conversational, unpunctuated, or
carry speech-recognition errors in names and numbers.

## Format handling

| Source | How |
|---|---|
| `.csv`, `.tsv` | sniffed delimiter, normalized to tab-separated rows |
| `.xlsx`, `.xlsm` | openpyxl, every sheet, `data_only` so formulas come through as values |
| `.docx` | stdlib `zipfile` + `ElementTree` over `word/document.xml`; tables flattened to tab-separated rows |
| `.html` | tags stripped (a saved email, usually) |
| `.txt`, `.md`, `.json` | decoded as-is |
| `.pdf`, images | **not** extracted — handed to the model as a native document/image block |

Extension wins over the browser's declared MIME type, because browsers report
`.csv` as anything from `text/csv` to `application/vnd.ms-excel` depending on
what's installed locally, which would otherwise send a plain CSV down the
openpyxl path.

`openpyxl` is the one new dependency, imported lazily: a virtualenv without it
still serves every other format, and `.xlsx` returns a 503 that says to run
`pip install -r requirements.txt` or save as `.csv`.

Limits: ~120,000 characters of extracted text, 2,000 spreadsheet rows, 200
parsed rows per batch, ~7MB per file, and 80MB uncompressed from an Office zip
(so a zip bomb is refused rather than inflated). Each one reports what to do
instead rather than truncating silently.

## Priming the parser with the shop's own vocabulary

The system prompt carries the real category list, subtypes, known vendors and
locations, and the seeded attribute pick-list values. Without it the parser
invents synonyms ("czech glass" / "Czech Glass" / "Bohemian glass") and
fragments the pick lists that the product form depends on. The attributes
sub-schema is generated from `product_service.ATTRIBUTE_FIELDS`, so adding a
product attribute column can't silently leave the parser unable to fill it —
there's a test pinning that.

Source material is also explicitly framed as data: the prompt says to ignore
any instructions contained in the source itself. A supplier spreadsheet is not
a place to take direction from.

## API

All under `/api/v1/inventory-intake`, staff-authenticated:

| Endpoint | Does |
|---|---|
| `POST /parse-text` | typed/pasted/dictated text → draft batch |
| `POST /parse-file` | base64 file → draft batch |
| `GET /batches` | recent imports |
| `GET /batches/{id}` | batch with rows and `will_create` |
| `PATCH /batches/{id}/rows` | apply shared values to every open row |
| `POST /batches/{id}/commit` | commit every ready row |
| `DELETE /batches/{id}` | discard (kept as `discarded` if anything was committed) |
| `PATCH /rows/{id}` | edit one row (re-runs product matching if the name or category changed) |
| `POST /rows/{id}/skip` | exclude a row, or put it back |

Files arrive as base64 in JSON rather than multipart, matching how the
order-email scan already submits attachments and keeping `python-multipart`
out of the dependency list.

## UI

- **Import Inventory** (`/inventory-import`) — paste/dictate box, file picker,
  and the list of recent imports.
- **Review Import** (`/inventory-import/:id`) — counts, parser notes, the
  `will_create` confirmation, a "fill in for every row" control, and one
  editable card per row with gaps outlined and labelled "needed".

Two deliberate choices in the review screen:

- **Save on blur.** Edits round-trip as a field loses focus, and the server's
  response replaces the row — so the gap flags, match badges and status on
  screen are always the server's verdict, not a local approximation. This is
  what makes a match badge flip from "new" to "on file" the moment a spelling
  is corrected.
- **"Fill in for every row."** Spreadsheets routinely omit the received date,
  vendor or location for every row because it was obvious in context. Filling
  those one row at a time would be the most tedious part of the review.

## Not built

- **Re-parse an existing batch.** `raw_text` is stored for it, but there's no
  endpoint yet. Worth adding after the prompt has seen real sources.
- **Multi-file import in one batch.** One file at a time today.
- **Duplicate detection across batches.** Importing the same spreadsheet twice
  creates two sets of inventory units; nothing warns about it. Matching on
  product name does at least mean it won't also create duplicate *products*.
- **Fuzzy name matching.** Product/vendor/category matching is exact (case
  insensitive). "Fire Mtn Gems" vs "Fire Mountain Gems" is *flagged* per field
  as `new` for a human to correct, but the code won't guess that the two are
  the same thing. Edit-distance suggestions ("did you mean...?") would be the
  natural next step if the flagging turns out not to be enough.

## Untested against reality

The parse quality itself has not been measured on Patti's real sources — the
AI call is stubbed in tests, and no live Anthropic call has been made from
this work. Everything around the parse (extraction, gap flagging, match
indicators, editing, per-row commit isolation, audit behavior) is covered by
74 tests. The first
real spreadsheet she imports is the actual test of the prompt, and the
`parser_notes` field exists so the model can say what confused it.
