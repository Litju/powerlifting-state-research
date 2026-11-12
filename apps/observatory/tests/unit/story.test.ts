import { describe, expect, it } from "vitest";
import { CHAPTERS, DIM, activeChapter, cameraPose, chapterCenter, layerWeights } from "@/lib/story";
import { buildSceneData } from "@/lib/scene-data";
import { ORIGIN_DAY } from "@/lib/sim";

describe("scroll choreography", () => {
  it("lands on each chapter pose at its scroll centre", () => {
    CHAPTERS.forEach((c, i) => {
      const pose = cameraPose(chapterCenter(i));
      expect(pose.az).toBeCloseTo(c.pose.az, 9);
      expect(pose.r).toBeCloseTo(c.pose.r, 9);
    });
  });

  it("is continuous and bounded across the whole scroll range", () => {
    let prev = cameraPose(0);
    for (let k = 1; k <= 1000; k += 1) {
      const next = cameraPose(k / 1000);
      expect(Math.abs(next.az - prev.az)).toBeLessThan(0.05);
      expect(Math.abs(next.r - prev.r)).toBeLessThan(0.1);
      prev = next;
    }
    expect(cameraPose(-1)).toEqual(cameraPose(0));
    expect(cameraPose(2)).toEqual(cameraPose(1));
  });

  it("emphasises only the focused layers in a single-focus chapter", () => {
    const w = layerWeights(chapterCenter(1));
    expect(w.C).toBe(1);
    expect(w.Y).toBeCloseTo(DIM, 9);
    expect(w.boundary).toBeCloseTo(DIM, 9);
    const b = layerWeights(chapterCenter(4));
    expect(b.boundary).toBe(1);
    expect(b.future).toBe(1);
    expect(b.gap).toBeCloseTo(DIM, 9);
  });

  it("maps progress to the active chapter", () => {
    expect(activeChapter(0)).toBe(0);
    expect(activeChapter(1)).toBe(CHAPTERS.length - 1);
    expect(activeChapter(chapterCenter(3))).toBe(3);
  });

  it("distinguishes C, E and Y in the conceptual scene and places the boundary at the origin", () => {
    const d = buildSceneData();
    expect(d.c.every((p) => p[2] === 0)).toBe(true);
    expect(d.e.some((p) => p[2] > 0.1)).toBe(true);
    expect(d.y).toHaveLength(32);
    expect(d.yFuture).toHaveLength(3);
    const maxHistoryX = Math.max(...d.y.map((p) => p[0]));
    expect(maxHistoryX).toBeLessThan(d.boundaryX);
    expect(Math.min(...d.yFuture.map((p) => p[0]))).toBeGreaterThan(d.boundaryX);
    expect(ORIGIN_DAY).toBe(224);
    const cessEnd = d.cCessation.at(-1)![1];
    const contEnd = d.cContinue.at(-1)![1];
    expect(cessEnd).toBeLessThan(contEnd);
  });
});
