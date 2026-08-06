import { useEffect, useState } from "react";
import { api } from "../lib/apiClient";
import { connectEmailAccount, deleteEmailAccount, listEmailAccounts } from "../lib/emailAccounts";
import { useFetch } from "../lib/useFetch";
import { useEmailScan } from "../lib/useEmailScan";
import type { EmailAccount, EmailProvider, Vendor } from "../lib/types";
import { EmailScanSection } from "../components/EmailScanSection";
import { Loading } from "../components/States";

function providerLabel(provider: EmailProvider): string {
  return provider === "gmail" ? "Gmail" : "Outlook";
}

function EmailScanForAccount({
  account,
  vendors,
  reloadVendors,
}: {
  account: EmailAccount;
  vendors: Vendor[];
  reloadVendors: () => void;
}) {
  const scan = useEmailScan(account, vendors, reloadVendors);

  return (
    <section className="detail-section">
      <h2>Scan {account.email_address}</h2>
      <div className="form-actions line-row">
        <div className="scan-trigger">
          <button className="btn-primary" onClick={scan.runScan} disabled={scan.scanning}>
            {scan.scanning ? "Scanning..." : "Scan Inbox"}
          </button>
          {scan.scanning && <div className="scan-status">Scanning {providerLabel(account.provider)} inbox…</div>}
        </div>
      </div>
      <EmailScanSection scan={scan} />
    </section>
  );
}

export function OrderEmailScanPage() {
  const vendors = useFetch(() => api.get<Vendor[]>("/vendors"), []);
  const vendorList = vendors.data ?? [];

  const accounts = useFetch(() => listEmailAccounts(), []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<EmailProvider | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && accounts.data && accounts.data.length > 0) {
      setSelectedId(accounts.data[0].id);
    }
  }, [accounts.data, selectedId]);

  async function handleConnect(provider: EmailProvider) {
    setConnectError(null);
    setConnecting(provider);
    try {
      const result = await connectEmailAccount(provider);
      if (!result.ok && result.message !== "Sign-in was cancelled.") {
        setConnectError(result.message || "Could not connect the account.");
      }
      accounts.reload();
    } catch (err) {
      setConnectError(err instanceof Error ? err.message : "Could not connect the account.");
    } finally {
      setConnecting(null);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteEmailAccount(id);
      if (selectedId === id) setSelectedId(null);
      accounts.reload();
    } finally {
      setDeletingId(null);
    }
  }

  const selectedAccount = accounts.data?.find((a) => a.id === selectedId) ?? null;

  return (
    <div>
      <h1>Order Email Scan</h1>

      <h2>What is this</h2>
      <p className="page-subtitle">
        Scans a connected email inbox (last ~6 months) for emails that look like bead-supply order
        confirmations — from your known vendors or mentioning bead-related terms. Use View to read an
        email, or Record Order to turn it into a supplier order. Record Order uses AI to read the order
        details and item list from the email body and any attached invoice/receipt (PDF or image) —
        review the created order and fix anything it misread. Once recorded, the email is moved out of
        the inbox into a folder created automatically the first time it's needed. Connected accounts stay
        connected across sessions and devices — you only need to sign in again if access expires or is
        revoked.
      </p>

      <section className="detail-section">
        <h2>Connected accounts</h2>
        {connectError && <div className="alert alert-error">{connectError}</div>}

        {accounts.loading && <Loading />}

        {accounts.data && accounts.data.length === 0 && (
          <div className="alert alert-warn">No email accounts connected yet. Add one below to start scanning.</div>
        )}

        {accounts.data && accounts.data.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Account</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {accounts.data.map((acct) => (
                <tr key={acct.id}>
                  <td>
                    <input
                      type="radio"
                      name="selected-account"
                      checked={selectedId === acct.id}
                      onChange={() => setSelectedId(acct.id)}
                      aria-label={`Select ${acct.email_address}`}
                    />
                  </td>
                  <td>
                    {providerLabel(acct.provider)}: {acct.email_address}
                  </td>
                  <td>
                    {acct.status === "needs_reauth" ? (
                      <span className="badge tone-warn">Needs reconnect</span>
                    ) : (
                      <span className="badge tone-good">Connected</span>
                    )}
                  </td>
                  <td>
                    <div className="maintenance-row">
                      {acct.status === "needs_reauth" && (
                        <button
                          className="btn-secondary"
                          onClick={() => handleConnect(acct.provider)}
                          disabled={connecting !== null}
                        >
                          {connecting === acct.provider ? "Connecting..." : "Reconnect"}
                        </button>
                      )}
                      <button
                        className="btn-secondary"
                        onClick={() => handleDelete(acct.id)}
                        disabled={deletingId === acct.id}
                      >
                        {deletingId === acct.id ? "Removing..." : "Remove"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="form-actions line-row">
          <button className="btn-secondary" onClick={() => handleConnect("gmail")} disabled={connecting !== null}>
            {connecting === "gmail" ? "Connecting..." : "Add Gmail Account"}
          </button>
          <button className="btn-secondary" onClick={() => handleConnect("outlook")} disabled={connecting !== null}>
            {connecting === "outlook" ? "Connecting..." : "Add Outlook Account"}
          </button>
        </div>
      </section>

      {selectedAccount && selectedAccount.status === "active" && (
        <EmailScanForAccount
          key={selectedAccount.id}
          account={selectedAccount}
          vendors={vendorList}
          reloadVendors={vendors.reload}
        />
      )}
    </div>
  );
}
