import type { Metadata } from "next";
import Link from "next/link";

import InfoPage from "@/components/InfoPage";
import { CONTACT_EMAIL, OPERATOR, POLICIES_UPDATED } from "@/lib/site";

export const metadata: Metadata = {
  title: "Legal disclaimer",
  description: "BatterySizer gives estimates to help you decide about a home battery. It isn't financial advice or a guarantee of savings.",
  alternates: { canonical: "https://www.batterysizer.co.uk/legal" },
};

export default function LegalPage() {
  return (
    <InfoPage
      title="Legal disclaimer"
      intro={<p>BatterySizer is a free, independent tool that estimates whether a home battery could pay for itself. Please read this before relying on it.</p>}
    >
      <h2>Estimates, not guarantees</h2>
      <p>
        Every figure is an estimate based on your answers and the assumptions explained in{" "}
        <Link href="/how-we-calculate">How we calculate</Link>. Your real savings will differ. They depend on how you use
        electricity, future energy prices, tariff changes, how the battery is set up and how well it performs.
      </p>

      <h2>Not financial advice</h2>
      <p>
        BatterySizer doesn&apos;t give financial, investment, legal or tax advice, and isn&apos;t regulated by the Financial
        Conduct Authority. Before you spend money, get quotes from MCS (Microgeneration Certification Scheme) certified
        installers and check the details with them, and take independent advice if you need it.
      </p>

      <h2>Prices and tariffs</h2>
      <p>
        Battery prices and tariff rates are checked regularly, but they change. Before you sign up for anything, check the
        current prices with the installer or supplier.
      </p>

      <h2>Independence</h2>
      <p>
        We don&apos;t sell batteries and we don&apos;t take payment from installers, manufacturers or energy suppliers. Naming
        a tariff or supplier isn&apos;t an endorsement.
      </p>

      <h2>The AI summary</h2>
      <p>
        The &ldquo;In a nutshell&rdquo; paragraph is written by AI from the figures on your results page. It can make
        mistakes, so rely on the figures themselves.
      </p>

      <h2>Our responsibility</h2>
      <p>
        BatterySizer is provided free and as it is. As far as the law allows, {OPERATOR} isn&apos;t liable for any loss that
        comes from relying on it, including money spent on a battery or tariff. Nothing here limits liability that
        can&apos;t be limited by law, such as for death or personal injury caused by negligence, or for fraud.
      </p>

      <h2>Data used by the calculator</h2>
      <p>
        Tariff and cost figures come from suppliers&apos; and installers&apos; published prices and government statistics.
        Typical household use comes from the Low Carbon London smart meter trial run by UK Power Networks (published under
        the CC BY 4.0 licence). Home details come from the government&apos;s EPC (Energy Performance Certificate) register.
      </p>

      <h2>Questions</h2>
      <p>
        Email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. These terms are governed by the law of England and
        Wales.
      </p>

      <p className="text-sm text-slate-400">Last updated {POLICIES_UPDATED}.</p>
    </InfoPage>
  );
}
