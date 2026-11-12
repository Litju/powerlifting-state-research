import { expect, test } from "@playwright/test";
import { sceneReady, settle, toBeat, viewState } from "./helpers";

test.describe("six-act story on the split stage", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== "desktop", "desktop WebGL project");
  });

  test("opens on the observation, with the central question as the page heading", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "stage-webgl");
    await sceneReady(page);
    await expect(page.getByTestId("scene-caption")).toHaveText(/Illustrative simulation · not measured data/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("What can noisy observations of strength performance actually tell us about a hidden system?");
    await expect(page.getByRole("navigation", { name: "Story acts" }).locator("a[aria-current=step]")).toContainText("Observation");
    expect(await page.evaluate(() => (window as unknown as { __THREE__?: string }).__THREE__)).toBeTruthy();
  });

  test("native scroll walks through all six acts and switches from illustration to evidence", async ({ page }) => {
    await page.goto("/");
    await sceneReady(page);
    const acts = page.getByRole("navigation", { name: "Story acts" });
    const expected: [string, string, RegExp][] = [
      ["capacity", "Hidden system", /Illustrative/],
      ["inverse", "Identification", /Illustrative/],
      ["g2", "Identification", /Evidence/],
      ["boundary", "Forecasting", /Illustrative/],
      ["ridge", "Forecasting", /Evidence/],
      ["history", "Uncertainty", /Evidence/],
      ["ledger", "Evidence", /Illustrative/],
    ];
    let lastY = 0;
    for (const [beat, act, badge] of expected) {
      await toBeat(page, beat);
      await expect(acts.locator("a[aria-current=step]")).toContainText(act);
      await expect(page.getByTestId("scene-caption")).toHaveText(badge);
      const y = await page.evaluate(() => window.scrollY);
      expect(y).toBeGreaterThan(lastY);
      lastY = y;
    }
    const fill = await page.getByTestId("progress-bar").evaluate((el) => getComputedStyle(el).transform);
    expect(fill).not.toBe("none");
    // Native scrolling continues past the story into the footer: nothing is trapped.
    await page.mouse.move(300, 400);
    for (let i = 0; i < 12; i += 1) await page.mouse.wheel(0, 900);
    await expect(page.getByRole("contentinfo")).toBeInViewport({ ratio: 0.2 });
  });

  test("evidence panels show real aggregate values and respond to their controls", async ({ page }) => {
    await page.goto("/");
    await sceneReady(page);
    await toBeat(page, "ridge");
    const ridge = page.getByTestId("panel-ridge");
    await expect(ridge).toBeVisible();
    await expect(page.getByTestId("stage-ridge-readout")).toContainText("TEST_A: GRU minus Ridge +0.1103 kg [+0.0679, +0.1487]");
    await ridge.getByRole("button", { name: "TEST_B" }).click();
    await expect(page.getByTestId("stage-ridge-readout")).toContainText("TEST_B: GRU minus Ridge +0.0916 kg [+0.0524, +0.1333]");
    await toBeat(page, "history");
    const unc = page.getByTestId("panel-uncertainty");
    await expect(unc).toContainText("Adding 127 history features made the forecasts slightly worse");
    await expect(page.getByTestId("stage-uncertainty-readout")).toContainText("H_HISTORY − B_MAG +0.0242 kg [+0.0180, +0.0308]");
    await toBeat(page, "g2");
    const g2 = page.getByTestId("panel-g2");
    await expect(g2).toContainText("7 of 256 full-model fits converged");
    await g2.getByRole("button", { name: "Doubled noise" }).click();
    await expect(g2).toContainText("22 of 256 full-model fits converged");
    await expect(g2).toContainText("FULL_G2_IDENTIFICATION_UNSUPPORTED");
  });

  test("act navigation is keyboard reachable and lands on the act", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("navigation", { name: "The six acts" }).getByRole("link", { name: /Forecasting/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#forecasting h2")).toBeInViewport();
    await expect(page).toHaveURL(/#forecasting$/);
  });

  test("orbit by drag and keyboard, zoom, layer focus and reset", async ({ page }) => {
    await page.goto("/");
    await sceneReady(page);
    await settle(page);
    expect(await viewState(page)).toEqual({ dAz: 0, dEl: 0, zoom: 1 });
    const box = (await page.getByTestId("scene-wrap").boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 30, { steps: 6 });
    await page.mouse.up();
    const dragged = await viewState(page);
    expect(dragged.dAz).not.toBe(0);
    await page.getByTestId("scene-wrap").focus();
    await page.keyboard.press("ArrowRight");
    expect((await viewState(page)).dAz).toBeGreaterThan(dragged.dAz);
    await page.getByRole("button", { name: "Zoom in" }).click();
    expect((await viewState(page)).zoom).toBeLessThan(1);
    const focus = page.getByRole("group", { name: "Focus a layer" }).getByRole("button", { name: "Y observed" });
    await focus.click();
    await expect(focus).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("scene-reset").click();
    expect(await viewState(page)).toEqual({ dAz: 0, dEl: 0, zoom: 1 });
    await expect(focus).toHaveAttribute("aria-pressed", "false");
  });

  test("hovering an observation reads its illustrative values", async ({ page }) => {
    await page.goto("/");
    await sceneReady(page);
    await settle(page, 1200);
    const box = (await page.getByTestId("scene-wrap").boundingBox())!;
    const readout = page.getByTestId("scene-readout");
    let found = false;
    for (let x = box.x + 20; x < box.x + box.width - 20 && !found; x += 6) {
      for (const y of [0.45, 0.5, 0.55, 0.6, 0.65, 0.7]) {
        await page.mouse.move(x, box.y + box.height * y);
        if (/Day \d+ · Y/.test((await readout.textContent()) ?? "")) {
          found = true;
          break;
        }
      }
    }
    expect(found).toBe(true);
    await expect(readout).toContainText("(illustrative)");
  });

  test("the canvas actually draws (non-blank pixels)", async ({ page }) => {
    await page.goto("/");
    await sceneReady(page);
    await settle(page, 1500);
    const shot = await page.getByTestId("scene-wrap").screenshot();
    expect(shot.length).toBeGreaterThan(15_000);
  });
});
