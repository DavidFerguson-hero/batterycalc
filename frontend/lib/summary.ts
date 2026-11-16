/** Helpers for sharing and the printable one-page summary (story H22). */

/** The cumulative £ position at a few milestone years (only years the chart has). */
export function milestones(years: number[], values: number[], at: number[] = [0, 5, 10, 15]): { year: number; value: number }[] {
  return at
    .map((y) => ({ year: y, i: years.indexOf(y) }))
    .filter((m) => m.i >= 0 && values[m.i] !== undefined)
    .map((m) => ({ year: m.year, value: values[m.i]! }));
}

/** What a shared link carries. Uploaded files never go in the link, so say so on that route. */
export function shareNote(route: "estimate" | "upload"): string {
  return route === "upload"
    ? "The link holds your answers but not your usage file, which we never keep. Whoever opens it will need to add the file again to see this result."
    : "The link holds your answers, so anyone who opens it sees the same result.";
}

/** The page address without the protocol, for printing (e.g. "batterysizer.co.uk/check/results?…"). */
export function printableUrl(href: string): string {
  return href.replace(/^https?:\/\//, "");
}
