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
