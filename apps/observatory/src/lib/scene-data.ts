import { DEFAULT_PARAMS, ORIGIN_DAY, simulate, type SimParams } from "./sim";

export type V3 = [number, number, number];

export interface SceneData {
  c: V3[];
  e: V3[];
  /** Future branches beyond the origin. */
  cContinue: V3[];
  cCessation: V3[];
  eContinue: V3[];
  /** Noisy assessments (history), and their residual segments from E. */
  y: V3[];
  yFuture: V3[];
  residual: V3[];
  /** Vertical connectors between C and E at weekly samples. */
  gap: V3[];
  boundaryX: number;
  axes: { x: V3[]; y: V3[]; z: V3[] };
  grid: V3[];
}

const X_SPAN = 5.2;
const Z_SCALE = 2.4;

/** Conceptual trajectories from the public law with fixed illustrative parameters. Not measured data. */
export function buildSceneData(step = 2): SceneData {
  const base: SimParams = { ...DEFAULT_PARAMS };
  const cont = simulate({ ...base, plan: "continue" });
  const cess = simulate({ ...base, plan: "cessation" });
  const values = [...cont.series.map((p) => p.C), ...cont.series.map((p) => p.E), ...cess.series.map((p) => p.C), ...cont.assessments.map((a) => a.y)];
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
  const cPts = (r: typeof cont, from: number, to: number): V3[] => sample(r.series, from, to).map((p) => [X(p.day), Y(p.C), 0]);
  const ePts = (r: typeof cont, from: number, to: number): V3[] => sample(r.series, from, to).map((p) => [X(p.day), Y(p.E), Z(p.S)]);
  const y: V3[] = [];
  const yFuture: V3[] = [];
  const residual: V3[] = [];
  for (const a of cont.assessments) {
    const s = cont.series[a.day]!;
    const pt: V3 = [X(a.day), Y(a.y), Z(s.S)];
    if (a.future) yFuture.push(pt);
    else {
      y.push(pt);
      residual.push([X(a.day), Y(s.E), Z(s.S)], pt);
    }
  }
  const gap: V3[] = [];
  for (let d = 6; d < ORIGIN_DAY; d += 7) {
    const s = cont.series[d]!;
    gap.push([X(d), Y(s.C), 0], [X(d), Y(s.E), Z(s.S)]);
  }
  const bx = X(ORIGIN_DAY - 0.5);
  const yb = -1.9;
  const grid: V3[] = [];
  for (let i = -5; i <= 5; i += 1) {
    grid.push([i, yb, -0.4], [i, yb, 2.4]);
  }
  for (let k = 0; k <= 4; k += 1) {
    const z = -0.4 + k * 0.7;
    grid.push([-X_SPAN, yb, z], [X_SPAN, yb, z]);
  }
  return {
    c: cPts(cont, 0, ORIGIN_DAY - 1),
    e: ePts(cont, 0, ORIGIN_DAY - 1),
    cContinue: cPts(cont, ORIGIN_DAY - 1, 279),
    cCessation: cPts(cess, ORIGIN_DAY - 1, 279),
    eContinue: ePts(cont, ORIGIN_DAY - 1, 279),
    y,
    yFuture,
    residual,
    gap,
    boundaryX: bx,
    axes: {
      x: [[-X_SPAN, yb, -0.4], [X_SPAN, yb, -0.4]],
      y: [[-X_SPAN, yb, -0.4], [-X_SPAN, 1.7, -0.4]],
      z: [[-X_SPAN, yb, -0.4], [-X_SPAN, yb, 2.4]],
    },
    grid,
  };
}
