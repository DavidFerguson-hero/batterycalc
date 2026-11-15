/**
 * Serves /calculator-config.js for the classic calculator (public/calculator.html).
 *
 * calculator.html is a static file, so it can't read env vars itself. This route
 * is rendered once at build time and bakes NEXT_PUBLIC_API_URL into a tiny script
 * that sets window.BATTERYSIZER_API_BASE before the calculator code runs.
 */
export const dynamic = "force-static";

export function GET() {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");
  const body = `window.BATTERYSIZER_API_BASE = ${JSON.stringify(apiBase)};\n`;
  return new Response(body, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  });
}
