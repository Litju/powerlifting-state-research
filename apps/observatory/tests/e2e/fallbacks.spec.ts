import { expect, test } from "@playwright/test";
import { settle } from "./helpers";

test.describe("fallbacks", () => {
  test("reduced motion: static camera, no scroll scrubbing, same information", async ({ page, browserName }, info) => {
    test.skip(info.project.name !== "desktop", "needs WebGL project");
    void browserName;
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "static");
    await expect(page.getByTestId("progress-bar")).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "Story chapters" })).toHaveCount(0);
    // Every chapter is present as text with its own semantic diagram.
    for (const id of ["capacity", "expression", "observation", "boundary", "evidence"]) {
      await expect(page.locator(`#${id} [data-testid=schematic]`)).toHaveCount(1);
    }
    await expect(page.getByTestId("scene-caption")).toBeVisible();
    // The stage is not sticky.
    const pos = await page.getByTestId("stage").evaluate((el) => getComputedStyle(el).position);
    expect(pos).not.toBe("sticky");
  });

  test("WebGL unavailable: semantic diagram and text, no blank page", async ({ page }, info) => {
    test.skip(info.project.name !== "no-webgl", "needs the WebGL-off project");
    await page.goto("/");
    await settle(page, 400);
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "diagram");
    await expect(page.getByTestId("scene-canvas")).toHaveCount(0);
    await expect(page.getByTestId("schematic").first()).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("What can we know");
    await expect(page.getByText("Conceptual illustration - not measured data")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Two honest negatives/ })).toBeAttached();
  });

  test("forced WebGL-off query uses the diagram", async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "needs WebGL project");
    await page.goto("/?scene=off");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "diagram");
  });

  test("low-end hint keeps the scene but lowers quality", async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "needs WebGL project");
    await page.goto("/?scene=low");
    await expect(page.getByTestId("story")).toHaveAttribute("data-mode", "scrub");
    await expect(page.getByTestId("scene-canvas")).toBeVisible();
  });
});
