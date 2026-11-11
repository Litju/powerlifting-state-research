/**
 * Illustrative, deterministic client-side demonstration of the public capacity/expression law
 * (docs/science/system-model.md). It is NOT research evidence, NOT athlete data, and is not fitted to anything.
 *
 *   s_t = d_t i_t / (d_t i_t + s_ref),  s_ref = 0.6 (1 - r_ref) / r_ref
 *   A_t = a_A A_{t-1} + (1 - a_A) s_t,   C_t = B (1 + g_A A_t)
 *   S_t = a_S S_{t-1} + (1 - a_S) s_t,   E_t = C_t (1 - g_S S_t)
 *   a_A = exp(-1/tau_A),  a_S = exp(-1/tau_S),  A_{-1} = S_{-1} = 0
 */
export type Plan = "continue" | "step_up" | "step_down" | "cessation";

export const PLAN_LABELS: Record<Plan, string> = {
  continue: "Continue",
  step_up: "Step-up (dose x1.5)",
  step_down: "Step-down (dose x0.5)",
  cessation: "Cessation (dose 0)",
};

const PLAN_DOSE_FACTOR: Record<Plan, number> = { continue: 1, step_up: 1.5, step_down: 0.5, cessation: 0 };

export interface SimParams {
  tauA: number;
  tauS: number;
  gainA: number;
  gainS: number;
  base: number;
  dose: number;
  intensity: number;
  rRef: number;
  plan: Plan;
  assessmentCv: number;
  seed: number;
}

export const ORIGIN_DAY = 224;
export const LAST_HISTORY_DAY = 223;
export const HORIZON_DAYS = 280;
export const FUTURE_ASSESSMENT_DAYS = [237, 251, 279] as const;

export const DEFAULT_PARAMS: SimParams = {
  tauA: 60,
  tauS: 8,
  gainA: 0.25,
  gainS: 0.18,
  base: 150,
  dose: 1,
  intensity: 0.7,
  rRef: 0.7,
  plan: "continue",
  assessmentCv: 0.05,
  seed: 20260101,
};

export interface SimPoint {
  day: number;
  stimulus: number;
  A: number;
  S: number;
  C: number;
  E: number;
}

export interface SimResult {
  series: SimPoint[];
  assessments: { day: number; y: number; future: boolean }[];
}

export function stimulus(dose: number, intensity: number, rRef: number): number {
  const sRef = (0.6 * (1 - rRef)) / rRef;
  const x = dose * intensity;
  return x <= 0 ? 0 : x / (x + sRef);
}

/** Small seeded PRNG (mulberry32), so every render of the demonstration is identical. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function gaussian(rng: () => number): number {
  const u = Math.max(rng(), 1e-12);
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export function assessmentDays(): number[] {
  const days: number[] = [];
  for (let d = 6; d <= LAST_HISTORY_DAY; d += 7) days.push(d);
  return days;
}

export function simulate(p: SimParams): SimResult {
  const aA = Math.exp(-1 / p.tauA);
  const aS = Math.exp(-1 / p.tauS);
  const factor = PLAN_DOSE_FACTOR[p.plan];
  let A = 0;
  let S = 0;
  const series: SimPoint[] = [];
  for (let t = 0; t < HORIZON_DAYS; t += 1) {
    const dose = t >= ORIGIN_DAY ? p.dose * factor : p.dose;
    const s = stimulus(dose, p.intensity, p.rRef);
    A = aA * A + (1 - aA) * s;
    S = aS * S + (1 - aS) * s;
    const C = p.base * (1 + p.gainA * A);
    const E = C * (1 - p.gainS * S);
    series.push({ day: t, stimulus: s, A, S, C, E });
  }
  const rng = mulberry32(p.seed);
  const days = [...assessmentDays(), ...FUTURE_ASSESSMENT_DAYS];
  const assessments = days.map((day) => {
    const e = (series[day] as SimPoint).E;
    return { day, y: e * (1 + p.assessmentCv * gaussian(rng)), future: day > LAST_HISTORY_DAY };
  });
  return { series, assessments };
}

/** Change in latent capacity from the last history day to a future assessment day: C_{t} - C_{223}. */
export function capacityChange(result: SimResult, day: number): number {
  const last = result.series[LAST_HISTORY_DAY - 1] as SimPoint;
  const at = result.series[day] as SimPoint;
  return at.C - last.C;
}
