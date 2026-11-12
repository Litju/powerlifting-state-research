import { expect, test } from "@playwright/test";
import { settle } from "./helpers";

const CONCEPTUAL = ["observe", "question", "capacity", "suppression", "noise", "inverse", "boundary", "ledger"];

test.describe("fallbacks", () => {
  test("reduced motion: no sticky stage, no WebGL, every beat carries its own figure or evidence panel", async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "desktop project");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await settle(page, 600);
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "inline");
    await expect(page.getByTestId("scene-canvas")).toHaveCount(0);
    await expect(page.getByTestId("stage")).toBeHidden();
    for (const id of CONCEPTUAL) await expect(page.locator(`[data-beat="${id}"] [data-testid=schematic]`)).toBeVisible();
    await expect(page.locator('[data-beat="g2"] [data-testid=g2-waffle]')).toBeVisible();
    await expect(page.locator('[data-beat="ridge"]')).toContainText("+0.1103 kg [+0.0679, +0.1487]");
    const sticky = await page.evaluate(() => [...document.querySelectorAll("main *")].filter((e) => getComputedStyle(e).position === "sticky").length);
    expect(sticky).toBe(0);
  });

  test("WebGL unavailable: semantic figure on the stage, no canvas, no blank page", async ({ page }, info) => {
    test.skip(info.project.name !== "no-webgl", "needs the WebGL-off project");
    await page.goto("/");
    await settle(page, 600);
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "stage-figure");
    await expect(page.getByTestId("scene-canvas")).toHaveCount(0);
    await expect(page.getByTestId("stage").getByTestId("schematic")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("What can noisy observations");
    await expect(page.getByTestId("scene-caption")).toHaveText(/not measured data/);
  });

  test("forced WebGL-off query uses the figure stage", async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "needs WebGL project");
    await page.goto("/?scene=off");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "stage-figure");
    await expect(page.getByTestId("stage").getByTestId("schematic")).toBeVisible();
  });

  test("low-end hint keeps the scene but lowers quality", async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "needs WebGL project");
    await page.goto("/?scene=low");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "stage-webgl");
    await page.mouse.wheel(0, 1);
    await expect(page.getByTestId("scene-canvas")).toBeVisible({ timeout: 20_000 });
  });

  test("phones never download the WebGL chunk", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "mobile project");
    await page.goto("/");
    await settle(page, 3000);
    await page.mouse.wheel(0, 2000);
    await settle(page, 1500);
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "inline");
    await expect(page.getByTestId("scene-canvas")).toHaveCount(0);
    // three.js registers window.__THREE__ when its module is evaluated.
    expect(await page.evaluate(() => (window as unknown as { __THREE__?: string }).__THREE__)).toBeUndefined();
  });
});
