/**
 * Plain-English lines about solar panels for the results page (story H17).
 * The API says whether solar was modelled in usage.solar.
 */
import type { AssessResponse } from "./api-v2-types";

type SolarSummary = AssessResponse["usage"]["solar"];

const DIRECTIONS: Record<string, string> = {
  south: "south", south_east: "south-east", south_west: "south-west", east: "east", west: "west",
};

const kwh = (n: number) => `${Math.round(n).toLocaleString("en-GB")} kWh`;

/** For the "other upgrades" panel: how solar shows up in their answer. Empty without solar. */
export function solarContextNote(s: SolarSummary): string {
  if (!s) return "";
  if (!s.modelled) {
    return "Your meter readings already include your solar panels, so your answer above does too.";
  }
  const own = s.status === "have" ? "your solar panels" : "the solar panels you're planning";
  const cost = s.status === "planning" ? " The panels' own cost isn't included in the battery's figures." : "";
  return `Your answer above includes ${own}.${cost}`;
}

/** For "Our assumptions": what we assumed about the panels. Null without solar. */
export function solarAssumption(s: SolarSummary): string | null {
  if (!s) return null;
  if (!s.modelled) return "Already in your meter readings, so we use them as they are";
  const size = `${s.kwp} kWp (kilowatts peak) facing ${DIRECTIONS[s.orientation] ?? s.orientation}`;
  const spare = s.spare_kwh !== null && s.spare_kwh !== undefined
    ? `, of which about ${kwh(s.spare_kwh)} is spare without a battery` : "";
  return `${size}, making about ${kwh(s.annual_generation_kwh)} a year${spare}. Spare solar charges the battery first.`;
}
