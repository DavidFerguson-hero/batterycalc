import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // The old calculator moved to /calculator-classic when /check replaced it (task 2.11).
      { source: "/calculator", destination: "/check", permanent: true },
    ];
  },
};

export default nextConfig;
