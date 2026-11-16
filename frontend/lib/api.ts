/**
 * Typed client for the BatterySizer API (v2).
 *
 * Request and response types are generated from the API's published contract
 * (docs/api-v2.schema.json → lib/api-v2-types.ts); run `npm run gen:api-types`
 * after the API's models change. No calculation logic lives here.
 *
 * The API runs on a free host that sleeps when idle, so the first request after
 * a quiet spell can take 30–60 seconds. Callers should show a "waking up" message
 * rather than treat a slow reply as an error.
 */
import type { AssessRequest, AssessResponse, SummaryResponse, UsageCheckResponse } from "./api-v2-types";

export type { AssessRequest, AssessResponse, SummaryResponse, UsageCheckResponse } from "./api-v2-types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/** Longer than the host's worst-case wake-up time. */
const TIMEOUT_MS = 90_000;

export class ApiError extends Error {
  constructor(
    /** HTTP status, or 0 when the API couldn't be reached at all. */
    public readonly status: number,
    /** A plain-English message that can be shown to the homeowner. */
    message: string,
    /** The API's own error detail, for logging (never contains usage data). */
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Turn FastAPI's error body into one readable sentence. */
function describe(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { loc?: (string | number)[]; msg?: string };
    const where = (first.loc ?? []).filter((p) => p !== "body").join(" › ");
    return where ? `${where}: ${first.msg}` : first.msg ?? "Some of the details aren't valid.";
  }
  if (status >= 500) return "Something went wrong on our side. Please try again in a minute.";
  return "Some of the details aren't valid. Please check them and try again.";
}

async function request<T>(path: string, init: RequestInit, signal?: AbortSignal): Promise<T> {
  // Combine the caller's signal with a timeout (by hand: AbortSignal.any is too new for older phones).
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; ctrl.abort(); }, TIMEOUT_MS);
  const onAbort = () => ctrl.abort();
  signal?.addEventListener("abort", onAbort, { once: true });
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, signal: ctrl.signal });
  } catch (err) {
    if (signal?.aborted) throw err;   // the caller cancelled (e.g. inputs changed); not an error to show
    throw new ApiError(
      0,
      timedOut
        ? "The calculator is taking too long to respond. Please try again."
        : "We couldn't reach the calculator. Check your connection and try again.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, describe(res.status, body), body);
  return body as T;
}

/**
 * Assess a home. For the upload route pass the CSV files; they are sent as
 * multipart form data and processed in memory by the API, never stored.
 */
export async function assess(
  inputs: AssessRequest,
  files: File[] = [],
  signal?: AbortSignal,
): Promise<AssessResponse> {
  if (inputs.usage.route === "upload") {
    if (!files.length) throw new ApiError(422, "Please add at least one usage file.");
    const form = new FormData();
    form.append("inputs", JSON.stringify(inputs));
    for (const f of files) form.append("files", f);
    return request<AssessResponse>("/api/v2/assess", { method: "POST", body: form }, signal);
  }
  return request<AssessResponse>(
    "/api/v2/assess",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(inputs) },
    signal,
  );
}

/**
 * Read uploaded usage files and report what was found (dates, days, gaps), without
 * running the assessment. Each file gets its own ok/error, so one bad file doesn't
 * hide the others. Processed in memory by the API; never stored.
 */
export async function checkUsage(files: File[], signal?: AbortSignal): Promise<UsageCheckResponse> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return request<UsageCheckResponse>("/api/v2/usage/check", { method: "POST", body: form }, signal);
}

/**
 * A short plain-English summary of an answer, written by AI (Claude) from its headline
 * figures (POST /api/v2/summary). Throws ApiError when no summary is available
 * (switched off, busy, or the reply failed its checks); callers just leave it out.
 */
export async function summarise(answer: AssessResponse, signal?: AbortSignal): Promise<SummaryResponse> {
  return request<SummaryResponse>(
    "/api/v2/summary",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(answer) },
    signal,
  );
}

/** A home at a postcode, from GET /api/epc/lookup (the EPC register). */
export interface EpcHome {
  certificate_number: string;
  address: string;
  dwelling_type: string | null;
  property_type: "flat" | "terraced" | "semi" | "detached";
  bedrooms: number;
  floor_area_m2: number | null;
  epc_rating: string | null;
  registration_date: string | null;
  heating_kind: "heat_pump" | "electric" | "gas" | "other_fuel" | "unknown";
  heating_description: string | null;
  heating_type: "gas" | "electric";
  has_gas: boolean;
  has_heat_pump: boolean;
  has_solar: boolean;
  has_battery: boolean;
  annual_kwh: number;
  confidence: "medium" | "low";
}

/**
 * Homes at a postcode on the EPC register. Resolves to [] when there are none.
 * Throws ApiError (503) when the lookup isn't available, so callers can offer manual entry.
 * The postcode is sent to the API only to search the register; it's never stored.
 */
export async function lookupEpc(postcode: string, signal?: AbortSignal): Promise<EpcHome[]> {
  const res = await request<{ found: boolean; properties: EpcHome[] }>(
    `/api/epc/lookup?postcode=${encodeURIComponent(postcode.trim())}`, { method: "GET" }, signal,
  );
  return res.found ? res.properties : [];
}

/** A tariff as listed by GET /api/tariffs (for the tariff picker). */
export interface TariffSummary {
  key: string;
  name: string;
  supplier: string;
  description: string;
  color: string;
  standing_charge_pence: number;
  is_flat_rate: boolean;
  is_dynamic: boolean;
  slot_rates_pence: number[];
}

export async function fetchTariffs(signal?: AbortSignal): Promise<TariffSummary[]> {
  return request<TariffSummary[]>("/api/tariffs", { method: "GET" }, signal);
}

/** Wake the API early (e.g. when the homeowner lands on /check) so results come back quicker. */
export function warmUp(): void {
  fetch(`${API_BASE}/health`, { method: "GET" }).catch(() => undefined);
}
