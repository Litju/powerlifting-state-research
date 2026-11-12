import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { evidence } from "@/lib/evidence";
import { inverseIllustration } from "@/lib/inverse";
import { buildSceneData } from "@/lib/scene-data";
import { ORIGIN_DAY } from "@/lib/sim";
import { ACTS, BEATS, HOLD, positionFromRects, sceneState } from "@/lib/story";
import { HISTORY_FEATURES, buildStoryEvidence } from "@/lib/story-evidence";

const REPO_ROOT = resolve(__dirname, "../../../..");

describe("six-act choreography", () => {
  it("has six acts in the required order, each with at least one beat", () => {
    expect(ACTS.map((a) => a.id)).toEqual(["observation", "system", "identification", "forecasting", "uncertainty", "synthesis"]);
    for (const a of ACTS) expect(a.beats.length).toBeGreaterThan(0);
    expect(new Set(BEATS.map((b) => b.id)).size).toBe(BEATS.length);
  });

  it("gives every act a visually distinct stage: no two consecutive acts share a pose and layer set", () => {
    const sig = (i: number) => JSON.stringify([BEATS[i]!.pose, BEATS[i]!.layers, BEATS[i]!.panel ?? null]);
    for (let a = 1; a < ACTS.length; a += 1) {
      const first = BEATS.indexOf(ACTS[a]!.beats[0]!);
      expect(sig(first)).not.toBe(sig(first - 1));
    }
  });

  it("holds each beat's pose and layers while it is being read", () => {
    BEATS.forEach((b, i) => {
      for (const t of [0.05, 0.3, HOLD - 0.01]) {
        const st = sceneState(i + t);
        expect(st.beat).toBe(i);
        expect(st.pose.az).toBeCloseTo(b.pose.az, 9);
        expect(st.layers.Y).toBeCloseTo(b.layers.Y ?? 0, 9);
      }
    });
  });

  it("is continuous across beat boundaries and clamps out-of-range input", () => {
    let prev = sceneState(0);
    for (let k = 1; k <= 4000; k += 1) {
      const next = sceneState((k / 4000) * BEATS.length);
      expect(Math.abs(next.pose.az - prev.pose.az)).toBeLessThan(0.08);
      expect(Math.abs(next.pose.r - prev.pose.r)).toBeLessThan(0.12);
      expect(Math.abs(next.layers.C - prev.layers.C)).toBeLessThan(0.08);
      prev = next;
    }
    expect(sceneState(-5)).toEqual(sceneState(0));
    expect(sceneState(Number.NaN)).toEqual(sceneState(0));
    expect(sceneState(1e9).beat).toBe(BEATS.length - 1);
  });

  it("starts with observations only, then reveals C before E, and draws them progressively", () => {
    const first = sceneState(0.2);
    expect(first.layers.Y).toBe(1);
    expect(first.layers.C).toBe(0);
    expect(first.layers.E).toBe(0);
    const cap = BEATS.findIndex((b) => b.id === "capacity");
    expect(sceneState(cap + 0.01).draw.C).toBeLessThan(0.05);
    expect(sceneState(cap + HOLD).draw.C).toBeCloseTo(1, 6);
    expect(sceneState(cap + 0.3).layers.E).toBe(0);
    const sup = BEATS.findIndex((b) => b.id === "suppression");
    expect(sceneState(sup + 0.3).layers.E).toBe(1);
  });

  it("switches from the conceptual scene to evidence panels for G2, RES-616 and RES-639", () => {
    const at = (id: string) => sceneState(BEATS.findIndex((b) => b.id === id) + 0.3);
    expect(at("g2").panels.g2).toBe(1);
    expect(at("ridge").panels.ridge).toBe(1);
    expect(at("scale").panels.uncertainty).toBe(1);
    expect(at("scale").panelStep).toBe(0);
    expect(at("history").panelStep).toBe(1);
    expect(at("boundary").panels).toEqual({ g2: 0, ridge: 0, uncertainty: 0 });
    expect(at("ledger").panels).toEqual({ g2: 0, ridge: 0, uncertainty: 0 });
  });

  it("maps the reading line onto beat geometry", () => {
    const rects = [
      { top: -200, height: 800 },
      { top: 600, height: 800 },
      { top: 1400, height: 800 },
    ];
    expect(positionFromRects(rects, 400)).toBeCloseTo(0.75, 9);
    expect(positionFromRects(rects, 1000)).toBeCloseTo(1.5, 9);
    expect(positionFromRects(rects, -500)).toBe(0);
    expect(positionFromRects(rects, 99999)).toBeLessThan(3);
  });
});

describe("conceptual scene and the illustrative inverse problem", () => {
  it("distinguishes C, E and Y and places the boundary at the origin", () => {
    const d = buildSceneData();
    expect(d.c.every((p) => p[2] === 0)).toBe(true);
    expect(d.e.some((p) => p[2] > 0.1)).toBe(true);
    expect(d.y).toHaveLength(32);
    expect(d.yInfo).toHaveLength(32);
    expect(d.band).toHaveLength(64);
    expect(d.yFuture).toHaveLength(3);
    expect(Math.max(...d.y.map((p) => p[0]))).toBeLessThan(d.boundaryX);
    expect(Math.min(...d.yFuture.map((p) => p[0]))).toBeGreaterThan(d.boundaryX);
    expect(ORIGIN_DAY).toBe(224);
    expect(d.cCessation.at(-1)![1]).toBeLessThan(d.cContinue.at(-1)![1]);
  });

  it("finds alternative parameter settings that fit as well as the truth but disagree about capacity", () => {
    const inv = inverseIllustration();
    expect(inv.gridSize).toBe(1440);
    expect(inv.accepted).toBeGreaterThan(10);
    expect(inv.shown.length).toBeGreaterThan(3);
    for (const c of inv.shown) expect(c.rmse).toBeLessThanOrEqual(inv.truth.rmse * inv.tolerance + 1e-9);
    expect(inv.cRange[1] - inv.cRange[0]).toBeGreaterThan(20);
    expect(inv.cRange[0]).toBeLessThan(inv.truth.cLast);
    expect(inv.cRange[1]).toBeGreaterThan(inv.truth.cLast);
  });
});

describe("story evidence binding", () => {
  const s = buildStoryEvidence(evidence);

  it("reads G1 and G2 from the public facts, including the unsupported-identification disposition", () => {
    expect(s.g1.kg).toBe("8.355256");
    expect(s.g2.disposition).toBe("FULL_G2_IDENTIFICATION_UNSUPPORTED");
    expect(s.g2.convergedNative).toEqual([7, 256]);
    expect(s.g2.convergedDoubled).toEqual([22, 256]);
    expect(s.g2.stationary).toEqual([17, 192]);
    expect(s.g2.localRank).toEqual([16, 16]);
    expect(s.g2.limits).toMatch(/not a proof of impossibility/);
  });

  it("uses the RES-616 primary GRU minus Ridge contrast with intervals above zero on both parents", () => {
    for (const p of ["TEST_A", "TEST_B"] as const) {
      const d = s.ridge.parents[p].diff;
      expect(d.lo).toBeGreaterThan(0);
      expect(d.diff).toBeGreaterThan(d.lo);
      expect(d.hi).toBeGreaterThan(d.diff);
      const [m0, m1, m2] = s.ridge.parents[p].scores;
      expect([m0!.model, m1!.model, m2!.model]).toEqual(["M0_C", "M1_C", "M2_C"]);
      expect(m2!.crps - m1!.crps).toBeCloseTo(d.diff, 6);
    }
    expect(s.ridge.parents.TEST_A.diff.diff).toBeCloseTo(0.110257535, 9);
  });

  it("uses the RES-639 B_GROUP → B_MAG → H_HISTORY scores and the primary H_HISTORY minus B_MAG contrast", () => {
    for (const p of ["TEST_A", "TEST_B"] as const) {
      const v = s.scale.parents[p];
      expect(v.scores.map((x) => x.model)).toEqual(["B_GROUP", "B_MAG", "H_HISTORY"]);
      expect(v.historyVsMag.lo).toBeGreaterThan(0);
      expect(v.magVsGroup.hi).toBeLessThan(0);
    }
    expect(s.scale.parents.TEST_A.historyVsMag.diff).toBeCloseTo(0.024194122, 9);
    expect(s.scale.parents.TEST_B.historyVsMag.diff).toBeCloseTo(0.018465299, 9);
    expect(s.scale.historyFeatures).toBe(127);
  });

  it("cites the 127 history summaries exactly as the public study report states them", () => {
    const doc = readFileSync(resolve(REPO_ROOT, HISTORY_FEATURES.path), "utf8");
    expect(doc).toContain(HISTORY_FEATURES.phrase);
  });

  it("serialises to a small payload (the full evidence file never reaches the story bundle)", () => {
    expect(JSON.stringify(s).length).toBeLessThan(6000);
  });
});

describe("client source links", () => {
  it("inline the pinned public revision without importing the evidence file", async () => {
    const src = await import("@/lib/source");
    expect(src.REVISION).toBe(evidence.source_revision);
    expect(src.sourceUrl("README.md")).toBe(`https://github.com/${evidence.source_repository}/blob/${evidence.source_revision}/README.md`);
    const text = readFileSync(resolve(__dirname, "../../src/lib/source.ts"), "utf8");
    expect(text).not.toMatch(/evidence\.v1\.json"/);
  });
});
