import type { Metadata } from "next";
import Link from "next/link";

import InfoPage from "@/components/InfoPage";
import { CONTACT_EMAIL, OPERATOR, POLICIES_UPDATED } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What BatterySizer does with your information: your smart meter data is used only to work out your answer and is never stored.",
  alternates: { canonical: "https://www.batterysizer.co.uk/privacy" },
};

export default function PrivacyPage() {
  return (
    <InfoPage
      title="Privacy"
      intro={<p>The short version: no account, no cookies, no tracking. Your smart meter data is used to work out your answer and then thrown away. It&apos;s never stored.</p>}
    >
      <h2>Who we are</h2>
      <p>
        BatterySizer is run by {OPERATOR}, an individual in the UK, who is responsible for your information under UK data
        protection law (the UK GDPR, General Data Protection Regulation). Contact:{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>

      <h2>What we use, and why</h2>
      <table>
        <caption className="sr-only">Information BatterySizer uses</caption>
        <thead><tr><th scope="col">Information</th><th scope="col">What happens to it</th></tr></thead>
        <tbody>
          <tr>
            <td>Smart meter data you upload</td>
            <td>Sent to our calculation server, read in memory to work out your answer, then discarded. It&apos;s never saved to disk, written to logs or shared with anyone.</td>
          </tr>
          <tr>
            <td>Your answers (home type, yearly use, tariff, car, heat pump, panels)</td>
            <td>Kept in the page&apos;s web address so the back button and share links work. Anyone you send a link to sees these answers, but nothing else.</td>
          </tr>
          <tr>
            <td>Your postcode, if you look up your home</td>
            <td>Sent to the government&apos;s EPC (Energy Performance Certificate) register to find your home&apos;s details. It isn&apos;t stored, and it never goes into the web address.</td>
          </tr>
          <tr>
            <td>Your results, for the AI summary</td>
            <td>
              The headline figures on your results page (not your meter data or postcode) are sent to Anthropic, whose AI
              Claude writes the &ldquo;In a nutshell&rdquo; paragraph. Under Anthropic&apos;s commercial terms, this isn&apos;t
              used to train their models.
            </td>
          </tr>
          <tr>
            <td>Your IP address (your connection&apos;s internet address)</td>
            <td>
              Seen by our hosting providers in their standard server logs. Our server also holds it in memory for up to an
              hour to limit how many AI summaries one address can ask for.
            </td>
          </tr>
        </tbody>
      </table>
      <p>
        We don&apos;t use cookies, analytics or advertising trackers, and we don&apos;t sell or share your information. If we
        add privacy-friendly visitor counts, this page will say so first.
      </p>

      <h2>Who else handles it</h2>
      <ul>
        <li><strong>Vercel</strong> hosts the website.</li>
        <li><strong>Render</strong> hosts the calculation server.</li>
        <li><strong>Anthropic</strong> writes the AI summary.</li>
        <li><strong>The EPC register</strong> (Ministry of Housing, Communities and Local Government) answers postcode lookups.</li>
      </ul>
      <p>Some of these providers may process data outside the UK, under the safeguards UK law requires.</p>

      <h2>The legal basis</h2>
      <p>
        We use your information because you&apos;ve asked us to work out an answer for you (legitimate interests), and only
        for that.
      </p>

      <h2>The classic calculator</h2>
      <p>
        The old calculator at <Link href="/calculator-classic">/calculator-classic</Link> is available until 16 December
        2026. It works differently:
      </p>
      <ul>
        <li>It keeps uploaded data in server memory for up to an hour, so you can change settings without uploading again.</li>
        <li>Its AI explanation sends your usage figures and postcode to Anthropic.</li>
        <li>Its solar estimate sends your postcode to postcodes.io and the European Commission&apos;s PVGIS (Photovoltaic Geographical Information System) solar service.</li>
      </ul>

      <h2>Your rights</h2>
      <p>
        Because we don&apos;t keep your information, there&apos;s normally nothing for us to show, correct or delete. You can
        still ask, or complain, by emailing <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. You can also complain
        to the Information Commissioner&apos;s Office (ICO) at{" "}
        <a href="https://ico.org.uk/make-a-complaint/" rel="noopener">ico.org.uk</a>.
      </p>

      <p className="text-sm text-slate-400">Last updated {POLICIES_UPDATED}.</p>
    </InfoPage>
  );
}
