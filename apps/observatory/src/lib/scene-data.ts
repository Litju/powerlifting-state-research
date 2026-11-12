import { inverseIllustration } from "./inverse";
import { DEFAULT_PARAMS, ORIGIN_DAY, simulate, type SimParams, type SimPoint } from "./sim";

export type V3 = [number, number, number];

export interface Assessment {
  day: number;
  y: number;
  C: number;
  E: number;
  S: number;
}

export interface SceneData {
  c: V3[];
  e: V3[];
  /** Future branches beyond the origin. */
  cContinue: V3[];
  cCessation: V3[];
  eContinue: V3[];
  /** Noisy assessments (history), their residual segments from E, and an illustrative +/-1.96 CV band per point. */
  y: V3[];
  yInfo: Assessment[];
  yFuture: V3[];
  residual: V3[];
  band: V3[];
  /** Vertical connectors between C and E at weekly samples. */
  gap: V3[];
  /** Alternative parameter settings that fit the same observations (Act III illustration). */
  candidatesC: V3[][];
  candidatesE: V3[][];
  boundaryX: number;
  axes: { x: V3[]; y: V3[]; z: V3[] };
  grid: V3[];
  /** Anchor points for labels. */
  anchors: { C: V3; E: V3; Y: V3; S: V3; boundary: V3; time: V3; candidates: V3 };
}

export const X_SPAN = 5.2;
const Z_SCALE = 2.4;
export const FLOOR_Y = -1.9;

/** Conceptual trajectories from the public law with fixed illustrative parameters. Not measured data. */
export function buildSceneData(step = 2): SceneData {
  const base: SimParams = { ...DEFAULT_PARAMS };
  const cont = simulate({ ...base, plan: "continue" });
  const cess = simulate({ ...base, plan: "cessation" });
  const inv = inverseIllustration();
  const values = [...cont.series.map((p) => p.C), ...cont.series.map((p) => p.E), ...cess.series.map((p) => p.C), ...cont.assessments.map((a) => a.y), ...inv.shown.map((c) => c.cLast)];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const X = (day: number) => ((day / 279) * 2 - 1) * X_SPAN;
  const Y = (v: number) => ((v - lo) / (hi - lo) - 0.5) * 3.2;
  const Z = (s: number) => s * Z_SCALE;
  const sample = <T,>(arr: T[], from: number, to: number): T[] => {
    const out: T[] = [];
    for (let i = from; i <= to; i += step) out.push(arr[i]!);
    if ((to - from) % step !== 0) out.push(arr[to]!);
    return out;
  };
  const cPts = (series: SimPoint[], from: number, to: number): V3[] => sample(series, from, to).map((p) => [X(p.day), Y(p.C), 0]);
  const ePts = (series: SimPoint[], from: number, to: number): V3[] => sample(series, from, to).map((p) => [X(p.day), Y(p.E), Z(p.S)]);
  const y: V3[] = [];
  const yInfo: Assessment[] = [];
  const yFuture: V3[] = [];
  const residual: V3[] = [];
  const band: V3[] = [];
  const cv = base.assessmentCv;
  for (const a of cont.assessments) {
    const s = cont.series[a.day]!;
    const pt: V3 = [X(a.day), Y(a.y), Z(s.S)];
    if (a.future) yFuture.push(pt);
    else {
      y.push(pt);
      yInfo.push({ day: a.day, y: a.y, C: s.C, E: s.E, S: s.S });
      residual.push([X(a.day), Y(s.E), Z(s.S)], pt);
      band.push([X(a.day), Y(a.y * (1 - 1.96 * cv)), Z(s.S)], [X(a.day), Y(a.y * (1 + 1.96 * cv)), Z(s.S)]);
    }
  }
  const gap: V3[] = [];
  for (let d = 6; d < ORIGIN_DAY; d += 7) {
    const s = cont.series[d]!;
    gap.push([X(d), Y(s.C), 0], [X(d), Y(s.E), Z(s.S)]);
  }
  const bx = X(ORIGIN_DAY - 0.5);
  const grid: V3[] = [];
  for (let i = -5; i <= 5; i += 1) grid.push([i, FLOOR_Y, -0.4], [i, FLOOR_Y, 2.4]);
  for (let k = 0; k <= 4; k += 1) {
    const z = -0.4 + k * 0.7;
    grid.push([-X_SPAN, FLOOR_Y, z], [X_SPAN, FLOOR_Y, z]);
  }
  const candStep = Math.max(step, 4);
  const candidatesC = inv.shown.map((c) => sample(c.series, 0, ORIGIN_DAY - 1).filter((_, i) => i % Math.round(candStep / step) === 0).map((p) => [X(p.day), Y(p.C), 0] as V3));
  const candidatesE = inv.shown.map((c) => sample(c.series, 0, ORIGIN_DAY - 1).filter((_, i) => i % Math.round(candStep / step) === 0).map((p) => [X(p.day), Y(p.E), Z(p.S)] as V3));
  const last = cont.series[ORIGIN_DAY - 1]!;
  const mid = cont.series[150]!;
  return {
    c: cPts(cont.series, 0, ORIGIN_DAY - 1),
    e: ePts(cont.series, 0, ORIGIN_DAY - 1),
    cContinue: cPts(cont.series, ORIGIN_DAY - 1, 279),
    cCessation: cPts(cess.series, ORIGIN_DAY - 1, 279),
    eContinue: ePts(cont.series, ORIGIN_DAY - 1, 279),
    y,
    yInfo,
    yFuture,
    residual,
    band,
    gap,
    candidatesC,
    candidatesE,
    boundaryX: bx,
    axes: {
      x: [[-X_SPAN, FLOOR_Y, -0.4], [X_SPAN, FLOOR_Y, -0.4]],
      y: [[-X_SPAN, FLOOR_Y, -0.4], [-X_SPAN, 1.7, -0.4]],
      z: [[-X_SPAN, FLOOR_Y, -0.4], [-X_SPAN, FLOOR_Y, 2.4]],
    },
    grid,
    anchors: {
      C: [X(150), Y(mid.C) + 0.28, 0],
      E: [X(150), Y(mid.E) - 0.3, Z(mid.S)],
      Y: [X(120), Y(cont.series[120]!.E) + 0.9, Z(cont.series[120]!.S)],
      S: [-X_SPAN, FLOOR_Y, 2.5],
      boundary: [bx, 1.95, 1],
      time: [X_SPAN - 0.4, FLOOR_Y, -0.55],
      candidates: [X(ORIGIN_DAY - 1) - 0.1, Y(inv.shown.at(-1)?.series[ORIGIN_DAY - 1]!.C ?? last.C) + 0.25, 0],
    },
  };
}
