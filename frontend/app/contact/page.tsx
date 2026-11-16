import type { Metadata } from "next";
import Link from "next/link";

import InfoPage from "@/components/InfoPage";
import { CONTACT_EMAIL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: "Get in touch with BatterySizer: questions, mistakes you've spotted, or ideas.",
  alternates: { canonical: "https://www.batterysizer.co.uk/contact" },
};

export default function ContactPage() {
  return (
    <InfoPage title="Contact" intro={<p>Questions, a mistake you&apos;ve spotted, or an idea? I&apos;d like to hear it.</p>}>
      <p className="text-lg">
        Email <a href={`mailto:${CONTACT_EMAIL}`} className="font-semibold text-white">{CONTACT_EMAIL}</a>
      </p>
      <p>BatterySizer is run by one person, so replies can take a few days.</p>

      <h2>Helpful to include</h2>
      <ul>
        <li>If it&apos;s about your result, use &ldquo;Copy link&rdquo; on your results page and paste the link. It holds your answers, but not your meter data or postcode.</li>
        <li>If a tariff or price looks out of date, tell us which one and where you saw the current figure.</li>
      </ul>
      <p>
        Please don&apos;t send your smart meter data file by email. We don&apos;t need it to answer, and we&apos;d rather not hold it.
      </p>

      <h2>Before you write</h2>
      <ul>
        <li><Link href="/how-we-calculate">How we calculate</Link> explains the method and the assumptions.</li>
        <li><Link href="/privacy">Privacy</Link> explains what happens to your information.</li>
      </ul>
    </InfoPage>
  );
}
