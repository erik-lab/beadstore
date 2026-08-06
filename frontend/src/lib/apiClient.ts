import { supabase } from "./supabaseClient";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.status = status;
    this.detail = detail;
  }
}

async function authHeaders(forceRefresh: boolean): Promise<Record<string, string>> {
  const { data } = forceRefresh ? await supabase.auth.refreshSession() : await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function doFetch(path: string, options: RequestInit, forceRefresh: boolean): Promise<Response> {
  const headers = {
    "Content-Type": "application/json",
    ...(await authHeaders(forceRefresh)),
    ...(options.headers ?? {}),
  };
  return fetch(`${API_BASE_URL}${path}`, { ...options, headers });
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response = await doFetch(path, options, false);

  // A 401 right after signing in can happen if this request's session read
  // raced the sign-in handoff finishing (several components — dashboard,
  // sidebar hints, profile — all fire their first request the instant
  // `session` flips from null to signed-in). One retry with a forced token
  // refresh clears that up instead of surfacing a confusing error the user
  // then has to dismiss even though they're actually still signed in fine.
  if (response.status === 401) {
    response = await doFetch(path, options, true);
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? body;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
