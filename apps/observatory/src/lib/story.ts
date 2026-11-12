/** Story chapters, camera keyframes and layer emphasis. Pure functions so that the scroll choreography is testable. */

export type Layer = "C" | "E" | "Y" | "gap" | "boundary" | "future";
export const LAYERS: Layer[] = ["C", "E", "Y", "gap", "boundary", "future"];

export interface Chapter {
  id: string;
  kicker: string;
  title: string;
  body: string;
  /** Layers emphasised while this chapter is centred. */
  focus: Layer[];
  pose: Pose;
}

export interface Pose {
  /** azimuth, elevation (radians), radius, and the look-at target */
  az: number;
  el: number;
  r: number;
  tx: number;
  ty: number;
  tz: number;
}

export const CHAPTERS: Chapter[] = [
  {
    id: "question",
    kicker: "The question",
    title: "What can we know about a system we only see through noise?",
    body: "A synthetic athlete has a hidden capacity, a temporarily suppressed expression of it, and a noisy record. Powerlifting State Research asks what a model can honestly infer, forecast and quantify about such a system, and where the limits are. Everything here is simulated.",
    focus: ["C", "E", "Y", "boundary", "future", "gap"],
    pose: { az: 0.7, el: 0.34, r: 13.5, tx: 0, ty: 0, tz: 0.6 },
  },
  {
    id: "capacity",
    kicker: "Latent capacity C",
    title: "Capacity builds slowly and is never observed.",
    body: "C = B(1 + g_A A) rises as adaptation A accumulates with a long time constant. It is the quantity a coach would like to know, and no observation contains it directly.",
    focus: ["C"],
    pose: { az: 0.25, el: 0.14, r: 8.5, tx: -2.4, ty: 0.2, tz: 0 },
  },
  {
    id: "expression",
    kicker: "Expressed performance E",
    title: "Performance on the day is capacity, partly suppressed.",
    body: "E = C(1 - g_S S). Suppression S rises and falls quickly with recent stimulus, pulling expression below capacity along a separate axis. The gap between C and E is what makes the two different quantities.",
    focus: ["E", "gap", "C"],
    pose: { az: 0.95, el: 0.5, r: 9, tx: 0, ty: 0, tz: 1.1 },
  },
  {
    id: "observation",
    kicker: "Observed Y",
    title: "What we record is expression, plus noise.",
    body: "Y = E(1 + noise). Assessments, loads and velocities all pass through E, so even a perfect, noiseless inversion recovers E but not C. This is the first negative result of the program (G1).",
    focus: ["Y", "E"],
    pose: { az: -0.35, el: 0.3, r: 8, tx: 1.6, ty: 0, tz: 0.9 },
  },
  {
    id: "boundary",
    kicker: "Information boundary",
    title: "Histories end on day 223; forecasts begin at origin 224.",
    body: "Models see only what lies left of the plane. The future depends on a declared plan: continue, step up, step down or cease. After cessation C can only fall, yet E and a noisy Y may still rise, so the forecast target matters.",
    focus: ["boundary", "future", "Y"],
    pose: { az: -1.05, el: 0.26, r: 9.5, tx: 3.6, ty: 0, tz: 0.4 },
  },
  {
    id: "evidence",
    kicker: "Evidence",
    title: "Then we test, report and keep the negatives.",
    body: "Identification of the full model is unsupported on current evidence. A GRU is not better than Ridge on the observed assessment, and participant-visible histories do not sharpen the predictive scale. The rest of this site is those results, with sources.",
    focus: ["C", "E", "Y", "boundary", "future"],
    pose: { az: 0.5, el: 0.5, r: 14.5, tx: 0, ty: 0, tz: 0.6 },
  },
];

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const smooth = (x: number) => x * x * (3 - 2 * x);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export function chapterCenter(i: number, n = CHAPTERS.length): number {
  return n <= 1 ? 0 : i / (n - 1);
}

/** Interpolated camera pose for scroll progress p in [0,1]. */
export function cameraPose(p: number): Pose {
  const n = CHAPTERS.length;
  const x = clamp01(p) * (n - 1);
  const i = Math.min(n - 2, Math.floor(x));
  const t = smooth(x - i);
  const a = CHAPTERS[i]!.pose;
  const b = CHAPTERS[i + 1]!.pose;
  return {
    az: lerp(a.az, b.az, t),
    el: lerp(a.el, b.el, t),
    r: lerp(a.r, b.r, t),
    tx: lerp(a.tx, b.tx, t),
    ty: lerp(a.ty, b.ty, t),
    tz: lerp(a.tz, b.tz, t),
  };
}

/** Closeness of progress p to chapter i, 1 at its centre and 0 at the neighbouring chapter centres. */
export function chapterWeight(p: number, i: number): number {
  const n = CHAPTERS.length;
  const d = Math.abs(clamp01(p) * (n - 1) - i);
  return smooth(clamp01(1 - d));
}

export const DIM = 0.14;

/** Opacity of each scene layer at progress p: dim by default, full when a centred chapter focuses it. */
export function layerWeights(p: number): Record<Layer, number> {
  const out = Object.fromEntries(LAYERS.map((l) => [l, DIM])) as Record<Layer, number>;
  CHAPTERS.forEach((c, i) => {
    const w = chapterWeight(p, i);
    for (const layer of c.focus) out[layer] = Math.max(out[layer], lerp(DIM, 1, w));
  });
  return out;
}

export function activeChapter(p: number): number {
  const n = CHAPTERS.length;
  return Math.min(n - 1, Math.max(0, Math.round(clamp01(p) * (n - 1))));
}
