import { api } from "./apiClient";
import type {
  IntakeBatch,
  IntakeBatchDetail,
  IntakeCommitResult,
  IntakeRow,
  IntakeSourceKind,
} from "./types";

// Keep in step with the server's base64 field limit (10MB of base64, so a
// file of roughly 7MB). Checked here too so an oversized pick fails
// immediately instead of after a long upload.
const MAX_FILE_BYTES = 7 * 1024 * 1024;

export class FileTooLargeError extends Error {
  constructor(filename: string) {
    super(
      `"${filename}" is too big to import in one go (limit is about 7MB). ` +
        `Split it into smaller files, or save just the relevant sheet.`,
    );
  }
}

/** Read a picked file as base64, without the data-URL prefix. */
export function fileToBase64(file: File): Promise<string> {
  if (file.size > MAX_FILE_BYTES) {
    return Promise.reject(new FileTooLargeError(file.name));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new Error(`Could not read "${file.name}".`));
    reader.readAsDataURL(file);
  });
}

export function parseIntakeText(
  text: string,
  sourceKind: Extract<IntakeSourceKind, "paste" | "voice">,
  sourceName?: string,
): Promise<IntakeBatchDetail> {
  return api.post<IntakeBatchDetail>("/inventory-intake/parse-text", {
    text,
    source_kind: sourceKind,
    source_name: sourceName ?? null,
  });
}

export async function parseIntakeFile(file: File): Promise<IntakeBatchDetail> {
  const data_base64 = await fileToBase64(file);
  return api.post<IntakeBatchDetail>("/inventory-intake/parse-file", {
    filename: file.name,
    mime_type: file.type,
    data_base64,
  });
}

export function listIntakeBatches(): Promise<IntakeBatch[]> {
  return api.get<IntakeBatch[]>("/inventory-intake/batches?limit=50");
}

export function getIntakeBatch(id: string): Promise<IntakeBatchDetail> {
  return api.get<IntakeBatchDetail>(`/inventory-intake/batches/${id}`);
}

export function updateIntakeRow(rowId: string, changes: Partial<IntakeRow>): Promise<IntakeRow> {
  return api.patch<IntakeRow>(`/inventory-intake/rows/${rowId}`, changes);
}

export function skipIntakeRow(rowId: string, skipped: boolean): Promise<IntakeRow> {
  return api.post<IntakeRow>(`/inventory-intake/rows/${rowId}/skip`, { skipped });
}

/** Apply shared values (date, vendor, location...) to every open row. */
export function bulkUpdateIntakeRows(
  batchId: string,
  changes: Record<string, string | null>,
): Promise<IntakeBatchDetail> {
  return api.patch<IntakeBatchDetail>(`/inventory-intake/batches/${batchId}/rows`, changes);
}

export function commitIntakeBatch(batchId: string): Promise<IntakeCommitResult> {
  return api.post<IntakeCommitResult>(`/inventory-intake/batches/${batchId}/commit`);
}

export function deleteIntakeBatch(batchId: string): Promise<void> {
  return api.delete<void>(`/inventory-intake/batches/${batchId}`);
}
