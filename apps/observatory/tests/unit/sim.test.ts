import { describe, expect, it } from "vitest";
import {
  DEFAULT_PARAMS,
  FUTURE_ASSESSMENT_DAYS,
  HORIZON_DAYS,
  ORIGIN_DAY,
  assessmentDays,
  capacityChange,
  simulate,
  stimulus,
} from "@/lib/sim";

describe("illustrative simulation of the public law", () => {
  it("implements the bounded stimulus s = di/(di + s_ref)", () => {
    const rRef = 0.7;
    const sRef = (0.6 * (1 - rRef)) / rRef;
    expect(stimulus(1, 0.7, rRef)).toBeCloseTo(0.7 / (0.7 + sRef), 12);
    expect(stimulus(0, 0.7, rRef)).toBe(0);
    expect(stimulus(1e9, 1, rRef)).toBeLessThan(1);
  });

  it("matches a hand-computed first step from A=S=0", () => {
    const p = { ...DEFAULT_PARAMS };
    const out = simulate(p).series[0]!;
    const s = stimulus(p.dose, p.intensity, p.rRef);
    const aA = Math.exp(-1 / p.tauA);
    const aS = Math.exp(-1 / p.tauS);
    const A = (1 - aA) * s;
    const S = (1 - aS) * s;
    expect(out.A).toBeCloseTo(A, 12);
    expect(out.C).toBeCloseTo(p.base * (1 + p.gainA * A), 10);
    expect(out.E).toBeCloseTo(p.base * (1 + p.gainA * A) * (1 - p.gainS * S), 10);
  });

  it("keeps expressed performance at or below latent capacity", () => {
    for (const point of simulate(DEFAULT_PARAMS).series) expect(point.E).toBeLessThanOrEqual(point.C);
  });

  it("is deterministic for a fixed seed and changes with the seed", () => {
    const a = simulate(DEFAULT_PARAMS);
    const b = simulate({ ...DEFAULT_PARAMS });
    expect(a).toEqual(b);
    const c = simulate({ ...DEFAULT_PARAMS, seed: 7 });
    expect(c.assessments[0]!.y).not.toBe(a.assessments[0]!.y);
  });

  it("uses weekly history assessments (days 6, 13, ..., 223) and the three future assessment days", () => {
    const days = assessmentDays();
    expect(days[0]).toBe(6);
    expect(days.at(-1)).toBe(223);
    const out = simulate(DEFAULT_PARAMS);
    expect(out.assessments.filter((a) => a.future).map((a) => a.day)).toEqual([...FUTURE_ASSESSMENT_DAYS]);
    expect(out.series).toHaveLength(HORIZON_DAYS);
  });

  it("under cessation the latent capacity change is nonpositive after the origin", () => {
    const out = simulate({ ...DEFAULT_PARAMS, plan: "cessation" });
    for (const day of FUTURE_ASSESSMENT_DAYS) expect(capacityChange(out, day)).toBeLessThanOrEqual(0);
    expect(out.series[ORIGIN_DAY + 10]!.C).toBeLessThan(out.series[ORIGIN_DAY - 1]!.C);
  });

  it("step-up raises and step-down lowers later latent capacity relative to continue", () => {
    const cont = simulate({ ...DEFAULT_PARAMS, plan: "continue" });
    const up = simulate({ ...DEFAULT_PARAMS, plan: "step_up" });
    const down = simulate({ ...DEFAULT_PARAMS, plan: "step_down" });
    expect(up.series[279]!.C).toBeGreaterThan(cont.series[279]!.C);
    expect(down.series[279]!.C).toBeLessThan(cont.series[279]!.C);
  });
});
