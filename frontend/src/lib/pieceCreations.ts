import { api } from "./apiClient";
import type { PieceCreation } from "./types";

export interface PieceComponentInput {
  inventory_unit_id: string;
  quantity_used: number;
}

export interface PieceCreationInput {
  product_id: string;
  created_date?: string | null;
  quantity_produced?: number;
  creation_cost?: number | null;
  notes?: string | null;
  components?: PieceComponentInput[];
}

export function listPieceCreations(): Promise<PieceCreation[]> {
  return api.get<PieceCreation[]>("/piece-creations");
}

export function getPieceCreation(id: string): Promise<PieceCreation> {
  return api.get<PieceCreation>(`/piece-creations/${id}`);
}

export function createPieceCreation(payload: PieceCreationInput): Promise<PieceCreation> {
  return api.post<PieceCreation>("/piece-creations", payload);
}

export function cancelPieceCreation(id: string): Promise<PieceCreation> {
  return api.post<PieceCreation>(`/piece-creations/${id}/cancel`);
}
