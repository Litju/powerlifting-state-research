import type { Page } from "@playwright/test";

export const ROUTES = ["/", "/lab", "/journey", "/benchmarks", "/forecast", "/publication", "/about"];

export async function settle(page: Page, ms = 800) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(ms);
}

export async function viewState(page: Page): Promise<{ dAz: number; dEl: number; zoom: number }> {
  const raw = await page.getByTestId("scene-wrap").getAttribute("data-view");
  return JSON.parse(raw ?? "{}");
}

/** Scroll so that a given story beat sits on the reading line (centre of the area below the header). */
export async function toBeat(page: Page, beat: string, fraction = 0.3) {
  await page.evaluate(
    ([beat, fraction]) => {
      const el = document.querySelector(`[data-beat="${beat}"]`);
      if (!el) throw new Error(`no beat ${beat}`);
      const r = el.getBoundingClientRect();
      const header = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--header-h")) || 56;
      const line = header + (innerHeight - header) / 2;
      window.scrollTo({ top: scrollY + r.top + r.height * Number(fraction) - line, behavior: "instant" });
    },
    [beat, fraction] as const,
  );
  await page.waitForTimeout(500);
}

/** Wait until the lazily loaded WebGL scene is mounted. */
export async function sceneReady(page: Page) {
  await page.mouse.wheel(0, 1);
  await page.getByTestId("scene-canvas").waitFor({ state: "visible", timeout: 20_000 });
}
