import { expect, test } from "@playwright/test";
import { ROUTES, settle } from "./helpers";

test.describe("routes", () => {
  for (const route of ROUTES) {
    test(`smoke ${route}: 200, headers, landmarks, no horizontal overflow`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      const requests: string[] = [];
      page.on("request", (r) => requests.push(r.url()));
      const res = await page.goto(route);
      expect(res?.status()).toBe(200);
      expect(res?.headers()["content-security-policy"]).toContain("default-src 'self'");
      expect(res?.headers()["x-content-type-options"]).toBe("nosniff");
      await settle(page, 500);
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.getByRole("banner")).toBeVisible();
      await expect(page.getByRole("contentinfo")).toBeVisible();
      await expect(page.getByRole("link", { name: "Skip to main content" })).toBeAttached();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
      expect(requests.filter((u) => !u.startsWith("http://127.0.0.1"))).toEqual([]);
      expect(errors).toEqual([]);
    });
  }

  test("skip link and keyboard focus are visible", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "keyboard on desktop");
    await page.goto("/lab");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to main content" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main")).toBeFocused();
  });

  test("theme toggle switches and persists", async ({ page }) => {
    await page.goto("/about");
    const before = await page.locator("html").getAttribute("data-theme");
    await page.getByTestId("theme-toggle").click();
    const after = await page.locator("html").getAttribute("data-theme");
    expect(after).not.toBe(before);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", after!);
  });
});

test.describe("forecast selectors", () => {
  test("selectors change the plotted records, sources and units", async ({ page }) => {
    await page.goto("/forecast");
    const summary = page.getByTestId("selection-summary");
    await expect(summary).toContainText("5 model records");
    await expect(summary).toContainText("observable_strength_forecasting");
    await page.getByTestId("study-RES-639").click();
    await expect(summary).toContainText("3 model records");
    await expect(summary).toContainText("history_conditional_uncertainty");
    await page.getByLabel("Test parent", { exact: true }).selectOption("TEST_B");
    await page.getByLabel("Scenario", { exact: true }).selectOption("ADAPTATION_TIMESCALE_SHIFT");
    await expect(summary).toContainText("TEST_B");
    await expect(summary).toContainText("shift scenario");
    await page.getByTestId("study-RES-616").click();
    await page.getByLabel("Plan / horizon", { exact: true }).selectOption("cessation/56");
    await expect(summary).toContainText("3 model records");
    await expect(page.getByText("No interval for this slice")).toBeVisible();
    await expect(page.getByText(/lower-is-better/i).first()).toBeVisible();
  });
});

test.describe("publication honesty and rights", () => {
  test("publication page shows pending state and no PDF, DOI or private link", async ({ page }) => {
    await page.goto("/publication");
    await expect(page.getByTestId("publication-status")).toContainText("Manuscript in private preparation — public release pending.");
    const hrefs = await page.locator("a").evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).href));
    expect(hrefs.filter((h) => /\.pdf(\?|$)/i.test(h))).toEqual([]);
    expect(hrefs.filter((h) => /powerlifting-state-research-paper/.test(h))).toEqual([]);
    expect(await page.locator("a[download]").count()).toBe(0);
    expect(await page.getByText(/doi\.org|10\.\d{4,}\//).count()).toBe(0);
    await expect(page.getByTestId("citation")).toContainText("github.com/Litju/powerlifting-state-research");
  });

  test("no paper artifact is served", async ({ request }) => {
    for (const path of ["/paper.pdf", "/manuscript.pdf", "/paper", "/downloads/paper.pdf"]) {
      const res = await request.get(path);
      expect(res.status()).toBe(404);
    }
  });
});

test.describe("research journey", () => {
  test("stage navigation reveals findings, limits and sources", async ({ page }) => {
    await page.goto("/journey");
    await page.getByTestId("stage-G2").click();
    const panel = page.getByTestId("stage-panel");
    await expect(panel).toContainText("FULL_G2_IDENTIFICATION_UNSUPPORTED");
    await expect(panel).toContainText("not a proof of impossibility");
    await expect(panel.getByRole("link", { name: /g2-identifiability-decision/ })).toHaveAttribute("href", /github.com\/Litju\/powerlifting-state-research\/blob\/41191d6/);
    await page.getByTestId("stage-RES-639").click();
    await expect(panel).toContainText("+0.024194");
  });
});

test.describe("benchmarks", () => {
  test("filters change the table and chart", async ({ page }) => {
    await page.goto("/benchmarks");
    await expect(page.getByText("(9 rows)")).toBeVisible();
    await page.getByLabel("Identity authority").selectOption("PUBLIC_NATIVE");
    await expect(page.getByText("(1 row)")).toBeVisible();
    await page.getByLabel("Candidate class").selectOption("RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT");
    await expect(page.getByTestId("frontier-summary")).toContainText("4 fit or ensemble identities");
  });
});

test.describe("lab", () => {
  test("plan and sliders change the illustrative table", async ({ page }) => {
    await page.goto("/lab");
    const row = page.getByRole("table").last().locator("tbody tr").first();
    const before = await row.innerText();
    await page.getByTestId("plan-cessation").click();
    await expect(row).not.toHaveText(before);
    await page.getByLabel(/Adaptation time constant/).fill("120");
    await page.getByTestId("lab-reset").click();
    await expect(page.getByTestId("plan-continue")).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("mobile touch", () => {
  test("home scrolls by touch swipe and has no horizontal overflow", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "mobile project");
    await page.goto("/");
    await settle(page);
    const start = await page.evaluate(() => window.scrollY);
    await page.touchscreen.tap(200, 300);
    const cdp = await page.context().newCDPSession(page);
    // A vertical one-finger swipe starting on the 3D stage must scroll the page (the canvas only claims horizontal drags).
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: 200, y: 650 }] });
    for (let i = 1; i <= 12; i += 1) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: 200, y: 650 - i * 40 }] });
      await page.waitForTimeout(16);
    }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await page.waitForTimeout(600);
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(start + 200);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  });
});
