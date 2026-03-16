import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const BASE_URL = "https://www.batterysizer.co.uk";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "BatterySizer — Free Home Battery Storage Calculator UK",
    template: "%s | BatterySizer",
  },
  description:
    "Free UK home battery storage calculator. Upload your smart meter data, compare Octopus Go, Economy 7 and more, and find the exact battery size that saves you the most money — with a clear payback timeline.",
  keywords: [
    "home battery storage calculator UK",
    "best battery size for home UK",
    "battery payback calculator",
    "octopus go battery savings",
    "is a home battery worth it UK",
    "10kwh battery payback UK",
    "home battery storage size",
    "domestic battery calculator",
  ],
  authors: [{ name: "BatterySizer" }],
  creator: "BatterySizer",
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: BASE_URL,
    siteName: "BatterySizer",
    title: "BatterySizer — Free Home Battery Storage Calculator UK",
    description:
      "Find the right battery size and tariff for your home. Upload your smart meter data and get an instant, personalised payback calculation — free.",
    images: [
      {
        url: "/batterysizer-logo.png",
        width: 960,
        height: 540,
        alt: "BatterySizer — Domestic Battery Storage Calculator",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "BatterySizer — Free Home Battery Storage Calculator UK",
    description:
      "Find the right battery size and tariff for your home. Upload your smart meter data and get an instant, personalised payback calculation — free.",
    images: ["/batterysizer-logo.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: BASE_URL,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-GB">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
