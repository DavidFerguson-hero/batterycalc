"use client";

import { useState } from "react";
import {
  Area, Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import type { AssessResponse } from "@/lib/api";
import { slotTime, summariseDay } from "@/lib/dayinlife";

type Season = "summer" | "winter" | "average";
const NAMES: Record<Season, string> = { summer: "Summer", winter: "Winter", average: "Average" };
const k1 = (n: number) => `${(Math.round(n * 10) / 10).toLocaleString("en-GB")} kWh`;

/** A modelled summer and winter day: when the battery charges and how much of the home it runs (H15). */
export default function DayInLife({ data }: { data: AssessResponse }) {
  const dil = data.day_in_life;
  const seasons = (["winter", "summer"] as const).filter((s) => dil[s]);
  const options: Season[] = seasons.length ? [...seasons] : ["average"];
  const [season, setSeason] = useState<Season>(options[0]);
  const day = dil[season] ?? dil.average;
  const s = summariseDay(day);
  const cap = data.recommendation.battery_kwh;

  const rows = day.load.map((_, i) => ({
    t: slotTime(i),
    grid: day.grid_to_home[i] ?? 0,
    battery: day.from_battery[i] ?? 0,
    charging: day.grid_to_battery[i] ?? 0,
    level: day.battery_level[i] ?? 0,
  }));

  return (
    <section aria-labelledby="day-heading">
      <h2 id="day-heading" className="mb-1 text-xl font-semibold">A day with the battery</h2>
      {options.length > 1 && (
        <div role="group" aria-label="Choose a day" className="mb-3 inline-flex rounded-full border border-slate-600 p-1">
          {options.map((o) => (
            <button key={o} type="button" aria-pressed={season === o} onClick={() => setSeason(o)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-white ${
                season === o ? "bg-[#f97316] text-[#0a1628]" : "text-slate-200 hover:text-white"}`}>
              {NAMES[o]} day
            </button>
          ))}
        </div>
      )}
      <p className="mb-4 text-sm text-slate-300" aria-live="polite">
        On a typical {NAMES[season].toLowerCase()} day your home uses about {k1(s.use)}.{" "}
        {s.window
          ? <>The battery charges {k1(s.charged)} from the grid, mostly {s.window}, when electricity is cheapest, then runs
            about {Math.round(s.share * 100)}% of your home ({k1(s.fromBattery)}) when it&apos;s dearer.</>
          : <>The battery doesn&apos;t charge from the grid on this day.</>}
      </p>

      <div className="h-72 w-full rounded-xl border border-slate-700 bg-[#0f1f38] p-2 sm:p-4" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart accessibilityLayer={false} data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#1e3354" vertical={false} />
            <XAxis dataKey="t" interval={7} tick={{ fill: "#cbd5e1", fontSize: 12 }} stroke="#475569" />
            <YAxis yAxisId="flow" tick={{ fill: "#cbd5e1", fontSize: 12 }} stroke="#475569" width={40}
              label={{ value: "kWh per half hour", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11, dy: 50 }} />
            <YAxis yAxisId="level" orientation="right" domain={[0, cap]} tick={{ fill: "#cbd5e1", fontSize: 12 }}
              stroke="#475569" width={36} />
            <Tooltip
              contentStyle={{ background: "#13233d", border: "1px solid #475569", borderRadius: 8, color: "#f1f5f9" }}
              formatter={(v) => k1(Number(v))}
            />
            <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: 12 }} />
            <Area yAxisId="flow" dataKey="grid" name="Home from the grid" stackId="home" type="stepAfter"
              stroke="#64748b" fill="#64748b" fillOpacity={0.5} isAnimationActive={false} />
            <Area yAxisId="flow" dataKey="battery" name="Home from the battery" stackId="home" type="stepAfter"
              stroke="#f97316" fill="#f97316" fillOpacity={0.6} isAnimationActive={false} />
            <Bar yAxisId="flow" dataKey="charging" name="Charging the battery" fill="#38bdf8" isAnimationActive={false} />
            <Line yAxisId="level" dataKey="level" name="Battery level (right scale)" stroke="#f1f5f9" strokeWidth={2}
              strokeDasharray="4 3" dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-slate-200 underline underline-offset-4">Show the half-hours as a table (kWh)</summary>
        <div className="mt-2 max-h-72 overflow-auto rounded-lg border border-slate-700" tabIndex={0} role="region" aria-label="Half-hourly figures">
          <table className="w-full text-right text-sm">
            <caption className="sr-only">{NAMES[season]} day, kWh in each half hour</caption>
            <thead className="sticky top-0 bg-[#13233d] text-slate-200">
              <tr>
                <th scope="col" className="px-3 py-2 text-left">Time</th>
                <th scope="col" className="px-3 py-2">Home use</th>
                <th scope="col" className="px-3 py-2">From battery</th>
                <th scope="col" className="px-3 py-2">Charging</th>
                <th scope="col" className="px-3 py-2">Battery level</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.t} className="border-t border-slate-800 text-slate-200">
                  <th scope="row" className="px-3 py-1 text-left font-normal">{r.t}</th>
                  <td className="px-3 py-1">{(day.load[i] ?? 0).toFixed(2)}</td>
                  <td className="px-3 py-1">{r.battery.toFixed(2)}</td>
                  <td className="px-3 py-1">{r.charging.toFixed(2)}</td>
                  <td className="px-3 py-1">{r.level.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
