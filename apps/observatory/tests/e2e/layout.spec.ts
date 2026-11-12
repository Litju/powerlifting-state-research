import { expect, test, type Page } from "@playwright/test";
import { ROUTES, settle, toBeat } from "./helpers";

/**
 * Structural layout regression tests, measured on the rendered page (bounding boxes), not inferred from source.
 * The safe zones are declared with data-zone attributes; see src/components/story/story.module.css.
 */

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
  { name: "narrow", width: 360, height: 800 },
] as const;

const BEATS = ["observe", "question", "capacity", "suppression", "noise", "inverse", "g2", "boundary", "ridge", "scale", "history", "ledger"];

/** Content scrolling underneath the sticky global header is ordinary scrolling, not a collision. */
const ALLOWED = new Set(["header|text", "header|inline-visual"]);

async function collisions(page: Page): Promise<string[]> {
  return page.evaluate((allowed) => {
    const boxes: { zone: string; r: DOMRect }[] = [];
    document.querySelectorAll<HTMLElement>("[data-zone]").forEach((el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (cs.display === "none" || cs.visibility === "hidden" || r.width < 2 || r.height < 2) return;
      if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) return;
      boxes.push({ zone: el.dataset.zone!, r });
    });
    const out: string[] = [];
    for (let i = 0; i < boxes.length; i += 1)
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i]!;
        const b = boxes[j]!;
        if (a.zone === b.zone) continue;
        const key = [a.zone, b.zone].sort().join("|");
        if (allowed.includes(key)) continue;
        const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
        const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
        if (w > 1 && h > 1) out.push(`${a.zone} × ${b.zone}: ${Math.round(w)}×${Math.round(h)} px`);
      }
    return out;
  }, [...ALLOWED]);
}

/** Elements that extend past the right edge without a scrolling or clipping ancestor (body clipping hides, not fixes). */
async function unclippedOverflow(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const clipped = (el: Element) => {
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) if (getComputedStyle(a).overflowX !== "visible") return true;
      return false;
    };
    return [...document.querySelectorAll("body *")]
      .filter((e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.right > innerWidth + 1 && !clipped(e);
      })
      .slice(0, 5)
      .map((e) => `${e.tagName.toLowerCase()} "${(e.textContent ?? "").trim().slice(0, 40)}"`);
  });
}

test.describe("safe zones never collide", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== "desktop", "viewport matrix runs once, in the WebGL project");
  });

  for (const vp of VIEWPORTS) {
    test(`story at ${vp.width}×${vp.height}: every beat is collision-free and the stage sits below the header`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/");
      await settle(page, 600);
      await page.mouse.wheel(0, 1);
      const headerH = await page.evaluate(() => document.querySelector("[data-zone=header]")!.getBoundingClientRect().height);
      expect(headerH).toBe(56);
      for (const beat of BEATS) {
        for (const f of [0.15, 0.6]) {
          await toBeat(page, beat, f);
          expect(await collisions(page), `${beat}@${f}`).toEqual([]);
        }
        const stageTop = await page.evaluate(() => {
          const z = [...document.querySelectorAll<HTMLElement>("[data-zone^=stage]")].filter((e) => e.getBoundingClientRect().height > 0);
          return z.length ? Math.min(...z.map((e) => e.getBoundingClientRect().top)) : null;
        });
        if (stageTop !== null) expect(stageTop).toBeGreaterThanOrEqual(headerH);
      }
      expect(await unclippedOverflow(page)).toEqual([]);
    });
  }

  test("stage controls and act links are not obstructed by anything", async ({ page }) => {
    await page.goto("/");
    await page.mouse.wheel(0, 1);
    await page.getByTestId("scene-canvas").waitFor({ timeout: 20_000 });
    for (const beat of ["observe", "inverse", "boundary", "ledger"]) {
      await toBeat(page, beat);
      const blocked = await page.evaluate(() =>
        [...document.querySelectorAll<HTMLElement>("[data-zone=stage-controls] button, [data-zone=stage-bar] a")]
          .filter((el) => {
            const r = el.getBoundingClientRect();
            const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return !(hit && (hit === el || el.contains(hit)));
          })
          .map((el) => el.textContent),
      );
      expect(blocked, beat).toEqual([]);
    }
  });

  test("evidence panels stay inside the stage field at laptop height", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    for (const [beat, id] of [
      ["g2", "g2"],
      ["ridge", "ridge"],
      ["history", "uncertainty"],
    ] as const) {
      await toBeat(page, beat);
      const inside = await page.evaluate((id) => {
        const field = document.querySelector("[data-zone=stage-field]")!.getBoundingClientRect();
        const panel = document.querySelector(`[data-testid=panel-${id}]`)!.getBoundingClientRect();
        return panel.top >= field.top - 1 && panel.bottom <= field.bottom + 1 && panel.left >= field.left - 1 && panel.right <= field.right + 1;
      }, id);
      expect(inside, beat).toBe(true);
    }
  });

  test("enlarged text (150%) on a phone keeps the story readable without overflow or collisions", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.addStyleTag({ content: "html { font-size: 150% !important; }" });
    await settle(page, 300);
    for (const beat of ["observe", "question", "ridge", "history", "ledger"]) {
      await toBeat(page, beat);
      expect(await collisions(page), beat).toEqual([]);
    }
    expect(await unclippedOverflow(page)).toEqual([]);
  });
});

test.describe("no hidden horizontal overflow on any route", () => {
  for (const width of [360, 390, 768]) {
    test(`routes at ${width} px`, async ({ page }, info) => {
      test.skip(info.project.name !== "desktop", "runs once");
      await page.setViewportSize({ width, height: 800 });
      for (const route of ROUTES) {
        await page.goto(route);
        await settle(page, 200);
        expect(await unclippedOverflow(page), route).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), route).toBeLessThanOrEqual(1);
      }
    });
  }
});

test.describe("global navigation", () => {
  test("compact menu opens, is keyboard operable, closes on Escape and returns focus", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout");
    await page.goto("/forecast");
    const button = page.getByTestId("menu-button");
    const links = page.locator("#primary-links");
    await expect(links).toBeHidden();
    await button.click();
    await expect(button).toHaveAttribute("aria-expanded", "true");
    await expect(links.getByRole("link", { name: "Benchmarks" })).toBeVisible();
    const box = (await links.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
    await page.keyboard.press("Escape");
    await expect(links).toBeHidden();
    await expect(button).toBeFocused();
    await button.click();
    await links.getByRole("link", { name: "Research journey" }).click();
    await expect(page).toHaveURL(/\/journey$/);
    await expect(page.locator("#primary-links")).toBeHidden();
  });

  test("the header never wraps: one row of 56 px at every width", async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "runs once");
    for (const width of [1440, 1280, 1024, 960, 768, 390, 360]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/benchmarks");
      const h = await page.evaluate(() => document.querySelector("[data-zone=header]")!.getBoundingClientRect().height);
      expect(h, String(width)).toBe(56);
    }
  });
});

test.describe("touch never traps scrolling", () => {
  test("a vertical swipe that starts on the 3D stage of a touch laptop scrolls the page", async ({ browser }, info) => {
    test.skip(info.project.name !== "desktop", "needs WebGL");
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto("/");
    await page.mouse.wheel(0, 1);
    await page.getByTestId("scene-canvas").waitFor({ timeout: 20_000 });
    const box = (await page.getByTestId("scene-wrap").boundingBox())!;
    const start = await page.evaluate(() => window.scrollY);
    const cdp = await ctx.newCDPSession(page);
    const x = box.x + box.width / 2;
    const y0 = box.y + box.height * 0.8;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: y0 }] });
    for (let i = 1; i <= 12; i += 1) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y0 - i * 30 }] });
      await page.waitForTimeout(16);
    }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await page.waitForTimeout(600);
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(start + 150);
    await ctx.close();
  });
});
