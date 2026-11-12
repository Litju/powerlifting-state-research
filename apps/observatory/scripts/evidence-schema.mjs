// Versioned schema for the Observatory evidence file. Pure data validators (zod).
import { z } from "zod";

export const SCHEMA_VERSION = "psr-observatory-evidence/1.0.0";
export const SOURCE_REPOSITORY = "Litju/powerlifting-state-research";
export const SOURCE_REVISION = "41191d6d17af5bf81ce0615efc244e1db604e6f6";

const sha = z.string().regex(/^[0-9a-f]{64}$/);
const finite = z.number().finite();

/** Fields every evidence record carries. */
export const provenance = {
  source_path: z.string().min(1),
  source_sha256: sha,
  study_id: z.string().min(1),
  /** C = latent capacity (or its change), E = expressed performance, Y = observed noisy assessment. Never mixed. */
  target: z.enum(["C", "E", "Y"]),
  cohort: z.string().min(1),
  unit: z.string().min(1),
  crps_sign: z.enum(["lower_is_better", "not_applicable"]),
  scenario_class: z.enum(["control", "shift", "not_applicable"]),
  ci_scope: z.string().nullable(),
  access: z.enum(["public", "restricted_aggregate_only"]),
};

const Parent = z.enum(["TEST_A", "TEST_B"]);
const Scenario = z.enum(["CONTROL", "VELOCITY_NOISE_SHIFT", "ADAPTATION_TIMESCALE_SHIFT"]);
const Lift = z.enum(["squat", "bench_press", "deadlift", "macro"]);

export const Source = z.strictObject({
  id: z.string(),
  path: z.string(),
  sha256: sha,
  bytes: z.number().int().positive(),
  kind: z.enum(["csv", "json", "markdown"]),
  access: z.literal("public"),
});

export const Score = z.strictObject({
  ...provenance,
  record: z.literal("score"),
  parent: Parent,
  scenario: Scenario,
  model: z.string(),
  lift: Lift,
  n: z.number().int(),
  crps: finite,
  nll: finite,
  abs_error: finite,
  cov50: finite.nullable(),
  cov80: finite,
  cov90: finite,
  width50: finite.nullable(),
  width80: finite,
  width90: finite,
  negative_mass: finite,
});

export const Contrast = z.strictObject({
  ...provenance,
  record: z.literal("contrast"),
  parent: Parent,
  scenario: Scenario,
  contrast: z.string(),
  status: z.enum(["PRIMARY", "descriptive"]),
  metric: z.enum(["crps", "nll"]),
  diff: finite,
  ci_lo: finite,
  ci_hi: finite,
  rel_pct: finite,
  rel_ci_lo_pct: finite,
  rel_ci_hi_pct: finite,
  reference_value: finite,
  sign_note: z.string(),
});

export const Shift = z.strictObject({
  ...provenance,
  record: z.literal("shift"),
  parent: Parent,
  scenario: Scenario,
  model: z.string(),
  crps_kg: finite,
  d_crps_vs_control_kg: finite,
  d_crps_pct: finite,
  nll_nats: finite,
  d_nll: finite,
  cov90: finite,
  d_cov90: finite,
  rank_by_crps: z.number().int(),
});

export const GroupSummary = z.strictObject({
  ...provenance,
  record: z.literal("group_summary"),
  parent: Parent,
  scenario: Scenario,
  comparison: z.string(),
  groups: z.number().int(),
  crps_worse: z.number().int(),
  nll_worse: z.number().int(),
  cov90_outside_85_95: z.number().int(),
  cov90_min: finite,
  cov90_max: finite,
});

export const GroupCell = z.strictObject({
  ...provenance,
  record: z.literal("group_cell"),
  parent: Parent,
  scenario: Scenario,
  model: z.string(),
  plan: z.enum(["continue", "step_up", "step_down", "cessation"]),
  horizon_days: z.union([z.literal(14), z.literal(28), z.literal(56)]),
  lift: z.enum(["squat", "bench_press", "deadlift"]),
  n: z.number().int(),
  crps_kg: finite,
  nll_nats: finite,
  cov90: finite,
  width90_kg: finite,
});

export const ScaleCoverage = z.strictObject({
  ...provenance,
  record: z.literal("scale_coverage"),
  parent: Parent,
  scenario: Scenario,
  model: z.string(),
  lift: z.enum(["squat", "bench_press", "deadlift"]),
  scale_quintile: z.number().int().min(1).max(5),
  n: z.number().int(),
  mean_sigma_kg: finite,
  cov50: finite,
  cov80: finite,
  cov90: finite,
});

export const Pit = z.strictObject({
  ...provenance,
  record: z.literal("pit"),
  parent: Parent,
  scenario: Scenario,
  model: z.string(),
  pit_bin: z.number().int().min(1).max(10),
  count: z.number().int(),
  fraction: finite,
});

export const Frontier = z.strictObject({
  ...provenance,
  record: z.literal("frontier"),
  method: z.string(),
  classification: z.string(),
  model_id: z.string(),
  fitted_instance_id: z.string(),
  seed: z.string(),
  lift: z.enum(["squat", "bench_press", "deadlift"]),
  rmse_kg: finite,
  mae_kg: finite,
  r2: finite,
  sre_ddof0: finite,
  parameter_count: z.number().int(),
});

export const RegistryEntry = z.strictObject({
  ...provenance,
  record: z.literal("registry"),
  slug: z.string(),
  display_name: z.string(),
  benchmark_id: z.string().nullable(),
  identity_authority: z.enum(["HISTORICAL_PROJECTION", "PUBLIC_NATIVE"]),
  historical_specimen_status: z.string(),
  historical_qualification_state: z.string(),
  public_implementation_status: z.string(),
  target_ontology: z.string(),
  task_type: z.string(),
  docs_path: z.string(),
});

export const Fact = z.strictObject({
  ...provenance,
  record: z.literal("fact"),
  id: z.string(),
  stage: z.string(),
  title: z.string(),
  statement: z.string(),
  limits: z.string(),
  /** Substrings that must occur verbatim in the source file; the build fails otherwise. */
  verified_strings: z.array(z.string()).min(1),
});

export const Study = z.strictObject({
  id: z.string(),
  label: z.string(),
  study_id: z.string(),
  disposition: z.string(),
  target: z.enum(["C", "E", "Y"]),
  primary: z.record(z.string(), z.strictObject({ diff: finite, ci_lo: finite, ci_hi: finite, rel_pct: finite })),
  nonclaims: z.array(z.string()),
  summary_path: z.string(),
  manifest_path: z.string(),
  audit_path: z.string().nullable(),
  audit_checks: z.number().int().nullable(),
});

export const Evidence = z.strictObject({
  schema_version: z.literal(SCHEMA_VERSION),
  source_repository: z.literal(SOURCE_REPOSITORY),
  source_revision: z.literal(SOURCE_REVISION),
  conventions: z.strictObject({
    crps: z.string(),
    contrast_sign: z.string(),
    targets: z.record(z.string(), z.string()),
    scenario_classes: z.string(),
    ci_scope: z.record(z.string(), z.string()),
    macro: z.string(),
  }),
  sources: z.array(Source),
  studies: z.array(Study),
  scores: z.array(Score),
  contrasts: z.array(Contrast),
  shifts: z.array(Shift),
  group_summaries: z.array(GroupSummary),
  group_cells: z.array(GroupCell),
  scale_coverage: z.array(ScaleCoverage),
  pit: z.array(Pit),
  frontier: z.array(Frontier),
  registry: z.array(RegistryEntry),
  facts: z.array(Fact),
});
