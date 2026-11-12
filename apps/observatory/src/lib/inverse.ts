/**
 * Illustrative inverse problem for the landing story (Act III). A coarse grid search over parameters of the public
 * capacity/expression law, scored against the same 32 illustrative noisy assessments that the story shows. It is a
 * demonstration inside the toy simulation, NOT the G2 study and NOT evidence about identifiability of the research
 * model. The G2 evidence is shown separately from the tracked aggregate report.
 */
import { DEFAULT_PARAMS, LAST_HISTORY_DAY, simulate, type SimParams, type SimPoint } from "./sim";

export interface CandidateFit {
  params: Pick<SimParams, "base" | "gainS" | "tauA" | "gainA">;
  rmse: number;
  /** latent capacity on the last history day, kg */
  cLast: number;
  series: SimPoint[];
}

export interface InverseIllustration {
  gridSize: number;
  /** fits within the tolerance of the generating model's own error */
  accepted: number;
  tolerance: number;
  truth: { rmse: number; cLast: number };
  /** a spread-out subset of accepted fits, sorted by cLast */
  shown: CandidateFit[];
  cRange: [number, number];
}

const GRID = {
  base: Array.from({ length: 10 }, (_, i) => 130 + i * 5),
  gainS: Array.from({ length: 16 }, (_, i) => Math.round((0.05 + i * 0.02) * 100) / 100),
  tauA: [45, 60, 75],
  gainA: [0.2, 0.25, 0.3],
};

let cache: InverseIllustration | null = null;

export function inverseIllustration(maxShown = 9): InverseIllustration {
  if (cache && cache.shown.length <= maxShown) return cache;
  const truthRun = simulate(DEFAULT_PARAMS);
  const obs = truthRun.assessments.filter((a) => !a.future);
  const rmseOf = (series: SimPoint[]) => Math.sqrt(obs.reduce((acc, a) => acc + (series[a.day]!.E - a.y) ** 2, 0) / obs.length);
  const truth = { rmse: rmseOf(truthRun.series), cLast: truthRun.series[LAST_HISTORY_DAY]!.C };
  const tolerance = 1.05;
  const accepted: CandidateFit[] = [];
  let gridSize = 0;
  for (const base of GRID.base)
    for (const gainS of GRID.gainS)
      for (const tauA of GRID.tauA)
        for (const gainA of GRID.gainA) {
          gridSize += 1;
          const { series } = simulate({ ...DEFAULT_PARAMS, base, gainS, tauA, gainA });
          const rmse = rmseOf(series);
          if (rmse <= truth.rmse * tolerance) accepted.push({ params: { base, gainS, tauA, gainA }, rmse, cLast: series[LAST_HISTORY_DAY]!.C, series });
        }
  accepted.sort((a, b) => a.cLast - b.cLast);
  const shown: CandidateFit[] = [];
  const k = Math.min(maxShown, accepted.length);
  for (let j = 0; j < k; j += 1) shown.push(accepted[Math.round((j * (accepted.length - 1)) / Math.max(1, k - 1))]!);
  const cRange: [number, number] = accepted.length ? [accepted[0]!.cLast, accepted.at(-1)!.cLast] : [truth.cLast, truth.cLast];
  cache = { gridSize, accepted: accepted.length, tolerance, truth, shown, cRange };
  return cache;
}
