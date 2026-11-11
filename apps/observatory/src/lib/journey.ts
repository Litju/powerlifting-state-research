import type { Evidence, FactRecord, StudyRecord } from "./evidence";

export interface Stage {
  id: string;
  label: string;
  question: string;
  verdict: string;
  factIds: string[];
  studyIds?: string[];
  lineage: string;
  tone: "negative" | "limited" | "descriptive";
}

export const STAGES: Stage[] = [
  {
    id: "G1",
    label: "G1 · Inversion",
    question: "Can observations be inverted, and what does that reveal?",
    verdict: "Expressed performance can be recovered; latent capacity cannot, even without noise.",
    factIds: ["G1"],
    lineage: "New public-native experiment (observation inversion). Historical G1 quantitative evidence was not recovered, and a historical PROVEN label is metadata, not evidence.",
    tone: "limited",
  },
  {
    id: "G2",
    label: "G2 · Identification",
    question: "Does target reconstruction identify the full 16-parameter system?",
    verdict: "FULL_G2_IDENTIFICATION_UNSUPPORTED given current evidence. This is not a proof of impossibility.",
    factIds: ["G2"],
    lineage: "RES-289 reconstruction study, RES-557 and RES-592 numerical admission work, and the RES-617 decision memo, which adds no computation and reads preserved aggregates only.",
    tone: "negative",
  },
  {
    id: "G3",
    label: "G3 · Surrogates",
    question: "Can public-data surrogates reproduce predictions or observable records?",
    verdict: "Donor copying adds no support; structural non-identification remained inconclusive.",
    factIds: ["G3"],
    lineage: "New public-native experiment (RES-290 public-surrogate reconstruction); the historical G3 home is navigation metadata.",
    tone: "limited",
  },
  {
    id: "G4",
    label: "G4 · Synthetic pretraining",
    question: "Does synthetic pretraining add value beyond public data and matched compute?",
    verdict: "No demonstrated advantage over the compute-matched control. The corrected reading is a negative finding.",
    factIds: ["G4"],
    lineage: "RES-292 original report, RES-510 corrected pooled inference and RES-511 initialization erratum. The correction is a proposal pending independent scientific approval.",
    tone: "negative",
  },
  {
    id: "BENCHMARK_VALIDITY",
    label: "Benchmark validity",
    question: "What may be compared across models and worlds?",
    verdict: "Descriptive panels only. No universal leaderboard, and historical cross-version comparisons are rejected.",
    factIds: ["BENCHMARK_VALIDITY"],
    lineage: "RES-284 audit suite and the RES-294 synthesis; see the benchmarks page for the registry and panel.",
    tone: "limited",
  },
  {
    id: "RES-293",
    label: "RES-293 · Representation",
    question: "Which representation, learner and information choices matter?",
    verdict: "Fixed finite-budget contrasts only; no optimal-frontier or necessity claim.",
    factIds: ["RES-293"],
    lineage: "Frozen protocol, one execution of 30 fits, sealed before evaluation truth was opened.",
    tone: "descriptive",
  },
  {
    id: "RES-615",
    label: "RES-615 · Probabilistic (M10 to M12)",
    question: "Can an unchanged GRU point forecast be supplemented with useful predictive distributions?",
    verdict: "Small proper-score gains on same-law tests, absolute degradation under shift, and conditional reliability not established.",
    factIds: ["M10-M12-gain", "M11-gain", "M12-shift"],
    lineage: "Public methods and aggregate summary only. M10, M11 and M12 are historical phase aliases for conditional scale, group calibration with support restriction, and controlled shifts.",
    tone: "limited",
  },
  {
    id: "RES-616",
    label: "RES-616 · Ridge vs GRU",
    question: "Does a GRU forecast the observed future assessment better than Ridge?",
    verdict: "OBSERVABLE_FORECASTING_NOT_QUALIFIED: the GRU is slightly worse than Ridge on both parents.",
    factIds: ["RES-616-note"],
    studyIds: ["RES-616"],
    lineage: "Frozen design, sealed predictions, one opening of test truth. Target Y is distinct from latent capacity and from expressed performance.",
    tone: "negative",
  },
  {
    id: "RES-639",
    label: "RES-639 · Histories",
    question: "Do participant-visible histories improve predictive scale beyond forecast magnitude?",
    verdict: "MIXED_OR_NOT_QUALIFIED: H_HISTORY is slightly worse than B_MAG on both parents.",
    factIds: ["RES-639-note"],
    studyIds: ["RES-639"],
    lineage: "One authorized run with an independent evidence audit. RES-617 (G2) was not reopened and RES-616's dispositions are unchanged.",
    tone: "negative",
  },
];

export function factsFor(stage: Stage, evidence: Pick<Evidence, "facts">): FactRecord[] {
  return stage.factIds.flatMap((id) => evidence.facts.filter((f) => f.id === id));
}

export function studiesFor(stage: Stage, evidence: Pick<Evidence, "studies">): StudyRecord[] {
  return (stage.studyIds ?? []).flatMap((id) => evidence.studies.filter((s) => s.id === id));
}
