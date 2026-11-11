import type {
  ContrastRecord,
  Evidence,
  GroupCellRecord,
  ScoreRecord,
  ShiftRecord,
} from "./evidence";

export type StudyKey = "RES-616" | "RES-639";
export type Parent = "TEST_A" | "TEST_B";
export type Scenario = "CONTROL" | "VELOCITY_NOISE_SHIFT" | "ADAPTATION_TIMESCALE_SHIFT";
export type LiftKey = "macro" | "squat" | "bench_press" | "deadlift";

export interface ForecastSelection {
  study: StudyKey;
  parent: Parent;
  scenario: Scenario;
  lift: LiftKey;
  /** "all" = pooled over plan x horizon; otherwise "plan/horizon", available for RES-616 only. */
  group: string;
}

export const STUDY_MODELS: Record<StudyKey, string[]> = {
  "RES-616": ["M0_C", "M1_C", "M2_C", "M1_G", "M2_G"],
  "RES-639": ["B_GROUP", "B_MAG", "H_HISTORY"],
};

export const STUDY_PRIMARY_CONTRAST: Record<StudyKey, string> = {
  "RES-616": "M2_C-M1_C",
  "RES-639": "H_HISTORY-B_MAG",
};

export interface ModelRow {
  model: string;
  n: number;
  crps: number;
  nll: number;
  cov50: number | null;
  cov80: number;
  cov90: number;
  width50: number | null;
  width80: number;
  width90: number;
  source_path: string;
  source_sha256: string;
  study_id: string;
  target: "Y";
}

/** Whether group-level (plan x horizon) tables exist for the selection. */
export function groupsAvailable(study: StudyKey): boolean {
  return study === "RES-616";
}

export function groupOptions(evidence: Evidence): string[] {
  const set = new Set(evidence.group_cells.map((c) => `${c.plan}/${c.horizon_days}`));
  const order = ["continue", "step_up", "step_down", "cessation"];
  return [...set].sort((a, b) => {
    const [pa, ha] = a.split("/") as [string, string];
    const [pb, hb] = b.split("/") as [string, string];
    return order.indexOf(pa) - order.indexOf(pb) || Number(ha) - Number(hb);
  });
}

export function studyIdPrefix(study: StudyKey): string {
  return study === "RES-616" ? "psr:study:observable-strength-assessment-forecasting@" : "psr:study:history-conditioned-assessment-uncertainty@";
}

/** Rows for the model comparison under the selection. Honest: group cells carry only CRPS, NLL, cov90 and width90. */
export function selectModelRows(evidence: Evidence, sel: ForecastSelection): ModelRow[] {
  const prefix = studyIdPrefix(sel.study);
  const models = STUDY_MODELS[sel.study];
  if (sel.group !== "all" && groupsAvailable(sel.study)) {
    const [plan, horizon] = sel.group.split("/") as [string, string];
    const out: ModelRow[] = [];
    for (const model of models) {
      const cells = evidence.group_cells.filter(
        (c: GroupCellRecord) =>
          c.parent === sel.parent && c.scenario === sel.scenario && c.model === model && c.plan === plan && c.horizon_days === Number(horizon) && (sel.lift === "macro" || c.lift === sel.lift),
      );
      if (cells.length === 0) continue;
      const mean = (f: (c: GroupCellRecord) => number) => cells.reduce((a, c) => a + f(c), 0) / cells.length;
      const first = cells[0] as GroupCellRecord;
      out.push({
        model,
        n: cells.reduce((a, c) => a + c.n, 0),
        crps: mean((c) => c.crps_kg),
        nll: mean((c) => c.nll_nats),
        cov50: null,
        cov80: Number.NaN,
        cov90: mean((c) => c.cov90),
        width50: null,
        width80: Number.NaN,
        width90: mean((c) => c.width90_kg),
        source_path: first.source_path,
        source_sha256: first.source_sha256,
        study_id: first.study_id,
        target: "Y",
      });
    }
    return out;
  }
  const rows: ModelRow[] = [];
  for (const model of models) {
    const r = evidence.scores.find(
      (s: ScoreRecord) => s.study_id.startsWith(prefix) && s.parent === sel.parent && s.scenario === sel.scenario && s.model === model && s.lift === sel.lift,
    );
    if (!r) continue;
    rows.push({
      model,
      n: r.n,
      crps: r.crps,
      nll: r.nll,
      cov50: r.cov50,
      cov80: r.cov80,
      cov90: r.cov90,
      width50: r.width50,
      width80: r.width80,
      width90: r.width90,
      source_path: r.source_path,
      source_sha256: r.source_sha256,
      study_id: r.study_id,
      target: "Y",
    });
  }
  return rows;
}

/** Paired contrasts exist only for pooled macro scores, never per lift or per plan x horizon group. */
export function contrastsAvailable(sel: ForecastSelection): boolean {
  return sel.lift === "macro" && sel.group === "all";
}

export function selectContrasts(evidence: Evidence, sel: ForecastSelection, metric: "crps" | "nll" = "crps"): ContrastRecord[] {
  if (!contrastsAvailable(sel)) return [];
  const prefix = studyIdPrefix(sel.study);
  return evidence.contrasts.filter(
    (c) => c.study_id.startsWith(prefix) && c.parent === sel.parent && c.scenario === sel.scenario && c.metric === metric,
  );
}

export function selectShifts(evidence: Evidence, sel: ForecastSelection): ShiftRecord[] {
  const prefix = studyIdPrefix(sel.study);
  return evidence.shifts.filter((s) => s.study_id.startsWith(prefix) && s.parent === sel.parent);
}

/** Ridge-vs-GRU on target Y (RES-616): M2_C minus M1_C. */
export function ridgeVersusGru(evidence: Evidence): ContrastRecord[] {
  return evidence.contrasts.filter(
    (c) => c.study_id.startsWith(studyIdPrefix("RES-616")) && c.contrast === "M2_C-M1_C" && c.scenario === "CONTROL" && c.status === "PRIMARY",
  );
}

/** Magnitude/history contrasts on target Y (RES-639), CRPS. */
export function historyContrasts(evidence: Evidence): ContrastRecord[] {
  return evidence.contrasts.filter(
    (c) => c.study_id.startsWith(studyIdPrefix("RES-639")) && c.scenario === "CONTROL" && c.metric === "crps",
  );
}
