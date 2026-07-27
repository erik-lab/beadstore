# Erik Acceptance Click-Through Script

Run this locally against your Supabase-backed environment (per `README.md` setup). Each step
lists what to do and what you should see. If any step doesn't match, stop and report it rather
than continuing — later steps assume earlier ones worked.

## 1. Login/logout
- Visit the app while logged out. **Expect:** redirected to `/login`.
- Log in with your Supabase account. **Expect:** landed on the Dashboard.
- Click **Log out** in the sidebar. **Expect:** returned to `/login`; visiting any other URL
  directly also redirects back to login.

## 2. Create a vendor
- **Vendors → + New Vendor.** Name only, e.g. "Golden Thread Beads." Save.
- **Expect:** redirected to the vendor's detail page showing the name and an empty supplier
  order list.

## 3. Create a bead product
- **Products → + New Product.** Name, category = Beads, leave subtype/attributes blank except
  optionally a SKU. Save.
- **Expect:** redirected to product detail; status shows **Active**; all blank attributes show
  "—" rather than blocking save.

## 4. Create a finding product
- Same as above with category = Findings.
- **Expect:** same result; category system supports both without special-casing.

## 5. Create a catalog listing for a product
- From the bead product's detail page, click **+ Catalog Listing**. Title required; price
  optional. Save.
- **Expect:** listing appears under **Catalog Listings** on the product detail page with a price
  or "—" if left blank.

## 6. Create a manual inventory unit
- **Inventory Units → + New Inventory Unit.** Select the bead product, quantity, unit type
  (e.g. strand), received date. Save.
- **Expect:** appears in the Inventory Units list showing the product's **name** (not a generic
  placeholder), vendor "—" (none set), status **Available**.

## 7. Create a supplier purchase order with two lines
- **Supplier Orders → + New Supplier Order.** Vendor = the one from step 2.
  - Line 1: select the bead product from the dropdown, expected quantity 10, unit strand.
  - Click **+ Add Line**. Line 2: leave the product dropdown on "Free-text item," type a
    description (e.g. "Unlabeled bag of clasps"), no quantity.
- Save.
- **Expect:** order detail page shows both lines — line 1 shows the product name, line 2 shows
  "Unresolved: Unlabeled bag of clasps." Status is **Draft**.

## 8. Receive partially against the supplier order
- Click **Mark as Ordered** (status → **Ordered**), then **Receive Items**.
- For the product-linked line, enter a received quantity *less than* 10 (e.g. 6). Leave the
  free-text line's received quantity blank for now.
- Click **Record Receipt**.
- **Expect:** result page lists the received line with reconciliation status **Shortage**; back
  on the order detail page, the order status is **Partially Received** and the line's own status
  shows **Partially Received** too.

## 9. Receive the remaining quantity against the same supplier order
- From the order detail page, click **Receive Items** again.
- Enter the remainder (e.g. 4) for the same product line.
- Click **Record Receipt**.
- **Expect:** result shows reconciliation status **Matched**; order status is now fully
  **Received**; the order detail page's **Receipts** section shows two separate receipts, each
  with its own line(s) and reconciliation outcome — this is the cumulative-reconciliation fix, so
  confirm the order actually reaches Received rather than staying stuck on Partially Received.

## 10. Record a discrepancy (overage, shortage, damaged, or substitution)
- Create a second supplier order with one product-linked line, expected quantity 5.
- Receive against it with either a different quantity (e.g. 8 for overage) or use the
  **Discrepancy Override** dropdown to mark it **Damaged** regardless of quantity.
- **Expect:** the reconciliation status shown matches your choice; the item still shows up under
  **Operations → Receiving Discrepancies** with the product name, vendor, quantity, and a link
  back to the order.

## 11. Use Quick Receive with no prior order
- **Quick Receive** (in the sidebar). Choose a vendor (or leave on Unknown Vendor). Add one item
  — either linked to an existing product or free-text. Enter a quantity and unit. Save.

## 12. Confirm Quick Receive created a retroactive order and receipt
- **Expect:** the result page's "What Was Recorded" table shows the item and its status; clicking
  **View created supplier order** opens a new order detail page tagged **"Created during
  receiving"** with status **Received** and a single receipt already attached.

## 13. Confirm inventory units were created from the receipt
- Go to **Inventory Units** (or the product detail page, if you linked a product in step 11).
- **Expect:** a new inventory unit exists with the quantity/unit you entered, vendor name shown,
  and status **Available** (or **Unresolved** if you left it free-text).

## 14. Resolve an unresolved received item to a product
- Go to **Operations → Items Needing Product Match**. Find the free-text item from step 7 or 11.
- Select a product from the dropdown and click **Match**.
- **Expect:** the row disappears from the unresolved list; opening the linked inventory unit (or
  the order's receipt line) now shows the product's name instead of the free-text description —
  both records update together, not just one.

## 15. Open product detail and confirm full history is visible
- Open the bead product used in steps 7–9.
- **Expect four sections beyond the product's own attributes:**
  - **Inventory Units** — quantity, location, vendor, status, received date.
  - **Supplier Order Lines** — every order that requested this product, with a link to each order.
  - **Receiving Activity** — every receipt this product came in on, with vendor, quantity,
    reconciliation status, and a link back to the order.
  - **Catalog Listings** — from step 5.
- You should be able to answer "what do we have, where is it, how did it get here, which
  vendor/order/receipt" entirely from this one page.

## 16. Confirm operational views work
- **Open Supplier Orders** — shows only draft/ordered/partially-received orders.
- **Items Needing Product Match** — should now be empty if you resolved everything in step 14
  (or show only whatever you deliberately left unresolved).
- **Inventory On Hand** — shows all available/reserved stock with location; filterable by
  category/location.
- **Receiving Discrepancies** — shows the shortage/overage/damaged/substitution lines from steps
  8–10, each with vendor, product, and a link to its order. (Note: a line's discrepancy status is
  a permanent record of that specific receipt event — a shortage from step 8 will still be listed
  here even after step 9 completed the order, which is intentional history, not a bug.)

If all 16 steps match expectations, the app is ready to walk Patti through the same script.
