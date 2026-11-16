"use client";

import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import type { AssessResponse } from "@/lib/api";
import { gbp, years } from "@/lib/format";

/**
 * Cumulative £ over the battery's life: the likely line, with the range between the
 * pessimistic and optimistic cases shaded. Below zero = still paying off the battery.
 * The same figures are always available as a table for people who can't use the chart.
 */
export default function BreakEvenChart({ data }: { data: AssessResponse }) {
  const be = data.break_even;
  const payback = data.headline.payback_years.likely;
  const life = data.assumptions.battery_life_years;
  const rows = be.years.map((y, i) => ({
    year: y,
    likely: be.likely[i],
    range: [Math.min(be.pessimistic[i], be.optimistic[i]), Math.max(be.pessimistic[i], be.optimistic[i])],
    pessimistic: be.pessimistic[i],
    optimistic: be.optimistic[i],
  }));

  const summary = `Starting at ${gbp(be.likely[0])} on the day it's fitted, the battery ${
    payback === null ? `doesn't pay back within ${life} years in the likely case` : `pays back after about ${years(payback)} in the likely case`
  } and ends ${gbp(be.likely[be.likely.length - 1])} ${be.likely[be.likely.length - 1] >= 0 ? "ahead" : "behind"} after ${life} years.`;

  return (
    <figure aria-labelledby="breakeven-heading">
      <h2 id="breakeven-heading" className="mb-1 text-xl font-semibold">When it pays back</h2>
      <figcaption className="mb-4 text-sm text-slate-300">
        {summary} The shaded band shows the range from a pessimistic case (higher price, slower rises in energy prices)
        to an optimistic one. The dip in year {data.assumptions.inverter_replacement_year ?? 10} is the inverter being replaced.
      </figcaption>

      <div className="h-72 w-full rounded-xl border border-slate-700 bg-[#0f1f38] p-2 sm:p-4" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 10, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="#1e3354" vertical={false} />
            <XAxis dataKey="year" type="number" domain={[0, life]} ticks={be.years} allowDecimals={false}
              tick={{ fill: "#cbd5e1", fontSize: 12 }} stroke="#475569"
              label={{ value: "Years after fitting", position: "insideBottom", offset: -2, fill: "#94a3b8", fontSize: 12 }} height={36} />
            <YAxis tickFormatter={(v: number) => gbp(v)} tick={{ fill: "#cbd5e1", fontSize: 12 }} stroke="#475569" width={72} />
            <Tooltip
              contentStyle={{ background: "#13233d", border: "1px solid #475569", borderRadius: 8, color: "#f1f5f9" }}
              labelFormatter={(y) => `Year ${y}`}
              formatter={(value, name) => {
                if (name === "range" && Array.isArray(value)) return [`${gbp(Number(value[0]))} to ${gbp(Number(value[1]))}`, "Range"];
                return [gbp(Number(value)), "Likely"];
              }}
            />
            <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
            {payback !== null && (
              <ReferenceLine x={payback} stroke="#4ade80" strokeDasharray="3 3"
                label={{ value: `Pays back ≈ year ${Math.round(payback * 10) / 10}`, fill: "#4ade80", fontSize: 12, position: "insideTopLeft" }} />
            )}
            <Area dataKey="range" stroke="none" fill="#f97316" fillOpacity={0.18} isAnimationActive={false} />
            <Line dataKey="likely" stroke="#f97316" strokeWidth={3} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-slate-200 underline underline-offset-4">Show the figures as a table</summary>
        <div className="mt-2 max-h-72 overflow-auto rounded-lg border border-slate-700">
          <table className="w-full text-right text-sm">
            <caption className="sr-only">Cumulative money position by year</caption>
            <thead className="sticky top-0 bg-[#13233d] text-slate-200">
              <tr>
                <th scope="col" className="px-3 py-2 text-left">Year</th>
                <th scope="col" className="px-3 py-2">Pessimistic</th>
                <th scope="col" className="px-3 py-2">Likely</th>
                <th scope="col" className="px-3 py-2">Optimistic</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.year} className="border-t border-slate-800 text-slate-200">
                  <th scope="row" className="px-3 py-1.5 text-left font-normal">{r.year}</th>
                  <td className="px-3 py-1.5">{gbp(r.pessimistic)}</td>
                  <td className="px-3 py-1.5 font-semibold text-white">{gbp(r.likely)}</td>
                  <td className="px-3 py-1.5">{gbp(r.optimistic)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
