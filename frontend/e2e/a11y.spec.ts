/**
 * Every page of the homeowner journey, at phone and desktop width:
 * - no WCAG 2.1 A/AA problems that axe can find (contrast, names, labels, structure)
 * - no sideways scrolling
 * - every control reached with Tab shows a visible focus indicator
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import assessFixture from "./fixtures/assess.json" with { type: "json" };
import tariffsFixture from "./fixtures/tariffs.json" with { type: "json" };

const SUMMARY = {
  summary: "Not yet: at about £6,500 fitted, a 10 kWh battery takes longer to pay back than its 10-year warranty.",
  model: "claude-haiku-5-5",
};

const PAGES: { name: string; path: string; ready: string }[] = [
  { name: "landing", path: "/", ready: "h1" },
  { name: "home setup", path: "/check", ready: "h1" },
  { name: "choose route", path: "/check/usage?ev=planning", ready: "h1" },
  { name: "estimate", path: "/check/usage/estimate?route=estimate", ready: "h1" },
  { name: "upload", path: "/check/usage/upload?route=upload", ready: "h1" },
  { name: "confirm", path: "/check/confirm?kwh=3000&prop=semi&route=estimate&tariff=octopusGo", ready: "h1" },
  { name: "results", path: "/check/results?kwh=3000&prop=semi&route=estimate&tariff=octopusGo", ready: "#verdict-heading" },
  { name: "tariff updates", path: "/tariff-updates", ready: "h1" },
  { name: "how we calculate", path: "/how-we-calculate", ready: "h1" },
  { name: "privacy", path: "/privacy", ready: "h1" },
  { name: "legal", path: "/legal", ready: "h1" },
  { name: "contact", path: "/contact", ready: "h1" },
];

/** Answer every API call from fixtures, so the pages render the same everywhere. */
async function stubApi(page: Page) {
  await page.route(/\/api\/v2\/assess$/, (r) => r.fulfill({ json: assessFixture }));
  await page.route(/\/api\/v2\/summary$/, (r) => r.fulfill({ json: SUMMARY }));
  await page.route(/\/api\/epc\//, (r) => r.fulfill({ json: [] }));
  await page.route(/\/api\/tariffs$/, (r) => r.fulfill({ json: tariffsFixture }));
  await page.route(/\/health$/, (r) => r.fulfill({ json: { status: "ok" } }));
}

async function open(page: Page, path: string, ready: string) {
  await stubApi(page);
  await page.goto(path);
  await page.locator(ready).first().waitFor();
  await page.waitForLoadState("networkidle");
}

for (const p of PAGES) {
  test.describe(p.name, () => {
    test("has no automatically detectable WCAG 2.1 AA problems", async ({ page }) => {
      await open(page, p.path, p.ready);
      // Check hidden-until-opened content too (tables behind "Show the figures").
      await page.evaluate(() => document.querySelectorAll("details").forEach((d) => { d.open = true; }));
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const summary = results.violations.map((v) =>
        `${v.id} (${v.impact}): ${v.help}\n` + v.nodes.slice(0, 5).map((n) => `   ${n.target.join(" ")}  ${n.failureSummary?.split("\n")[1] ?? ""}`).join("\n"));
      expect(summary, summary.join("\n\n")).toEqual([]);
    });

    test("doesn't scroll sideways", async ({ page }) => {
      await open(page, p.path, p.ready);
      const wide = await page.evaluate(() => {
        const w = document.documentElement.clientWidth;
        return document.documentElement.scrollWidth > w
          ? [...document.querySelectorAll("body *")]
              .filter((e) => e.getBoundingClientRect().right > w + 1 && !e.closest("[role=region]"))
              .slice(0, 5).map((e) => `${e.tagName.toLowerCase()}.${String(e.className).slice(0, 60)}`)
          : [];
      });
      expect(wide).toEqual([]);
    });

    test("shows where keyboard focus is", async ({ page, isMobile }) => {
      test.skip(isMobile, "Keyboard focus is checked at desktop width");
      await open(page, p.path, p.ready);
      const missing: string[] = [];
      for (let i = 0; i < 60; i++) {
        await page.keyboard.press("Tab");
        const info = await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null;
          if (!el || el === document.body) return null;
          // Next's dev-only error overlay isn't part of the page.
          if (el.tagName === "NEXTJS-PORTAL") return { key: "", visible: true, label: "" };
          const ring = (e: Element) => {
            const s = getComputedStyle(e);
            return (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== "none";
          };
          // The indicator may be drawn on the control or, for a card whose whole area is the
          // link, on the card around it (:has(:focus-visible)).
          // A visually hidden radio or checkbox draws its ring on its label.
          let visible = ring(el) || [...((el as HTMLInputElement).labels ?? [])].some(ring)
            || (!!el.nextElementSibling && ring(el.nextElementSibling));
          for (let p = el.parentElement, n = 0; !visible && p && n < 3; p = p.parentElement, n++) visible = ring(p);
          const label = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("name") || el.tagName).trim().slice(0, 40);
          return { key: `${el.tagName}|${label}`, visible, label: `${el.tagName.toLowerCase()} "${label}"` };
        });
        if (!info) break;
        if (!info.visible && !missing.includes(info.label)) missing.push(info.label);
      }
      expect(missing, `No visible focus indicator on: ${missing.join(", ")}`).toEqual([]);
    });
  });
}
