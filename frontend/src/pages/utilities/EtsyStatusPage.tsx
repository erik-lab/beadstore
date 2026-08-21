import { useState } from "react";
import { api, ApiError } from "../../lib/apiClient";
import { useFetch } from "../../lib/useFetch";
import { connectEtsyShop } from "../../lib/etsyConnect";
import type { CatalogListing, EtsyAccount, EtsyListingSync, EtsyPullResult } from "../../lib/types";
import { Loading, EmptyState, ErrorState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";

// Deliberately no-frills, same spirit as RecordSalePage.tsx — a way for
// Patti/Erik to see the Etsy integration actually work (connect, push a
// listing, pull orders) without needing real Etsy credentials yet (points
// at the built-in simulator locally). Easy to delete: this file, its route,
// its Utilities card.

export function EtsyStatusPage() {
  const accounts = useFetch(() => api.get<EtsyAccount[]>("/etsy/accounts"), []);
  const listings = useFetch(() => api.get<CatalogListing[]>("/catalog-listings?limit=200"), []);

  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<EtsyPullResult | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  const [listingId, setListingId] = useState("");
  const [taxonomyId, setTaxonomyId] = useState("1");
  const [shippingProfileId, setShippingProfileId] = useState("1");
  const [returnPolicyId, setReturnPolicyId] = useState("1");
  const [whoMade, setWhoMade] = useState("i_did");
  const [whenMade, setWhenMade] = useState("made_to_order");
  const [pushResult, setPushResult] = useState<EtsyListingSync | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushing, setPushing] = useState(false);

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

  async function handlePush() {
    setPushError(null);
    setPushResult(null);
    if (!listingId) {
      setPushError("Choose a listing to push.");
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
          <div className="line-row">
            <input placeholder="Taxonomy ID" value={taxonomyId} onChange={(e) => setTaxonomyId(e.target.value)} />
            <input
              placeholder="Shipping Profile ID"
              value={shippingProfileId}
              onChange={(e) => setShippingProfileId(e.target.value)}
            />
            <input
              placeholder="Return Policy ID"
              value={returnPolicyId}
              onChange={(e) => setReturnPolicyId(e.target.value)}
            />
          </div>
          <div className="line-row">
            <select value={whoMade} onChange={(e) => setWhoMade(e.target.value)}>
              <option value="i_did">I did</option>
              <option value="someone_else">Someone else</option>
              <option value="collective">A member of my shop</option>
            </select>
            <input placeholder="When made (e.g. made_to_order)" value={whenMade} onChange={(e) => setWhenMade(e.target.value)} />
          </div>
          <button className="btn-primary" onClick={handlePush} disabled={pushing}>
            {pushing ? "Pushing..." : "Push to Etsy"}
          </button>
        </div>
        {pushResult && (
          <p className="page-subtitle" style={{ marginTop: 8 }}>
            Sync status: <StatusBadge status={pushResult.sync_status} /> — Etsy listing ID:{" "}
            {pushResult.etsy_listing_id ?? "—"}
          </p>
        )}
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
