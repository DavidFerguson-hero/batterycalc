import { defineConfig, devices } from "@playwright/test";

/**
 * Accessibility and phone-width checks (task 2.10). Run: npm run test:a11y
 * In CI it runs against the production build (`next start`); locally against `next dev`.
 * API calls are answered from e2e/fixtures, so no API needs to be running.
 */
const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: process.env.CI ? "list" : "line",
  use: {
    baseURL: `http://localhost:${PORT}`,
    // Locally use the installed Chrome; CI installs Playwright's Chromium.
    ...(process.env.CI ? {} : { channel: "chrome" }),
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 5"], viewport: { width: 375, height: 812 }, ...(process.env.CI ? {} : { channel: "chrome" }) } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 }, ...(process.env.CI ? {} : { channel: "chrome" }) } },
  ],
  webServer: {
    command: process.env.CI ? `npm run start -- -p ${PORT}` : `npm run dev -- -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
