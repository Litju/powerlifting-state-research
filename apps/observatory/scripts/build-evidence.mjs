#!/usr/bin/env node
// Builds apps/observatory/data/evidence.v1.json from tracked public sources of the repository root.
// The build FAILS (non-zero exit) on any missing source, contradicted number or schema violation.
// There is no fallback to invented values.  `--check` verifies that the committed file is byte-identical.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  Evidence,
  SCHEMA_VERSION,
  SOURCE_REPOSITORY,
  SOURCE_REVISION,
} from "./evidence-schema.mjs";

const here = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = resolve(process.env.PSR_REPO_ROOT ?? join(here, "..", "..", ".."));
export const OUT_PATH = join(here, "..", "data", "evidence.v1.json");

const RES616 = "results/studies/observable_strength_forecasting/full";
const RES639 = "results/studies/history_conditional_uncertainty/full";

class EvidenceError extends Error {}
const fail = (msg) => {
  throw new EvidenceError(msg);
};
const assert = (cond, msg) => {
  if (!cond) fail(msg);
};

// ---------------------------------------------------------------- source registry
const sources = new Map();
function readSource(path, kind) {
  const abs = join(REPO_ROOT, path);
  if (!existsSync(abs)) fail(`missing source: ${path}`);
  const buf = readFileSync(abs);
  const sha256 = createHash("sha256").update(buf).digest("hex");
  const text = buf.toString("utf8");
  if (!sources.has(path)) {
    sources.set(path, { id: path, path, sha256, bytes: buf.length, kind, access: "public" });
  }
  return { path, sha256, text };
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i += 1;
      row.push(field);
      field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else field += ch;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  const header = rows.shift();
  return rows.map((r, index) => {
    assert(r.length === header.length, `ragged CSV row ${index + 2}`);
    return Object.fromEntries(header.map((h, i) => [h, r[i]]));
  });
}

function csv(path) {
  const src = readSource(path, "csv");
  return { ...src, rows: parseCsv(src.text) };
}
function json(path) {
  const src = readSource(path, "json");
  return { ...src, value: JSON.parse(src.text) };
}
function md(path) {
  return readSource(path, "markdown");
}
const num = (value, where) => {
  const n = Number(value);
  assert(value !== "" && Number.isFinite(n), `non-finite number in ${where}: ${value}`);
  return n;
};
const int = (value, where) => {
  const n = num(value, where);
  assert(Number.isInteger(n), `non-integer in ${where}: ${value}`);
  return n;
};
const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const near = (a, b, tol, what) =>
  assert(Math.abs(a - b) <= tol, `${what}: ${a} differs from ${b} by more than ${tol}`);

// ---------------------------------------------------------------- conventions
const CRPS_SIGN =
  "CRPS and NLL are lower-is-better proper scores (kg and nats per observation). A contrast is first-minus-second; a positive difference means the first-named model is worse.";
const CI_616 =
  "95% stratified entity-cluster bootstrap, 1,000 replicates per parent; conditional on the fixed fitted models and calibration; excludes GRU training-seed variation (not tested).";
const CI_639 =
  "95% paired stratified entity-cluster bootstrap, 1,000 replicates per parent; conditional on the frozen Ridge and scale models; per-entity scores are not published so intervals are not independently recomputable.";

const scenarioClass = (s) => (s === "CONTROL" ? "control" : "shift");

function base(src, studyId, extra) {
  return {
    source_path: src.path,
    source_sha256: src.sha256,
    study_id: studyId,
    target: "Y",
    unit: "kg",
    crps_sign: "lower_is_better",
    access: "public",
    ...extra,
  };
}

const scoreRows = (src, studyId, modelKey) =>
  src.rows.map((r) => ({
    record: "score",
    ...base(src, studyId, {
      cohort: r.parent,
      scenario_class: scenarioClass(r.scenario),
      ci_scope: null,
    }),
    parent: r.parent,
    scenario: r.scenario,
    model: r[modelKey],
    lift: r.lift,
    n: int(r.n, "n"),
    crps: num(r.crps, "crps"),
    nll: num(r.nll, "nll"),
    abs_error: num(r.abs_error, "abs_error"),
    cov50: r.cov50 === undefined ? null : num(r.cov50, "cov50"),
    cov80: num(r.cov80, "cov80"),
    cov90: num(r.cov90, "cov90"),
    width50: r.width50 === undefined ? null : num(r.width50, "width50"),
    width80: num(r.width80, "width80"),
    width90: num(r.width90, "width90"),
    negative_mass: num(r.negative_mass, "negative_mass"),
  }));

/** The stored tables already contain a macro row per cell; recompute it from the three lifts and require agreement. */
function verifyMacro(rows, label) {
  const groups = new Map();
  for (const r of rows) {
    const key = `${r.parent}|${r.scenario}|${r.model}`;
    if (!groups.has(key)) groups.set(key, { lifts: [], macro: null });
    const g = groups.get(key);
    if (r.lift === "macro") g.macro = r;
    else g.lifts.push(r);
  }
  for (const [key, g] of groups) {
    assert(g.lifts.length === 3 && g.macro, `${label}: expected three lifts and one macro row for ${key}`);
    for (const field of ["crps", "nll", "abs_error", "cov80", "cov90", "width80", "width90", "negative_mass"]) {
      near(mean(g.lifts.map((r) => r[field])), g.macro[field], 5e-9, `${label}: recomputed macro ${field} for ${key}`);
    }
  }
  return rows;
}

// ---------------------------------------------------------------- RES-616
function build616() {
  const manifest = json(`${RES616}/manifest.json`);
  const summary = json(`${RES616}/summary.json`);
  const scores = csv(`${RES616}/scores.csv`);
  const paired = csv(`${RES616}/paired_contrasts.csv`);
  const shift = csv(`${RES616}/shift_degradation.csv`);
  const groups = csv(`${RES616}/group_summary.csv`);
  const cells = csv(`${RES616}/group_calibration.csv`);
  const studyId = manifest.value.study_id;
  assert(studyId.startsWith("psr:study:observable-strength-assessment-forecasting@"), "RES-616 study id");
  assert(summary.value.profile === "full" && manifest.value.profile === "full", "RES-616 must be the full profile");
  assert(summary.value.disposition === manifest.value.disposition, "RES-616 disposition mismatch");

  // Manifest hashes must match the files actually read.
  for (const file of ["scores.csv", "paired_contrasts.csv", "shift_degradation.csv", "group_summary.csv", "group_calibration.csv", "summary.json"]) {
    const rel = `${RES616}/${file}`;
    assert(sources.get(rel)?.sha256 === manifest.value.output_sha256[file], `RES-616 manifest hash mismatch: ${file}`);
  }

  const scoreRecords = verifyMacro(scoreRows(scores, studyId, "arm"), "RES-616");
  const macro = (parent, scenario, model) =>
    scoreRecords.find((r) => r.lift === "macro" && r.parent === parent && r.scenario === scenario && r.model === model);

  // Recompute macro CRPS and cross-check against the stored shift table.
  const shiftRecords = shift.rows.map((r) => {
    const rec = {
      record: "shift",
      ...base(shift, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: null }),
      parent: r.parent,
      scenario: r.scenario,
      model: r.arm,
      crps_kg: num(r.crps_kg, "crps_kg"),
      d_crps_vs_control_kg: num(r.d_crps_vs_control_kg, "d_crps"),
      d_crps_pct: num(r.d_crps_pct, "d_crps_pct"),
      nll_nats: num(r.nll_nats, "nll"),
      d_nll: num(r.d_nll, "d_nll"),
      cov90: num(r.cov90, "cov90"),
      d_cov90: num(r.d_cov90, "d_cov90"),
      rank_by_crps: int(r.rank_by_crps, "rank"),
    };
    const m = macro(r.parent, r.scenario, r.arm);
    assert(m, `no recomputed macro for ${r.parent}/${r.scenario}/${r.arm}`);
    near(m.crps, rec.crps_kg, 5e-9, `macro CRPS ${r.parent}/${r.scenario}/${r.arm}`);
    near(m.nll, rec.nll_nats, 5e-9, `macro NLL ${r.parent}/${r.scenario}/${r.arm}`);
    return rec;
  });

  const contrastRecords = paired.rows.map((r) => ({
    record: "contrast",
    ...base(paired, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: CI_616 }),
    parent: r.parent,
    scenario: r.scenario,
    contrast: r.contrast,
    status: r.status,
    metric: "crps",
    diff: num(r.diff_crps_kg, "diff"),
    ci_lo: num(r.ci_lo, "ci_lo"),
    ci_hi: num(r.ci_hi, "ci_hi"),
    rel_pct: num(r.rel_pct, "rel_pct"),
    rel_ci_lo_pct: num(r.rel_ci_lo_pct, "rel_ci_lo"),
    rel_ci_hi_pct: num(r.rel_ci_hi_pct, "rel_ci_hi"),
    reference_value: num(r.reference_crps_kg, "reference"),
    sign_note: "difference = CRPS(first) - CRPS(second) in kg; positive means the first model is worse",
  }));

  // Primary endpoint: summary.json must agree with the paired table, and with the documented values.
  for (const parent of ["TEST_A", "TEST_B"]) {
    const row = contrastRecords.find(
      (c) => c.parent === parent && c.scenario === "CONTROL" && c.contrast === "M2_C-M1_C" && c.status === "PRIMARY",
    );
    assert(row, `RES-616 primary row missing for ${parent}`);
    const s = summary.value.primary[parent];
    near(s.diff, row.diff, 1e-8, `RES-616 primary diff ${parent}`);
    near(s.ci_lo, row.ci_lo, 1e-8, `RES-616 primary ci_lo ${parent}`);
    near(s.ci_hi, row.ci_hi, 1e-8, `RES-616 primary ci_hi ${parent}`);
    // M2_C - M1_C must equal the recomputed macro difference.
    near(
      macro(parent, "CONTROL", "M2_C").crps - macro(parent, "CONTROL", "M1_C").crps,
      row.diff,
      1e-8,
      `RES-616 recomputed paired difference ${parent}`,
    );
  }
  // Numbers stated in the study document.
  const doc = md("docs/studies/observable-strength-forecasting.md");
  const stated = { TEST_A: { M1_C: 6.6378, M2_C: 6.7481 }, TEST_B: { M1_C: 6.6281, M2_C: 6.7197 } };
  for (const [parent, arms] of Object.entries(stated)) {
    for (const [arm, value] of Object.entries(arms)) {
      const got = macro(parent, "CONTROL", arm).crps;
      near(got, value, 5e-5, `RES-616 ${arm} ${parent} control macro CRPS vs documented ${value}`);
      assert(doc.text.includes(value.toFixed(4)), `RES-616 document no longer states ${value}`);
    }
  }
  assert(doc.text.includes("+0.1103") && doc.text.includes("+0.0916"), "RES-616 documented primary differences");

  const groupSummaries = groups.rows.map((r) => ({
    record: "group_summary",
    ...base(groups, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: null, crps_sign: "lower_is_better" }),
    parent: r.parent,
    scenario: r.scenario,
    comparison: r.comparison,
    groups: int(r.groups, "groups"),
    crps_worse: int(r.crps_worse, "crps_worse"),
    nll_worse: int(r.nll_worse, "nll_worse"),
    cov90_outside_85_95: int(r.cov90_outside_85_95, "outside"),
    cov90_min: num(r.cov90_min, "min"),
    cov90_max: num(r.cov90_max, "max"),
  }));
  const cellRecords = cells.rows.map((r) => {
    const [plan, horizon] = r.plan_horizon.split("/");
    return {
      record: "group_cell",
      ...base(cells, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: null }),
      parent: r.parent,
      scenario: r.scenario,
      model: r.arm,
      plan,
      horizon_days: int(horizon, "horizon"),
      lift: r.lift,
      n: int(r.n, "n"),
      crps_kg: num(r.crps_kg, "crps"),
      nll_nats: num(r.nll_nats, "nll"),
      cov90: num(r.cov90, "cov90"),
      width90_kg: num(r.width90_kg, "width90"),
    };
  });
  const study = {
    id: "RES-616",
    label: "Observable strength-assessment forecasting",
    study_id: studyId,
    disposition: summary.value.disposition,
    target: "Y",
    primary: Object.fromEntries(
      Object.entries(summary.value.primary).map(([k, v]) => [k, { diff: v.diff, ci_lo: v.ci_lo, ci_hi: v.ci_hi, rel_pct: v.rel_pct }]),
    ),
    nonclaims: manifest.value.nonclaims,
    summary_path: summary.path,
    manifest_path: manifest.path,
    audit_path: null,
    audit_checks: null,
  };
  return { study, scoreRecords, contrastRecords, shiftRecords, groupSummaries, cellRecords };
}

// ---------------------------------------------------------------- RES-639
function build639() {
  const manifest = json(`${RES639}/manifest.json`);
  const summary = json(`${RES639}/summary.json`);
  const audit = json(`${RES639}/independent-audit/evidence-audit.json`);
  const scores = csv(`${RES639}/scores.csv`);
  const paired = csv(`${RES639}/paired_contrasts.csv`);
  const shift = csv(`${RES639}/shift_degradation.csv`);
  const cond = csv(`${RES639}/conditional_coverage.csv`);
  const pit = csv(`${RES639}/pit.csv`);
  const studyId = manifest.value.study_id;
  assert(studyId.startsWith("psr:study:history-conditioned-assessment-uncertainty@"), "RES-639 study id");
  assert(summary.value.profile === "full", "RES-639 must be the full profile");
  assert(summary.value.disposition === manifest.value.disposition, "RES-639 disposition mismatch");
  for (const file of ["scores.csv", "paired_contrasts.csv", "shift_degradation.csv", "conditional_coverage.csv", "pit.csv", "summary.json"]) {
    assert(sources.get(`${RES639}/${file}`)?.sha256 === manifest.value.output_sha256[file], `RES-639 manifest hash mismatch: ${file}`);
  }
  // Independent audit: every boolean check must be true, none failed.
  const checks = Object.entries(audit.value).filter(([, v]) => typeof v === "boolean");
  assert(checks.length === audit.value.n_checks, "RES-639 audit check count");
  assert(checks.every(([, v]) => v === true), "RES-639 audit contains a failed check");
  assert(Array.isArray(audit.value.failed_audit_checks) && audit.value.failed_audit_checks.length === 0, "RES-639 failed audit checks");

  const scoreRecords = verifyMacro(scoreRows(scores, studyId, "model"), "RES-639");
  const macro = (parent, scenario, model) =>
    scoreRecords.find((r) => r.lift === "macro" && r.parent === parent && r.scenario === scenario && r.model === model);
  for (const r of shift.rows) {
    const m = macro(r.parent, r.scenario, r.model);
    assert(m, `no macro for ${r.parent}/${r.scenario}/${r.model}`);
    near(m.crps, num(r.crps_kg, "crps"), 5e-9, `RES-639 macro CRPS ${r.parent}/${r.scenario}/${r.model}`);
    near(m.nll, num(r.nll_nats, "nll"), 5e-9, `RES-639 macro NLL ${r.parent}/${r.scenario}/${r.model}`);
    near(m.cov90, num(r.cov90, "cov90"), 5e-9, `RES-639 macro cov90 ${r.parent}/${r.scenario}/${r.model}`);
  }
  const shiftRecords = shift.rows.map((r) => ({
    record: "shift",
    ...base(shift, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: null }),
    parent: r.parent,
    scenario: r.scenario,
    model: r.model,
    crps_kg: num(r.crps_kg, "crps"),
    d_crps_vs_control_kg: num(r.d_crps_vs_control_kg, "d_crps"),
    d_crps_pct: num(r.d_crps_pct, "d_crps_pct"),
    nll_nats: num(r.nll_nats, "nll"),
    d_nll: num(r.d_nll, "d_nll"),
    cov90: num(r.cov90, "cov90"),
    d_cov90: num(r.d_cov90, "d_cov90"),
    rank_by_crps: int(r.rank_by_crps, "rank"),
  }));
  const contrastRecords = paired.rows.map((r) => ({
    record: "contrast",
    ...base(paired, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: CI_639 }),
    parent: r.parent,
    scenario: r.scenario,
    contrast: r.contrast,
    status: r.status,
    metric: r.metric,
    diff: num(r.diff, "diff"),
    ci_lo: num(r.ci_lo, "ci_lo"),
    ci_hi: num(r.ci_hi, "ci_hi"),
    rel_pct: num(r.rel_pct, "rel_pct"),
    rel_ci_lo_pct: num(r.rel_ci_lo_pct, "rel_ci_lo"),
    rel_ci_hi_pct: num(r.rel_ci_hi_pct, "rel_ci_hi"),
    reference_value: num(r.reference_value, "reference"),
    sign_note: `difference = ${r.metric.toUpperCase()}(first) - ${r.metric.toUpperCase()}(second); positive means the first model is worse`,
  }));

  const doc = md("docs/studies/history-conditional-uncertainty.md");
  const expected = { TEST_A: 0.024194, TEST_B: 0.018465 };
  for (const parent of ["TEST_A", "TEST_B"]) {
    const row = contrastRecords.find(
      (c) => c.parent === parent && c.scenario === "CONTROL" && c.contrast === "H_HISTORY-B_MAG" && c.status === "PRIMARY" && c.metric === "crps",
    );
    assert(row, `RES-639 primary row missing for ${parent}`);
    near(row.diff, expected[parent], 5e-7, `RES-639 H_HISTORY-B_MAG ${parent} vs documented +${expected[parent]} kg`);
    near(summary.value.primary[parent].diff, row.diff, 1e-8, `RES-639 summary.json primary ${parent}`);
    near(macro(parent, "CONTROL", "H_HISTORY").crps - macro(parent, "CONTROL", "B_MAG").crps, row.diff, 1e-8, `RES-639 recomputed paired difference ${parent}`);
    assert(row.ci_lo > 0, `RES-639 expected interval above zero for ${parent}`);
  }
  assert(doc.text.includes("+0.0242") && doc.text.includes("+0.0185"), "RES-639 document stated differences");
  const ridge = (parent) => macro(parent, "CONTROL", "B_GROUP");
  assert(ridge("TEST_A") && ridge("TEST_B"), "RES-639 B_GROUP rows");

  const scaleRecords = cond.rows.map((r) => ({
    record: "scale_coverage",
    ...base(cond, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: null, crps_sign: "not_applicable" }),
    parent: r.parent,
    scenario: r.scenario,
    model: r.model,
    lift: r.lift,
    scale_quintile: int(r.scale_quintile, "quintile"),
    n: int(r.n, "n"),
    mean_sigma_kg: num(r.mean_sigma_kg, "sigma"),
    cov50: num(r.cov50, "cov50"),
    cov80: num(r.cov80, "cov80"),
    cov90: num(r.cov90, "cov90"),
  }));
  const pitRecords = pit.rows.map((r) => ({
    record: "pit",
    ...base(pit, studyId, { cohort: r.parent, scenario_class: scenarioClass(r.scenario), ci_scope: null, crps_sign: "not_applicable", unit: "fraction of entity-lift outcomes" }),
    parent: r.parent,
    scenario: r.scenario,
    model: r.model,
    pit_bin: int(r.pit_bin, "pit_bin"),
    count: int(r.count, "count"),
    fraction: num(r.fraction, "fraction"),
  }));
  const study = {
    id: "RES-639",
    label: "History-conditioned predictive uncertainty",
    study_id: studyId,
    disposition: summary.value.disposition,
    target: "Y",
    primary: Object.fromEntries(
      Object.entries(summary.value.primary).map(([k, v]) => [k, { diff: v.diff, ci_lo: v.ci_lo, ci_hi: v.ci_hi, rel_pct: v.rel_pct }]),
    ),
    nonclaims: manifest.value.nonclaims,
    summary_path: summary.path,
    manifest_path: manifest.path,
    audit_path: audit.path,
    audit_checks: audit.value.n_checks,
  };
  return { study, scoreRecords, contrastRecords, shiftRecords, scaleRecords, pitRecords };
}

// ---------------------------------------------------------------- frontier + registry
function docsPath(slug) {
  const path = `docs/benchmarks/${slug.replaceAll("_", "-")}.md`;
  return md(path).path; // fails when the research card is missing and binds its hash
}

function buildFrontier() {
  const f = csv("results/tables/public-native-comparator-frontier.csv");
  const reg = json("artifacts/registries/benchmark-registry.json");
  const iid = reg.value.benchmarks.find((b) => b.slug === "iid_latent_capacity_change_with_transient_expression_forecasting");
  assert(iid?.benchmark_id, "public-native benchmark id missing from registry");
  const lifts = { squat_delta_capacity_kg: "squat", bench_press_delta_capacity_kg: "bench_press", deadlift_delta_capacity_kg: "deadlift" };
  const records = f.rows.map((r) => {
    assert(lifts[r.target], `unexpected frontier target ${r.target}`);
    return {
      record: "frontier",
      ...base(f, iid.benchmark_id, {
        target: "C",
        cohort: "public IID realization (validation evaluation)",
        crps_sign: "not_applicable",
        scenario_class: "not_applicable",
        ci_scope: null,
      }),
      method: r.method,
      classification: r.classification,
      model_id: r.model_id,
      fitted_instance_id: r.fitted_instance_id,
      seed: r.seed,
      lift: lifts[r.target],
      rmse_kg: num(r.rmse_kg, "rmse"),
      mae_kg: num(r.mae_kg, "mae"),
      r2: num(r.r2, "r2"),
      sre_ddof0: num(r.sre_ddof0, "sre"),
      parameter_count: int(r.parameter_count, "params"),
    };
  });
  const identities = new Set(records.map((r) => r.fitted_instance_id));
  assert(records.length === 66 && identities.size === 22, `frontier must have 22 identities x 3 targets, got ${identities.size} x ${records.length}`);
  assert(new Set(records.map((r) => r.method)).size === 7, "frontier must contain seven learner families");
  const registry = reg.value.benchmarks.map((b) => ({
    record: "registry",
    ...base(reg, b.benchmark_id ?? `psr:benchmark-spec:${b.slug}@historical-projection`, {
      target: "C",
      cohort: b.identity_authority === "PUBLIC_NATIVE" ? "public-native IID world" : "historical world (projection)",
      crps_sign: "not_applicable",
      scenario_class: "not_applicable",
      ci_scope: null,
      unit: "not_applicable",
    }),
    slug: b.slug,
    display_name: b.display_name,
    benchmark_id: b.benchmark_id,
    identity_authority: b.identity_authority,
    historical_specimen_status: b.historical_specimen_status,
    historical_qualification_state: b.historical_qualification_state,
    public_implementation_status: b.public_implementation_status,
    target_ontology: b.target_ontology,
    task_type: b.task_type,
    docs_path: docsPath(b.slug),
  }));
  assert(registry.length === 9, "benchmark registry must have nine entries");
  assert(registry.filter((r) => r.identity_authority === "PUBLIC_NATIVE").length === 1, "exactly one public-native benchmark expected");
  return { records, registry };
}

// ---------------------------------------------------------------- curated facts (verified against doc text)
function buildFacts() {
  const defs = [
    {
      id: "G1", stage: "G1", path: "docs/studies/index.md", target: "E", unit: "kg",
      title: "Observation inversion",
      statement: "Assessment, load and velocity factor through expressed performance. Noiseless expressed-performance recovery does not recover latent capacity: last-observation squat expression error is zero while capacity RMSE is 8.355256 kg in the reported noiseless condition.",
      limits: "Local Jacobian rank is not a global inverse proof. History averaging can mix changing states; paired noise-channel conclusions are condition-specific. Synthetic system only.",
      verify: ["8.355256 kg", "Local Jacobian rank is not a global inverse proof"],
    },
    {
      id: "G2", stage: "G2", path: "docs/studies/g2-identifiability-decision.md", target: "C", unit: "not_applicable",
      title: "Identification of the full 16-parameter model",
      statement: "Disposition FULL_G2_IDENTIFICATION_UNSUPPORTED given the current evidence: at native noise only 7 of 256 full-MLE starts converged (22 of 256 at doubled noise); 17 of 192 RES-592 starts were independently stationary; local rank is 16/16 but condition numbers are large.",
      limits: "This is not a proof of impossibility. Failing to find a competing solution does not prove uniqueness, and no result is a theorem about global identifiability. Forward simulation and local sensitivity remain supported.",
      verify: ["FULL_G2_IDENTIFICATION_UNSUPPORTED", "7/256 full-MLE starts converged", "17/192 overall", "a theorem about global identifiability"],
    },
    {
      id: "G3", stage: "G3", path: "results/studies/res294-definition-b-final-synthesis.md", target: "Y", unit: "kg",
      title: "Public-surrogate reconstruction",
      statement: "The empirical resampler generated 384 records from 245 unique fitting donors with exact donor-copy fraction 1.000. Across 54 conditional-model cells one had lower point RMSE than the empirical plan-by-horizon mean; Sequence RFF Ridge had higher RMSE than Summary Ridge in 27/27 paired cells.",
      limits: "Predictive agreement does not establish source-mechanism recovery. The structural non-identification demonstration remains inconclusive; off-support and real-athlete transfer were not evaluated.",
      verify: ["384 records from 245 unique fitting donors", "27/27 paired cells", "remains **INCONCLUSIVE**"],
    },
    {
      id: "G4", stage: "G4", path: "docs/studies/g4-reader-corrections-v1.md", target: "C", unit: "kg",
      title: "Synthetic-pretraining transfer, corrected reading",
      statement: "Across 108 pooled cells the original classification was 98 equivalence / 9 inconclusive / 1 benefit; the corrected crossed-bootstrap analysis after the Monte Carlo guard gives 97 / 11 / 0. Against the compute-matched public-only control, 17 of 18 primary bootstrap-pretraining cells are equivalent and one is inconclusive.",
      limits: "Corrected inference is a proposal pending independent scientific approval. Random nonzero bias initialization deviated from the zero-bias specification and its effect is unknown. Five fits do not establish seed-population coverage.",
      verify: ["| Original published pooled | 98 | 9 | 1 | 0 |", "| Corrected after frozen Monte Carlo guard | 97 | 11 | 0 | 0 |", "17 equivalence and 1 inconclusive over 18 cells", "independent scientific approval pending"],
    },
    {
      id: "BENCHMARK_VALIDITY", stage: "Benchmark validity", path: "results/studies/res294-definition-b-final-synthesis.md", target: "C", unit: "not_applicable",
      title: "Benchmark validity and audits",
      statement: "The saved M4 panel has seven learner families and 22 candidate fit or ensemble identities on the public IID realization. The audit suite records 264 unsupported uncertainty entries, a shortcut-dependence audit that is NOT_RUN, and 36 historical cross-version numeric comparisons REJECTED_FOR_NUMERICAL_COMPARISON.",
      limits: "The panel is descriptive: representations, budgets, hardware and information privileges differ. There is no universal scalar leaderboard.",
      verify: ["seven learner families and 22 candidate fit/ensemble identities", "264 unsupported", "`NOT_RUN`", "REJECTED_FOR_NUMERICAL_COMPARISON"],
    },
    {
      id: "RES-293", stage: "RES-293", path: "results/studies/res294-definition-b-final-synthesis.md", target: "C", unit: "kg",
      title: "Representation, learner and information ablations",
      statement: "Six configurations and five paired seeds gave 30 CPU fits of 60 epochs and 2,340 updates each, with 21 target-wise exploratory contrasts and 105 per-seed contrasts.",
      limits: "Point differences describe these fixed finite-budget procedures only. The multiplier envelope is descriptive; no calibrated coverage, significance or equivalence margin is claimed.",
      verify: ["30 fits of 60 epochs / 2,340 updates", "105 seed-specific contrasts", "descriptive"],
    },
    {
      id: "RES-616-note", stage: "RES-616", path: "docs/studies/observable-strength-forecasting.md", target: "Y", unit: "kg",
      title: "Ridge versus GRU on the observed assessment",
      statement: "A newly fitted GRU beats persistence by about 25-26% but is slightly worse than Ridge: +0.1103 kg [+0.0679, +0.1487] on TEST_A and +0.0916 kg [+0.0524, +0.1333] on TEST_B.",
      limits: "One GRU initialization was fitted, so training-seed stability is not tested. Statistically distinguishable, but about 1.5% in size.",
      verify: ["Training-seed stability is **not tested**", "+0.1103", "+0.0916"],
    },
    {
      id: "RES-639-note", stage: "RES-639", path: "docs/studies/history-conditional-uncertainty.md", target: "Y", unit: "kg",
      title: "Participant-visible histories and predictive scale",
      statement: "H_HISTORY is slightly worse than forecast magnitude alone (B_MAG): +0.024194 kg on TEST_A and +0.018465 kg on TEST_B, intervals above zero. The frozen screen needed at least a 1% improvement on both parents.",
      limits: "The label distinguishable_below_screen means distinguishable from zero, not a small gain. Pooled, not individual, calibration. Per-entity scores are unpublished so intervals cannot be recomputed here.",
      verify: ["+0.0242", "+0.0185", "not** a small gain", "pooled** calibration"],
    },
  ];
  const records = [];
  for (const d of defs) {
    const src = md(d.path);
    for (const needle of d.verify) assert(src.text.includes(needle), `fact ${d.id}: ${d.path} no longer contains ${JSON.stringify(needle)}`);
    records.push({
      record: "fact",
      source_path: src.path,
      source_sha256: src.sha256,
      study_id: d.id,
      target: d.target,
      cohort: "synthetic aggregate report",
      unit: d.unit,
      crps_sign: "not_applicable",
      scenario_class: "not_applicable",
      ci_scope: null,
      access: "public",
      id: d.id,
      stage: d.stage,
      title: d.title,
      statement: d.statement,
      limits: d.limits,
      verified_strings: d.verify,
    });
  }
  // Restricted M10-M12 aggregates: published only as the public aggregate summary.
  const prob = md("docs/studies/probabilistic-capacity-forecasting.md");
  const restricted = [
    { id: "M10-M12-gain", title: "Conditional scale H versus B1 (restricted raw evidence, aggregate report only)", statement: "Calibrated H versus B1 macro CRPS gain: 2.7485% on the first independent test and 2.9636% on the second.", verify: ["2.7485%", "2.9636%"] },
    { id: "M11-gain", title: "Group calibration and support (restricted raw evidence, aggregate report only)", statement: "H_GT versus H macro CRPS gain: 0.3582% and 0.3133%; H_GT nominal 90% pooled coverage 90.6901% and 90.7118%.", verify: ["0.3582%", "0.3133%", "90.6901%", "90.7118%"] },
    { id: "M12-shift", title: "Controlled shifts (restricted raw evidence, aggregate report only)", statement: "Under the adaptation-timescale shift, nominal 90% conditional coverage falls to 208/256 = 81.25% (parent A step-up/14 squat) and 203/256 = 79.296875% (parent B step-up/28 squat). Conditional reliability is not established.", verify: ["208/256 = 81.25%", "203/256 = 79.296875%", "Conditional reliability is not established"] },
  ];
  for (const r of restricted) {
    for (const needle of r.verify) assert(prob.text.includes(needle), `restricted aggregate ${r.id}: summary no longer contains ${JSON.stringify(needle)}`);
    records.push({
      record: "fact",
      source_path: prob.path,
      source_sha256: prob.sha256,
      study_id: r.id,
      target: "C",
      cohort: "private numerical audit, public aggregate summary only",
      unit: "kg or percent as stated",
      crps_sign: "lower_is_better",
      scenario_class: "not_applicable",
      ci_scope: null,
      access: "restricted_aggregate_only",
      id: r.id,
      stage: "M10-M12",
      title: r.title,
      statement: r.statement,
      limits: "Restricted raw evidence, aggregate report only: the underlying cohorts, scores and fitted parameters are not public and cannot be reproduced from this repository.",
      verified_strings: r.verify,
    });
  }
  return records;
}

// ---------------------------------------------------------------- assemble
export function buildEvidence() {
  const a = build616();
  const b = build639();
  const f = buildFrontier();
  const facts = buildFacts();
  const evidence = {
    schema_version: SCHEMA_VERSION,
    source_repository: SOURCE_REPOSITORY,
    source_revision: SOURCE_REVISION,
    conventions: {
      crps: CRPS_SIGN,
      contrast_sign: "first minus second; positive means the first-named model is worse (higher CRPS, NLL or RMSE).",
      targets: {
        C: "latent capacity, or its change (kg). Never directly observed; used by the public IID comparator panel and the reference world.",
        E: "expressed performance E = C(1 - g_S S), the transient, suppressed trace. Never directly observed.",
        Y: "observed noisy assessment Y = E(1 + eps), a distinct synthetic measurement target (kg).",
      },
      scenario_classes: "control = IID same-law evaluation; shift = frozen models evaluated unchanged under a named distribution shift (velocity noise or adaptation time-constant density). Six scenario sets come from two dependent parents.",
      ci_scope: { "RES-616": CI_616, "RES-639": CI_639 },
      macro: "Macro scores are the equal-weight mean of the squat, bench press and deadlift per-lift means, recomputed here and cross-checked against the stored shift tables.",
    },
    sources: [],
    studies: [a.study, b.study],
    scores: [...a.scoreRecords, ...b.scoreRecords],
    contrasts: [...a.contrastRecords, ...b.contrastRecords],
    shifts: [...a.shiftRecords, ...b.shiftRecords],
    group_summaries: a.groupSummaries,
    group_cells: a.cellRecords,
    scale_coverage: b.scaleRecords,
    pit: b.pitRecords,
    frontier: f.records,
    registry: f.registry,
    facts,
  };
  evidence.sources = [...sources.values()].sort((x, y) => (x.path < y.path ? -1 : 1));
  const parsed = Evidence.safeParse(evidence);
  if (!parsed.success) fail(`schema violation: ${JSON.stringify(parsed.error.issues.slice(0, 3))}`);
  return `${JSON.stringify(parsed.data, null, 1)}\n`;
}

function main() {
  const check = process.argv.includes("--check");
  let output;
  try {
    output = buildEvidence();
  } catch (error) {
    console.error(`evidence build FAILED: ${error instanceof Error ? error.message : error}`);
    process.exit(1);
  }
  if (check) {
    const current = existsSync(OUT_PATH) ? readFileSync(OUT_PATH, "utf8") : null;
    if (current !== output) {
      console.error("evidence build FAILED: data/evidence.v1.json is missing or differs from a fresh regeneration; run `npm run evidence`.");
      process.exit(1);
    }
    console.log("evidence OK: committed file matches regeneration byte for byte");
    return;
  }
  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, output);
  console.log(`wrote ${OUT_PATH} (${output.length} bytes)`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
