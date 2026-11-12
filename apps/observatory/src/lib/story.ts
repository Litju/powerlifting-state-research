/**
 * The landing narrative: six acts, each made of one to three "beats". A beat is one scroll step with one message and
 * one stage state (camera pose, layer emphasis, progressive drawing, or an evidence panel built from real aggregate
 * data). Everything here is pure so that the choreography is unit-testable and independent of rendering.
 */

export type Layer = "Y" | "band" | "C" | "E" | "gap" | "residual" | "candidates" | "boundary" | "future";
export const LAYERS: Layer[] = ["Y", "band", "C", "E", "gap", "residual", "candidates", "boundary", "future"];

/** Layers that are drawn progressively (left to right) during the beat that introduces them. */
export const DRAWN: Layer[] = ["C", "E", "candidates", "future"];

/** Evidence panels replace the conceptual scene with real, source-bound aggregate results. */
export type PanelId = "g2" | "ridge" | "uncertainty";

export interface Pose {
  /** azimuth, elevation (radians), radius, and the look-at target */
  az: number;
  el: number;
  r: number;
  tx: number;
  ty: number;
  tz: number;
}

export interface Beat {
  id: string;
  /** Opacity of each layer while this beat is centred (absent = hidden). */
  layers: Partial<Record<Layer, number>>;
  pose: Pose;
  /** Layers that are drawn progressively during this beat. */
  draws?: Layer[];
  panel?: PanelId;
  /** Within an evidence panel, the step revealed by this beat. */
  panelStep?: number;
}

export interface Act {
  id: string;
  numeral: string;
  kicker: string;
  /** Short label for the act index. */
  short: string;
  title: string;
  beats: Beat[];
}

const FULL: Partial<Record<Layer, number>> = { Y: 1, C: 1, E: 1, gap: 0.5, residual: 0.6, boundary: 1, future: 1 };

export const ACTS: Act[] = [
  {
    id: "observation",
    numeral: "I",
    kicker: "The observation",
    short: "Observation",
    title: "All we ever see is Y.",
    beats: [
      { id: "observe", layers: { Y: 1 }, pose: { az: 0, el: 0.06, r: 12.2, tx: 0, ty: -0.35, tz: 0.6 } },
      { id: "question", layers: { Y: 1, band: 0.85 }, pose: { az: -0.38, el: 0.2, r: 12.6, tx: 0, ty: -0.1, tz: 0.6 } },
    ],
  },
  {
    id: "system",
    numeral: "II",
    kicker: "The hidden system",
    short: "Hidden system",
    title: "Two hidden quantities sit behind every measurement.",
    beats: [
      { id: "capacity", layers: { Y: 0.25, C: 1 }, draws: ["C"], pose: { az: 0.18, el: 0.12, r: 11.4, tx: 0, ty: 0.2, tz: 0.4 } },
      { id: "suppression", layers: { Y: 0.2, C: 1, E: 1, gap: 0.8 }, draws: ["E"], pose: { az: -0.6, el: 0.42, r: 11.8, tx: 0, ty: 0, tz: 1.0 } },
      { id: "noise", layers: { Y: 1, C: 0.45, E: 1, gap: 0.25, residual: 1 }, pose: { az: -0.42, el: 0.22, r: 10.6, tx: -0.8, ty: 0, tz: 0.9 } },
    ],
  },
  {
    id: "identification",
    numeral: "III",
    kicker: "The identification problem",
    short: "Identification",
    title: "Can the hidden parameters be recovered?",
    beats: [
      { id: "inverse", layers: { Y: 1, C: 0.9, E: 0.5, candidates: 1 }, draws: ["candidates"], pose: { az: 0.1, el: 0.24, r: 12.4, tx: 0, ty: 0.1, tz: 0.6 } },
      { id: "g2", layers: { Y: 0.6, C: 0.6, candidates: 0.6 }, panel: "g2", pose: { az: -0.2, el: 0.3, r: 14, tx: 0, ty: 0, tz: 0.6 } },
    ],
  },
  {
    id: "forecasting",
    numeral: "IV",
    kicker: "Forecasting",
    short: "Forecasting",
    title: "So change the question: predict the next Y.",
    beats: [
      { id: "boundary", layers: { Y: 1, E: 0.5, C: 0.3, boundary: 1, future: 1 }, draws: ["future"], pose: { az: -0.72, el: 0.3, r: 11.6, tx: 2.6, ty: 0, tz: 0.8 } },
      { id: "ridge", layers: { Y: 0.6, boundary: 0.6, future: 0.6 }, panel: "ridge", pose: { az: -1.1, el: 0.3, r: 11, tx: 3.2, ty: 0, tz: 0.6 } },
    ],
  },
  {
    id: "uncertainty",
    numeral: "V",
    kicker: "Predictive uncertainty",
    short: "Uncertainty",
    title: "A forecast is a distribution, not a number.",
    beats: [
      { id: "scale", layers: { Y: 0.6, future: 0.6 }, panel: "uncertainty", panelStep: 0, pose: { az: -1.1, el: 0.3, r: 11, tx: 3.2, ty: 0, tz: 0.6 } },
      { id: "history", layers: { Y: 0.6, future: 0.6 }, panel: "uncertainty", panelStep: 1, pose: { az: -1.1, el: 0.3, r: 11, tx: 3.2, ty: 0, tz: 0.6 } },
    ],
  },
  {
    id: "synthesis",
    numeral: "VI",
    kicker: "What the evidence supports",
    short: "Evidence",
    title: "What the evidence supports, and what it does not.",
    beats: [{ id: "ledger", layers: FULL, pose: { az: -0.5, el: 0.34, r: 14.6, tx: 0, ty: 0, tz: 0.6 } }],
  },
];

export const BEATS: Beat[] = ACTS.flatMap((a) => a.beats);
export const BEAT_ACT: number[] = ACTS.flatMap((a, i) => a.beats.map(() => i));

export function actStart(actIndex: number): number {
  return BEAT_ACT.indexOf(actIndex);
}

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const smooth = (x: number) => {
  const c = clamp01(x);
  return c * c * (3 - 2 * c);
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Fraction of a beat over which the stage holds its state before blending into the next beat. */
export const HOLD = 0.6;

export interface SceneState {
  beat: number;
  act: number;
  pose: Pose;
  layers: Record<Layer, number>;
  /** 0..1 fraction drawn for progressively drawn layers. */
  draw: Record<Layer, number>;
  /** Opacity of each evidence panel. */
  panels: Record<PanelId, number>;
  /** Highest step revealed within the visible panel. */
  panelStep: number;
}

/**
 * Stage state for a continuous story position. Position p means: beat floor(p) is centred on screen and the fractional
 * part is how far the reader has scrolled through it. Each beat holds its state, then blends into the next.
 */
export function sceneState(position: number): SceneState {
  const n = BEATS.length;
  const p = Math.min(n - 1 + 0.9999, Math.max(0, Number.isFinite(position) ? position : 0));
  const i = Math.min(n - 1, Math.floor(p));
  const t = p - i;
  const cur = BEATS[i]!;
  const next = BEATS[Math.min(i + 1, n - 1)]!;
  const blend = i === n - 1 ? 0 : smooth((t - HOLD) / (1 - HOLD));
  const pose = {} as Pose;
  for (const k of ["az", "el", "r", "tx", "ty", "tz"] as const) pose[k] = lerp(cur.pose[k], next.pose[k], blend);
  const layers = {} as Record<Layer, number>;
  const draw = {} as Record<Layer, number>;
  for (const l of LAYERS) {
    layers[l] = lerp(cur.layers[l] ?? 0, next.layers[l] ?? 0, blend);
    const start = BEATS.findIndex((b) => b.draws?.includes(l));
    draw[l] = start < 0 || i > start ? 1 : i < start ? 0 : smooth(t / HOLD);
  }
  // Sequential cross-fade: an outgoing panel is gone before an incoming one appears, so two figures never overlap.
  const panels: Record<PanelId, number> = { g2: 0, ridge: 0, uncertainty: 0 };
  if (cur.panel) panels[cur.panel] = next.panel === cur.panel ? 1 : 1 - smooth(blend * 2);
  if (next.panel && next !== cur && next.panel !== cur.panel) panels[next.panel] = smooth(blend * 2 - 1);
  const panelStep = cur.panel && next.panel === cur.panel && blend > 0.5 ? (next.panelStep ?? 0) : (cur.panelStep ?? 0);
  return { beat: i, act: BEAT_ACT[i]!, pose, layers, draw, panels, panelStep };
}

/** Story position from the geometry of the beat blocks: the reading line is the vertical centre of the viewport. */
export function positionFromRects(rects: { top: number; height: number }[], readingLine: number): number {
  if (rects.length === 0) return 0;
  for (let i = 0; i < rects.length; i += 1) {
    const r = rects[i]!;
    if (readingLine < r.top + r.height || i === rects.length - 1) {
      if (readingLine < r.top) return i;
      return i + Math.min(0.9999, (readingLine - r.top) / Math.max(1, r.height));
    }
  }
  return rects.length - 1;
}
