import { useState } from "react";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import { connectEtsyShop } from "../../lib/etsyConnect";
import type {
  CatalogListing,
  EtsyAccount,
  EtsyActivateResult,
  EtsyListingSync,
  EtsyOption,
  EtsyPullResult,
} from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

// Deliberately no-frills, same spirit as RecordSalePage.tsx — a way for
// Patti/Erik to see the Etsy integration actually work (connect, push a
// listing, pull orders) without needing real Etsy credentials yet (points
// at the built-in simulator locally). Easy to delete: this file, its route,
// its Utilities card.

const WHEN_MADE_OTHER = "__other__";

// Etsy's `when_made` is a fixed enum and a wrong value fails the push. These
// are the values that published sources agree on; the buckets covering the
// 2000s differ between them, and the most recent bucket shifts over time, so
// those go through "Other" rather than being guessed at here. `made_to_order`
// is what Patti's own pieces will almost always be.
const WHEN_MADE_OPTIONS = [
  { value: "made_to_order", label: "Made to order" },
  { value: "2020_2022", label: "2020-2022" },
  { value: "2010_2019", label: "2010-2019" },
  { value: "1990s", label: "1990s" },
  { value: "1980s", label: "1980s" },
  { value: "1970s", label: "1970s" },
  { value: "1960s", label: "1960s" },
  { value: "1950s", label: "1950s" },
  { value: "before_1700", label: "Before 1700" },
];

export function EtsyStatusPage() {
  const accounts = useFetch(() => api.get<EtsyAccount[]>("/etsy/accounts"), []);
  const listings = useFetch(() => api.get<CatalogListing[]>("/catalog-listings?limit=200"), []);

  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<EtsyPullResult | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  const [listingId, setListingId] = useState("");
  const [taxonomyId, setTaxonomyId] = useState("");
  const [shippingProfileId, setShippingProfileId] = useState("");
  const [returnPolicyId, setReturnPolicyId] = useState("");
  const [whoMade, setWhoMade] = useState("i_did");
  const [whenMade, setWhenMade] = useState("made_to_order");
  const [taxonomySearch, setTaxonomySearch] = useState("");

  // Fetched from the connected shop rather than typed: these are Etsy's own
  // numeric IDs, which can't be known from inside the back office.
  const hasShop = (accounts.data ?? []).some((a) => a.status === "active");
  const shippingProfiles = useFetch(
    () => (hasShop ? api.get<EtsyOption[]>("/etsy/shipping-profiles") : Promise.resolve([])),
    [hasShop],
  );
  const returnPolicies = useFetch(
    () => (hasShop ? api.get<EtsyOption[]>("/etsy/return-policies") : Promise.resolve([])),
    [hasShop],
  );
  // Searched server-side against a cached copy of Etsy's taxonomy — the full
  // tree is far too large to hand to the browser.
  const taxonomy = useFetch(
    () =>
      hasShop
        ? api.get<EtsyOption[]>(
            `/etsy/taxonomy?limit=50${taxonomySearch.trim() ? `&search=${encodeURIComponent(taxonomySearch.trim())}` : ""}`,
          )
        : Promise.resolve([]),
    [hasShop, taxonomySearch],
  );
  const optionsError = shippingProfiles.error ?? returnPolicies.error ?? taxonomy.error;
  const [pushResult, setPushResult] = useState<EtsyListingSync | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushing, setPushing] = useState(false);

  const [activating, setActivating] = useState(false);
  const [activateError, setActivateError] = useState<string | null>(null);
  const [activateResult, setActivateResult] = useState<EtsyActivateResult | null>(null);

  const [simulateQuantity, setSimulateQuantity] = useState("1");
  const [simulatePrice, setSimulatePrice] = useState("");
  const [simulating, setSimulating] = useState(false);
  const [simulateError, setSimulateError] = useState<string | null>(null);
  const [simulateOk, setSimulateOk] = useState(false);

  async function handleConnect() {
    setConnecting(true);
    setConnectError(null);
    try {
      const result = await connectEtsyShop();
      if (!result.ok) {
        setConnectError(result.message || "Could not connect the shop.");
      }
      accounts.reload();
    } catch (err) {
      setConnectError(err instanceof Error ? err.message : "Could not connect the shop.");
    } finally {
      setConnecting(false);
    }
  }

  async function handleDisconnect(accountId: string) {
    await api.delete(`/etsy/accounts/${accountId}`);
    accounts.reload();
  }

  async function handlePull() {
    setPulling(true);
    setPullError(null);
    setPullResult(null);
    try {
      const result = await api.post<EtsyPullResult>("/etsy/pull", {});
      setPullResult(result);
    } catch (err) {
      setPullError(err instanceof ApiError ? String(err.detail) : "Could not pull orders.");
    } finally {
      setPulling(false);
    }
  }

  async function handleActivate() {
    setActivateError(null);
    setActivateResult(null);
    if (!listingId) {
      setActivateError("Choose a listing above first.");
      return;
    }
    setActivating(true);
    try {
      setActivateResult(
        await api.post<EtsyActivateResult>(`/etsy/listings/${listingId}/activate`),
      );
    } catch (err) {
      setActivateError(
        err instanceof ApiError ? String(err.detail) : "Could not activate the listing.",
      );
    } finally {
      setActivating(false);
    }
  }

  async function handlePush() {
    setPushError(null);
    setPushResult(null);
    if (!listingId) {
      setPushError("Choose a listing to push.");
      return;
    }
    // These used to default to a hardcoded "1", which only worked against the
    // simulator. Empty now, so they have to be checked — Number("") is 0, and
    // Etsy would reject that with a far less helpful message.
    const missing = [
      !taxonomyId && "an Etsy category",
      !shippingProfileId && "a shipping profile",
      !returnPolicyId && "a return policy",
      !whenMade.trim() && "when it was made",
    ].filter(Boolean);
    if (missing.length > 0) {
      setPushError(`Etsy needs ${missing.join(", ")} before this can be pushed.`);
      return;
    }
    setPushing(true);
    try {
      const result = await api.post<EtsyListingSync>(`/etsy/listings/${listingId}/push`, {
        taxonomy_id: Number(taxonomyId),
        shipping_profile_id: Number(shippingProfileId),
        return_policy_id: Number(returnPolicyId),
        who_made: whoMade,
        when_made: whenMade,
      });
      setPushResult(result);
    } catch (err) {
      setPushError(err instanceof ApiError ? String(err.detail) : "Could not push listing.");
    } finally {
      setPushing(false);
    }
  }

  async function handleSimulateSale() {
    setSimulateError(null);
    setSimulateOk(false);
    if (!listingId) {
      setSimulateError("Choose a listing above and push it to Etsy first.");
      return;
    }
    setSimulating(true);
    try {
      await api.post("/etsy/simulate-sale", {
        catalog_listing_id: listingId,
        quantity: Number(simulateQuantity) || 1,
        price: simulatePrice ? Number(simulatePrice) : null,
      });
      setSimulateOk(true);
    } catch (err) {
      setSimulateError(err instanceof ApiError ? String(err.detail) : "Could not simulate a sale.");
    } finally {
      setSimulating(false);
    }
  }

  const listingItems = listings.data ?? [];

  return (
    <div>
      <h1>Etsy Integration</h1>
      <p className="page-subtitle">
        Testing/validation tool for the Etsy push/pull sync — points at the built-in Etsy simulator
        in dev, the real Etsy API once credentials and a connected shop exist. No polish intended.
      </p>

      <section className="detail-section">
        <h2>Connected Shop</h2>
        {connectError && <div className="alert alert-error">{connectError}</div>}
        {accounts.loading && <Loading />}
        {accounts.error && <ErrorState message={accounts.error} />}
        {accounts.data && accounts.data.length === 0 && <EmptyState label="No Etsy shop connected yet." />}
        {accounts.data && accounts.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Shop</th>
                <th>Status</th>
                <th>Scopes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {accounts.data.map((a) => (
                <tr key={a.id}>
                  <td>{a.shop_name ?? a.shop_id}</td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                  <td style={{ fontSize: 12 }}>{a.scopes}</td>
                  <td>
                    <button className="btn-secondary" onClick={() => handleDisconnect(a.id)}>
                      Disconnect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <button className="btn-primary" onClick={handleConnect} disabled={connecting} style={{ marginTop: 12 }}>
          {connecting ? "Connecting..." : "Connect Etsy Shop"}
        </button>
      </section>

      <section className="detail-section">
        <h2>Push a Listing</h2>
        <p className="page-subtitle">
          Creates a draft listing on Etsy the first time, updates price/quantity on later pushes.
        </p>
        {pushError && <div className="alert alert-error">{pushError}</div>}
        <div className="form-card">
          <label>
            Catalog Listing
            <select value={listingId} onChange={(e) => setListingId(e.target.value)}>
              <option value="">Select listing...</option>
              {listingItems.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
          </label>
          {/* These three are Etsy's own numeric IDs, which mean nothing
              outside the live shop — so they're fetched from it rather than
              typed from memory. They need a connected shop to load. */}
          {optionsError && <div className="alert alert-warn">{optionsError}</div>}

          <label>
            Etsy category
            <input
              placeholder="Search Etsy's categories, e.g. beads"
              value={taxonomySearch}
              onChange={(e) => setTaxonomySearch(e.target.value)}
            />
            <select value={taxonomyId} onChange={(e) => setTaxonomyId(e.target.value)}>
              <option value="">
                {taxonomy.loading ? "Loading..." : "Select a category..."}
              </option>
              {(taxonomy.data ?? []).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="line-row">
            <label>
              Shipping profile
              <select
                value={shippingProfileId}
                onChange={(e) => setShippingProfileId(e.target.value)}
              >
                <option value="">
                  {shippingProfiles.loading ? "Loading..." : "Select a profile..."}
                </option>
                {(shippingProfiles.data ?? []).map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Return policy
              <select value={returnPolicyId} onChange={(e) => setReturnPolicyId(e.target.value)}>
                <option value="">
                  {returnPolicies.loading ? "Loading..." : "Select a policy..."}
                </option>
                {(returnPolicies.data ?? []).map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="line-row">
            <label>
              Who made it
              <select value={whoMade} onChange={(e) => setWhoMade(e.target.value)}>
                <option value="i_did">I did</option>
                <option value="someone_else">Someone else</option>
                <option value="collective">A member of my shop</option>
              </select>
            </label>
            <label>
              When made
              <select
                value={WHEN_MADE_OPTIONS.some((o) => o.value === whenMade) ? whenMade : WHEN_MADE_OTHER}
                onChange={(e) =>
                  setWhenMade(e.target.value === WHEN_MADE_OTHER ? "" : e.target.value)
                }
              >
                {WHEN_MADE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
                <option value={WHEN_MADE_OTHER}>Other — type the exact Etsy value...</option>
              </select>
              {!WHEN_MADE_OPTIONS.some((o) => o.value === whenMade) && (
                <input
                  placeholder="e.g. 2003_2009"
                  value={whenMade}
                  onChange={(e) => setWhenMade(e.target.value)}
                />
              )}
            </label>
          </div>
          <button className="btn-primary" onClick={handlePush} disabled={pushing}>
            {pushing ? "Pushing..." : "Push to Etsy"}
          </button>
        </div>
        {pushResult && (
          <p className="page-subtitle" style={{ marginTop: 8 }}>
            Sync status: <StatusBadge status={pushResult.sync_status} /> — Etsy listing ID:{" "}
            {pushResult.etsy_listing_id ?? "—"}
            {pushResult.etsy_state ? ` — on Etsy this listing is a ${pushResult.etsy_state}` : ""}
          </p>
        )}
      </section>

      <section className="detail-section">
        <h2>Make a Listing Live</h2>
        <p className="page-subtitle">
          A pushed listing starts as a <strong>draft</strong>: it's on Etsy but nobody can see it.
          Activating is what puts it in front of buyers. Etsy needs the listing to have at least one
          photo first — photos are sent automatically whenever you push, taken from the product's
          Photos section.
        </p>
        <div className="alert alert-warn">
          Against a real Etsy shop, activating a listing is what Etsy charges its per-listing fee
          for. Drafts are free. That's why this is a separate button and never happens
          automatically when you push.
        </div>
        {activateError && <div className="alert alert-error">{activateError}</div>}
        {activateResult && (
          <div className="alert alert-success">
            Listing {activateResult.etsy_listing_id} is now{" "}
            <strong>{activateResult.etsy_state}</strong> on Etsy.
          </div>
        )}
        <div className="form-card">
          <p className="page-subtitle">
            Uses the listing selected under “Push a Listing” above.
          </p>
          <div className="maintenance-row">
            <button className="btn-primary" onClick={handleActivate} disabled={activating}>
              {activating ? "Activating..." : "Activate on Etsy"}
            </button>
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h2>Simulate a Sale</h2>
        <p className="page-subtitle">
          Play button for the simulator — pretends someone bought the listing selected above (must
          be pushed to Etsy first), so "Pull Orders Now" below has a real order to find. Only works
          against the simulator; there's no such thing on the real Etsy API.
        </p>
        {simulateError && <div className="alert alert-error">{simulateError}</div>}
        <div className="line-row">
          <input
            type="number"
            step="1"
            placeholder="Quantity"
            value={simulateQuantity}
            onChange={(e) => setSimulateQuantity(e.target.value)}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Price (optional, defaults to listing price)"
            value={simulatePrice}
            onChange={(e) => setSimulatePrice(e.target.value)}
          />
          <button className="btn-secondary" onClick={handleSimulateSale} disabled={simulating}>
            {simulating ? "Simulating..." : "Simulate Sale on Etsy"}
          </button>
        </div>
        {simulateOk && (
          <p className="page-subtitle" style={{ marginTop: 8 }}>
            Done — a fake paid order was created on the simulator. Click "Pull Orders Now" below to
            bring it in.
          </p>
        )}
      </section>

      <section className="detail-section">
        <h2>Pull Orders</h2>
        <p className="page-subtitle">Fetch paid Etsy orders and record them as sales, decrementing inventory.</p>
        {pullError && <div className="alert alert-error">{pullError}</div>}
        <button className="btn-primary" onClick={handlePull} disabled={pulling}>
          {pulling ? "Pulling..." : "Pull Orders Now"}
        </button>
        {pullResult && (
          <p className="page-subtitle" style={{ marginTop: 8 }}>
            Created {pullResult.created}, skipped {pullResult.skipped_duplicate} already-recorded,{" "}
            {pullResult.skipped_unmapped} unmapped to a pushed listing.
          </p>
        )}
      </section>
    </div>
  );
}
