// Types for candidate/detail emails returned by the backend's email-account
// scan endpoints (backend/app/schemas/email_account.py) — field names mirror
// the API response directly (snake_case), same convention as Profile.

export interface CandidateEmail {
  id: string;
  from_address: string;
  subject: string;
  date: string;
  snippet: string;
  match_reasons: string[];
}

export interface EmailAttachment {
  filename: string;
  mime_type: string;
  base64_data: string;
}

export interface EmailDetail {
  id: string;
  from_address: string;
  to_address: string;
  subject: string;
  date: string;
  body_text: string;
  attachments: EmailAttachment[];
}

export type MoveEmailResult =
  | { moved: true; reason: null; message: null }
  | { moved: false; reason: "permission" | "error"; message: string };
