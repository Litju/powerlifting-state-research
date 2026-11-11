export function fmt(value: number, digits = 4): string {
  return value.toFixed(digits);
}

/** Signed difference with an explicit plus sign. */
export function signed(value: number, digits = 4): string {
  const text = Math.abs(value).toFixed(digits);
  return value < 0 ? `−${text}` : `+${text}`;
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export const MODEL_LABELS: Record<string, string> = {
  M0_C: "M0 persistence (latest assessment)",
  M1_C: "M1 Ridge",
  M2_C: "M2 GRU",
  M1_G: "M1 Ridge + group adjustment",
  M2_G: "M2 GRU + group adjustment",
  B_GROUP: "B_GROUP (group RMS scale)",
  B_MAG: "B_MAG (forecast-magnitude scale)",
  H_HISTORY: "H_HISTORY (+ visible histories)",
};

export const SCENARIO_LABELS: Record<string, string> = {
  CONTROL: "Control (same-law IID)",
  VELOCITY_NOISE_SHIFT: "Shift: extra velocity noise",
  ADAPTATION_TIMESCALE_SHIFT: "Shift: adaptation time-constant density",
};

export const LIFT_LABELS: Record<string, string> = {
  squat: "Squat",
  bench_press: "Bench press",
  deadlift: "Deadlift",
  macro: "Macro (mean of three lifts)",
};

export function modelLabel(id: string): string {
  return MODEL_LABELS[id] ?? id;
}
