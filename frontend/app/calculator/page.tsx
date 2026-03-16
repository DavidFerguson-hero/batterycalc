import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home Battery Size Calculator — Instant UK Results",
  description:
    "Upload your half-hourly smart meter CSV or enter your annual usage to find the best home battery size and tariff for your home. Compare payback periods across all major UK tariffs — free.",
  alternates: {
    canonical: "https://www.batterysizer.co.uk/calculator",
  },
};

export default function CalculatorPage() {
  return (
    <iframe
      src="/calculator.html"
      style={{ display: "block", width: "100%", height: "100vh", border: "none" }}
      title="BatterySizer Calculator"
    />
  );
}
