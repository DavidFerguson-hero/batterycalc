/**
 * The switch from the classic calculator to /check (task 2.11).
 */
import { expect, test } from "@playwright/test";

test("/calculator redirects permanently to /check", async ({ request }) => {
  const r = await request.get("/calculator", { maxRedirects: 0 });
  expect(r.status()).toBe(308);
  expect(r.headers()["location"]).toBe("/check");
});

test("every landing page call to action goes to /check", async ({ page }) => {
  await page.goto("/");
  const hrefs = await page.locator("a").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  expect(hrefs).not.toContain("/calculator");
  expect(hrefs.filter((h) => h === "/check").length).toBeGreaterThanOrEqual(3);
});

test("the classic calculator is still there for now, but not indexed", async ({ page }) => {
  await page.goto("/calculator-classic");
  await expect(page.getByText("This is the old calculator")).toBeVisible();
  await expect(page.locator('iframe[src="/calculator.html"]')).toHaveCount(1);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
});

test("/check is indexable", async ({ page }) => {
  await page.goto("/check");
  await expect(page.locator('meta[name="robots"]')).not.toHaveAttribute("content", /noindex/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://www.batterysizer.co.uk/check");
});
