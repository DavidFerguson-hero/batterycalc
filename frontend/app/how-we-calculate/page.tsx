import type { Metadata } from "next";
import Link from "next/link";

import InfoPage from "@/components/InfoPage";

export const metadata: Metadata = {
  title: "How we calculate",
  description:
    "How BatterySizer works out whether a home battery pays back: your usage, a half-hour by half-hour simulation on each tariff, costs, wear and a range of energy prices.",
  alternates: { canonical: "https://www.batterysizer.co.uk/how-we-calculate" },
};

export default function HowWeCalculatePage() {
  return (
    <InfoPage
      title="How we calculate"
      intro={<p>The short version: we take a year of your electricity use, work out what a battery would do with it every half hour on each tariff, then follow the money over the battery&apos;s life.</p>}
    >
      <h2>1. Your electricity use</h2>
      <h3>If you upload your smart meter data</h3>
      <p>
        We use your real half-hourly readings, up to the latest 12 months. Short gaps are filled from similar days. If you
        upload less than a year, we fill the missing months using the usual seasonal pattern (more in winter, less in
        summer) and tell you the answer is less certain.
      </p>
      <h3>If we estimate it</h3>
      <p>
        We spread your yearly use across the year using the pattern of real UK homes: how use changes through the day,
        from month to month, and from one day to the next. That pattern comes from a year of half-hourly readings from
        3,765 London homes in the Low Carbon London smart meter trial run by UK Power Networks.
      </p>
      <p>
        We tested estimates against those homes&apos; real readings. When the yearly use was right, the estimated saving
        was within 10% of the real-data answer for three homes in four, and within 20% for nine in ten. If your yearly use
        is a guess, the answer can be further out, so uploading your data gives a firmer answer.
      </p>
      <h3>Electric cars, heat pumps and solar panels</h3>
      <ul>
        <li><strong>Electric car</strong> (EV): we add charging between 00:30 and 04:30 each night for your yearly mileage (7,000 miles if you don&apos;t know it).</li>
        <li><strong>Heat pump</strong>: we add heating use, mostly in winter, sized from your home&apos;s floor area and its energy rating (EPC, Energy Performance Certificate).</li>
        <li>
          <strong>Solar panels</strong>: a typical UK roof makes about 850 kWh a year for each kWp (kilowatt peak, the panels&apos; size). We spread
          that across each day between sunrise and sunset, month by month. We don&apos;t model individual sunny or cloudy days.
        </li>
      </ul>
      <p>If you already have one of these, it&apos;s already in your meter readings, so we don&apos;t add it twice.</p>

      <h2>2. What a battery would do, half hour by half hour</h2>
      <p>For every half hour of the year, on each of the 10 time-of-use tariffs we track, and for each standard battery size, we work out:</p>
      <ul>
        <li>charging from the grid in the tariff&apos;s cheapest hours</li>
        <li>using that stored energy in the dearer hours, instead of buying from the grid</li>
        <li>storing spare solar first, and exporting what doesn&apos;t fit</li>
      </ul>
      <p>
        We allow for 10% of the energy being lost between charging and use, a charging speed of 3.6 kW (kilowatts), and a
        10% reserve that&apos;s never used. Energy left at midnight carries into the next day. Dynamic tariffs, whose prices
        change every day, are modelled using their typical daily pattern.
      </p>
      <p>
        <strong>We only count what the battery adds.</strong> Switching to a cheaper tariff can save money on its own, so
        we compare against the best tariff for you <em>without</em> a battery. We show the tariff switch separately, and
        flag it when switching alone gets you most of the saving.
      </p>

      <h2>3. What it costs</h2>
      <p>
        Fitted prices for each size come from published prices: low is online and installer packages, and high is the
        government&apos;s median for installs by MCS (Microgeneration Certification Scheme) certified installers. If you
        have a quote, try its price under &ldquo;What if…?&rdquo; on your results. Home batteries currently pay 0% VAT, until 31 March 2027.
      </p>

      <h2>4. Over the battery&apos;s life</h2>
      <table>
        <caption className="sr-only">Assumptions used over the battery&apos;s life</caption>
        <thead><tr><th scope="col">Assumption</th><th scope="col">What we use</th></tr></thead>
        <tbody>
          <tr><td>Battery life</td><td>15 years</td></tr>
          <tr><td>Warranty</td><td>10 years</td></tr>
          <tr><td>Wear</td><td>2% of capacity lost each year, so the saving shrinks a little each year</td></tr>
          <tr><td>Energy prices</td><td>Rise by 1%, 3% or 5% a year (pessimistic, likely and optimistic cases)</td></tr>
          <tr><td>Inverter</td><td>Replaced once, in year 10, at a typical £1,200</td></tr>
        </tbody>
      </table>
      <p>
        We work out three cases. Pessimistic uses the high price and slow energy-price rises; likely uses the typical
        price and 3% rises; optimistic uses the low price and fast rises. That&apos;s why you see a range, not a single figure.
      </p>
      <p>
        <strong>Payback</strong> is when the money saved overtakes what you paid, and stays ahead. The
        <strong> best-value size</strong> is the one that leaves you furthest ahead over its life in the likely case. It
        isn&apos;t always the biggest.
      </p>

      <h2>5. The verdict</h2>
      <ul>
        <li><strong>Worth it</strong>: likely payback within 7 years, well inside the 10-year warranty.</li>
        <li><strong>Borderline</strong>: pays back, but only between 7 and 10 years.</li>
        <li><strong>Not yet</strong>: unlikely to pay back within the warranty at today&apos;s prices. We show what would change that, such as a lower price.</li>
      </ul>

      <h2>6. Tariffs and the AI summary</h2>
      <p>
        Tariff rates are checked against suppliers&apos; published prices every night, and any change is reviewed before
        it&apos;s used. You can see the latest checks on <Link href="/tariff-updates">Tariff updates</Link>.
      </p>
      <p>
        The short &ldquo;In a nutshell&rdquo; paragraph is written by AI (Claude, made by Anthropic) from the figures on
        your results page. We check that it doesn&apos;t quote any £ figure that isn&apos;t on the page, and hide it if it does.
      </p>

      <h2>What we don&apos;t model</h2>
      <ul>
        <li>Payments for using less at busy times, such as suppliers&apos; saving sessions</li>
        <li>Changes in how you use electricity in future, beyond a car, heat pump or panels you tell us about</li>
        <li>Sunny and cloudy days for solar panels: every day in a month gets that month&apos;s average sunshine</li>
        <li>Borrowing costs, if you pay for the battery with a loan</li>
      </ul>
      <p>
        These are estimates to help you decide, not a guarantee or financial advice. See the{" "}
        <Link href="/legal">legal disclaimer</Link>.
      </p>
    </InfoPage>
  );
}
