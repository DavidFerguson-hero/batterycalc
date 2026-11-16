/**
 * The homeowner's answers, kept in the page's query string so any step or result
 * can be bookmarked or shared without a database (story H22).
 *
 * One place reads and writes the query; each step adds its own fields here.
 * Values left at their default are omitted, so links stay short and readable,
 * e.g. /check/usage?ev=planning&hp=have
 */

export type Ownership = "none" | "have" | "planning";

export const HOME_ITEMS = ["solar", "heat_pump", "ev", "battery"] as const;
export type HomeItem = (typeof HOME_ITEMS)[number];

export type HomeSetup = Record<HomeItem, Ownership>;

/** How we'll learn the home's electricity use: real smart meter data, or a quick estimate. */
export type Route = "upload" | "estimate";
export const ROUTES: readonly Route[] = ["upload", "estimate"];

export interface Journey {
  home: HomeSetup;
  route: Route | null;   // null until chosen
}

/** Query-string keys for each home item (short, so shared links stay tidy). */
export const HOME_KEYS: Record<HomeItem, string> = {
  solar: "solar",
  heat_pump: "hp",
  ev: "ev",
  battery: "batt",
};

const OWNERSHIP: readonly Ownership[] = ["none", "have", "planning"];

export const DEFAULT_JOURNEY: Journey = {
  home: { solar: "none", heat_pump: "none", ev: "none", battery: "none" },
  route: null,
};

const ROUTE_KEY = "route";

/** Where each route's own step lives. */
export const ROUTE_PATHS: Record<Route, string> = {
  upload: "/check/usage/upload",
  estimate: "/check/usage/estimate",
};

type QueryLike = URLSearchParams | string | { toString(): string };

function asParams(q: QueryLike): URLSearchParams {
  return q instanceof URLSearchParams ? q : new URLSearchParams(q.toString());
}

function ownership(v: string | null): Ownership {
  return OWNERSHIP.includes(v as Ownership) ? (v as Ownership) : "none";
}

/** Read the journey from a query string. Unknown or invalid values fall back to defaults. */
export function parseJourney(q: QueryLike): Journey {
  const p = asParams(q);
  const home = { ...DEFAULT_JOURNEY.home };
  for (const item of HOME_ITEMS) home[item] = ownership(p.get(HOME_KEYS[item]));
  const r = p.get(ROUTE_KEY);
  const route = ROUTES.includes(r as Route) ? (r as Route) : null;
  return { home, route };
}

/**
 * Write the journey into a query string, keeping any parameters this module doesn't
 * know about (so later steps' answers survive an earlier step being changed).
 */
export function writeJourney(j: Journey, existing: QueryLike = ""): string {
  const p = asParams(existing);
  const out = new URLSearchParams(p);
  for (const item of HOME_ITEMS) {
    const key = HOME_KEYS[item];
    if (j.home[item] === "none") out.delete(key);
    else out.set(key, j.home[item]);
  }
  if (j.route) out.set(ROUTE_KEY, j.route);
  else out.delete(ROUTE_KEY);
  out.sort();
  return out.toString();
}

/** A link to a step that carries the current answers. */
export function stepHref(path: string, query: string): string {
  return query ? `${path}?${query}` : path;
}

/** The query with the route set, ready to link to that route's step. */
export function withRoute(route: Route, query: QueryLike): string {
  return writeJourney({ ...parseJourney(query), route }, query);
}

/** True when the homeowner hasn't picked anything (all "none"). */
export function hasNothing(home: HomeSetup): boolean {
  return HOME_ITEMS.every((i) => home[i] === "none");
}

/**
 * The parts of the v2 assess request this step decides. The API models EVs and heat
 * pumps directly; solar and an existing battery are context for the results page.
 */
export function homeToRequest(home: HomeSetup): {
  ev: { status: Ownership };
  heat_pump: { status: Ownership };
} {
  return { ev: { status: home.ev }, heat_pump: { status: home.heat_pump } };
}
