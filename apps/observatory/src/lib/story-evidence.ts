/**
 * Real, source-bound values used by the landing story. Every number is read from the hashed evidence file; a missing
 * record or an unparseable statement throws at build time instead of falling back to a typed-in value.
 */
import type { ContrastRecord, Evidence, FactRecord, ScoreRecord } from "./evidence";
import { studyIdPrefix } from "./forecast";

function need<T>(value: T | undefined | null, what: string): T {
  if (value === undefined || value === null) throw new Error(`story evidence: missing ${what}`);
  return value;
}

function match(statement: string, re: RegExp, what: string): number[] {
  const m = re.exec(statement);
  if (!m) throw new Error(`story evidence: cannot read ${what} from statement`);
  return m.slice(1).map(Number);
}

export interface G2Numbers {
  fact: FactRecord;
  disposition: string;
  convergedNative: [number, number];
  convergedDoubled: [number, number];
  stationary: [number, number];
  localRank: [number, number];
}

export function g2Numbers(evidence: Pick<Evidence, "facts">): G2Numbers {
  const fact = need(evidence.facts.find((f) => f.id === "G2"), "fact G2");
  const s = fact.statement;
  const disposition = need(/FULL_G2_IDENTIFICATION_UNSUPPORTED/.exec(s)?.[0], "G2 disposition");
  const [a, b] = match(s, /only (\d+) of (\d+) full-MLE starts converged/, "native-noise convergence");
  const [c, d] = match(s, /\((\d+) of (\d+) at doubled noise\)/, "doubled-noise convergence");
  const [e, f] = match(s, /(\d+) of (\d+) RES-592 starts were independently stationary/, "stationary starts");
  const [g, h] = match(s, /local rank is (\d+)\/(\d+)/, "local rank");
  return { fact, disposition, convergedNative: [a!, b!], convergedDoubled: [c!, d!], stationary: [e!, f!], localRank: [g!, h!] };
}

export function g1CapacityRmse(evidence: Pick<Evidence, "facts">): { fact: FactRecord; kg: string } {
  const fact = need(evidence.facts.find((f) => f.id === "G1"), "fact G1");
  const kg = need(/capacity RMSE is ([\d.]+) kg/.exec(fact.statement)?.[1], "G1 capacity RMSE");
  return { fact, kg };
}

export type ParentKey = "TEST_A" | "TEST_B";
export const PARENTS: ParentKey[] = ["TEST_A", "TEST_B"];

function controlMacro(evidence: Pick<Evidence, "scores">, study: "RES-616" | "RES-639", parent: ParentKey, model: string): ScoreRecord {
  const prefix = studyIdPrefix(study);
  return need(
    evidence.scores.find((s) => s.study_id.startsWith(prefix) && s.parent === parent && s.scenario === "CONTROL" && s.lift === "macro" && s.model === model),
    `${study} ${parent} ${model} control macro score`,
  );
}

function contrast(evidence: Pick<Evidence, "contrasts">, study: "RES-616" | "RES-639", parent: ParentKey, name: string): ContrastRecord {
  const prefix = studyIdPrefix(study);
  return need(
    evidence.contrasts.find((c) => c.study_id.startsWith(prefix) && c.parent === parent && c.scenario === "CONTROL" && c.metric === "crps" && c.contrast === name),
    `${study} ${parent} ${name} contrast`,
  );
}

export interface ModelScore {
  model: string;
  label: string;
  crps: number;
  record: ScoreRecord;
}

export interface RidgeGru {
  parents: Record<ParentKey, { scores: ModelScore[]; diff: ContrastRecord }>;
}

export function ridgeGru(evidence: Pick<Evidence, "scores" | "contrasts">): RidgeGru {
  const labels: Record<string, string> = { M0_C: "Persistence", M1_C: "Ridge", M2_C: "GRU" };
  const parents = {} as RidgeGru["parents"];
  for (const p of PARENTS) {
    parents[p] = {
      scores: (["M0_C", "M1_C", "M2_C"] as const).map((m) => {
        const record = controlMacro(evidence, "RES-616", p, m);
        return { model: m, label: labels[m]!, crps: record.crps, record };
      }),
      diff: contrast(evidence, "RES-616", p, "M2_C-M1_C"),
    };
  }
  return { parents };
}

export interface ScaleStudy {
  parents: Record<ParentKey, { scores: ModelScore[]; magVsGroup: ContrastRecord; historyVsMag: ContrastRecord }>;
}

export function scaleStudy(evidence: Pick<Evidence, "scores" | "contrasts">): ScaleStudy {
  const labels: Record<string, string> = { B_GROUP: "B_GROUP", B_MAG: "B_MAG", H_HISTORY: "H_HISTORY" };
  const parents = {} as ScaleStudy["parents"];
  for (const p of PARENTS) {
    parents[p] = {
      scores: (["B_GROUP", "B_MAG", "H_HISTORY"] as const).map((m) => {
        const record = controlMacro(evidence, "RES-639", p, m);
        return { model: m, label: labels[m]!, crps: record.crps, record };
      }),
      magVsGroup: contrast(evidence, "RES-639", p, "B_MAG-B_GROUP"),
      historyVsMag: contrast(evidence, "RES-639", p, "H_HISTORY-B_MAG"),
    };
  }
  return { parents };
}

/* ---------- Trimmed, serialisable payload for the client story (keeps the full evidence file out of the bundle). */

export interface Src {
  path: string;
  sha256: string;
}
export interface Interval {
  diff: number;
  lo: number;
  hi: number;
  relPct: number;
}
export interface StoryEvidence {
  revision: string;
  repository: string;
  g1: { kg: string; source: Src };
  g2: Omit<G2Numbers, "fact"> & { limits: string; source: Src };
  ridge: {
    disposition: string;
    ciScope: string;
    scoreSource: Src;
    contrastSource: Src;
    parents: Record<ParentKey, { scores: { model: string; label: string; crps: number }[]; diff: Interval }>;
  };
  scale: {
    disposition: string;
    ciScope: string;
    auditChecks: number | null;
    scoreSource: Src;
    contrastSource: Src;
    historyFeatures: number;
    parents: Record<ParentKey, { scores: { model: string; label: string; crps: number }[]; magVsGroup: Interval; historyVsMag: Interval }>;
  };
}

const interval = (c: ContrastRecord): Interval => ({ diff: c.diff, lo: c.ci_lo, hi: c.ci_hi, relPct: c.rel_pct });
const src = (r: { source_path: string; source_sha256: string }): Src => ({ path: r.source_path, sha256: r.source_sha256 });

/**
 * Number of participant-visible history summaries that H_HISTORY adds to B_MAG. This count is stated in the public
 * study report (not in the aggregate evidence tables); tests/unit/story.test.ts asserts the report still says so.
 */
export const HISTORY_FEATURES = { count: 127, path: "docs/studies/history-conditional-uncertainty.md", phrase: "the 127 RES-616 participant-visible summaries" } as const;
export function historyFeatureCount(): number {
  return HISTORY_FEATURES.count;
}

export function buildStoryEvidence(evidence: Evidence): StoryEvidence {
  const g1 = g1CapacityRmse(evidence);
  const { fact: g2fact, ...g2 } = g2Numbers(evidence);
  const rg = ridgeGru(evidence);
  const sc = scaleStudy(evidence);
  const s616 = need(evidence.studies.find((s) => s.id === "RES-616"), "study RES-616");
  const s639 = need(evidence.studies.find((s) => s.id === "RES-639"), "study RES-639");
  const trimScores = (xs: ModelScore[]) => xs.map(({ model, label, crps }) => ({ model, label, crps }));
  return {
    revision: evidence.source_revision,
    repository: evidence.source_repository,
    g1: { kg: g1.kg, source: src(g1.fact) },
    g2: { ...g2, limits: g2fact.limits, source: src(g2fact) },
    ridge: {
      disposition: s616.disposition,
      ciScope: rg.parents.TEST_A.diff.ci_scope ?? "",
      scoreSource: src(rg.parents.TEST_A.scores[0]!.record),
      contrastSource: src(rg.parents.TEST_A.diff),
      parents: {
        TEST_A: { scores: trimScores(rg.parents.TEST_A.scores), diff: interval(rg.parents.TEST_A.diff) },
        TEST_B: { scores: trimScores(rg.parents.TEST_B.scores), diff: interval(rg.parents.TEST_B.diff) },
      },
    },
    scale: {
      disposition: s639.disposition,
      ciScope: sc.parents.TEST_A.historyVsMag.ci_scope ?? "",
      auditChecks: s639.audit_checks,
      scoreSource: src(sc.parents.TEST_A.scores[0]!.record),
      contrastSource: src(sc.parents.TEST_A.historyVsMag),
      historyFeatures: historyFeatureCount(),
      parents: {
        TEST_A: { scores: trimScores(sc.parents.TEST_A.scores), magVsGroup: interval(sc.parents.TEST_A.magVsGroup), historyVsMag: interval(sc.parents.TEST_A.historyVsMag) },
        TEST_B: { scores: trimScores(sc.parents.TEST_B.scores), magVsGroup: interval(sc.parents.TEST_B.magVsGroup), historyVsMag: interval(sc.parents.TEST_B.historyVsMag) },
      },
    },
  };
}
