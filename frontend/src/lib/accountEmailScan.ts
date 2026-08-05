import { api } from "./apiClient";
import type { CandidateEmail, EmailDetail, MoveEmailResult } from "./emailScanTypes";

export function scanAccountForOrderEmails(accountId: string, vendorNames: string[]): Promise<CandidateEmail[]> {
  return api.post<CandidateEmail[]>(`/email-accounts/${accountId}/scan`, { vendor_names: vendorNames });
}

export function fetchAccountEmailDetail(accountId: string, messageId: string): Promise<EmailDetail> {
  return api.get<EmailDetail>(`/email-accounts/${accountId}/emails/${encodeURIComponent(messageId)}`);
}

export function moveAccountEmailToOrders(accountId: string, messageId: string): Promise<MoveEmailResult> {
  return api.post<MoveEmailResult>(`/email-accounts/${accountId}/emails/${encodeURIComponent(messageId)}/move`);
}
