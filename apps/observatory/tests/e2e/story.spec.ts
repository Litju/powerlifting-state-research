import { expect, test } from "@playwright/test";
import { settle, viewState } from "./helpers";

test.describe("scroll narrative and 3D interaction", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== "desktop", "desktop WebGL project");
  });

  test("renders the WebGL stage in scrub mode with the conceptual caption", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    await expect(page.getByTestId("scene-canvas")).toBeVisible();
    await expect(page.getByTestId("scene-caption")).toHaveText(/Conceptual illustration - not measured data/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("What can we know");
  });

  test("scroll drives chapters, the rail and the progress bar without trapping the page", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    const rail = page.getByRole("navigation", { name: "Story chapters" });
    await expect(rail.locator("a[aria-current=step]")).toHaveAttribute("aria-label", /Chapter 1 of 6/);
    const vh = 900;
    for (const [i, name] of [[1, /Latent capacity/], [2, /Expressed performance/], [3, /Observed Y/], [4, /Information boundary/], [5, /Evidence/]] as const) {
      await page.mouse.move(700, 450);
      await page.mouse.wheel(0, vh);
      await page.waitForTimeout(500);
      await expect(rail.locator("a[aria-current=step]")).toHaveAttribute("aria-label", name);
      expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(i * vh * 0.8);
    }
    const scale = await page.getByTestId("progress-bar").evaluate((el) => getComputedStyle(el).transform);
    expect(scale).not.toBe("none");
    // Native scrolling continues past the story to ordinary content.
    await page.mouse.wheel(0, 3000);
    await expect(page.getByRole("heading", { name: "Explore" })).toBeInViewport({ ratio: 0.1 });
  });

  test("chapter navigation by keyboard reaches the target chapter", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    await page.getByRole("list", { name: "Jump to chapter" }).getByRole("link", { name: "Observed Y" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#observation")).toBeInViewport({ ratio: 0.5 });
  });

  test("orbit by drag and keyboard, zoom, and reset", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    await settle(page);
    const initial = await viewState(page);
    expect(initial).toEqual({ dAz: 0, dEl: 0, zoom: 1 });
    const box = (await page.getByTestId("scene-wrap").boundingBox())!;
    await page.mouse.move(box.x + 700, box.y + 400);
    await page.mouse.down();
    await page.mouse.move(box.x + 820, box.y + 440, { steps: 6 });
    await page.mouse.up();
    const dragged = await viewState(page);
    expect(dragged.dAz).not.toBe(0);
    await page.getByTestId("scene-wrap").focus();
    await page.keyboard.press("ArrowRight");
    expect((await viewState(page)).dAz).toBeGreaterThan(dragged.dAz);
    await page.getByRole("button", { name: "Zoom in" }).click();
    expect((await viewState(page)).zoom).toBeLessThan(1);
    await page.getByTestId("scene-reset").click();
    expect(await viewState(page)).toEqual(initial);
  });

  test("toggles for dynamics, observation noise and information boundary are real controls", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    for (const name of ["Dynamics", "Observation noise", "Information boundary"]) {
      const b = page.getByRole("toolbar", { name: "Scene controls" }).getByRole("button", { name, exact: true });
      await expect(b).toHaveAttribute("aria-pressed", "true");
      await b.click();
      await expect(b).toHaveAttribute("aria-pressed", "false");
    }
  });

  test("the canvas actually draws (non-blank pixels)", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    await settle(page, 1500);
    const shot = await page.getByTestId("stage").screenshot();
    // A blank stage would compress to a tiny, uniform PNG.
    expect(shot.length).toBeGreaterThan(20_000);
  });
});
