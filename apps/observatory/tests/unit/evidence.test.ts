// @vitest-environment node
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { Evidence } from "../../scripts/evidence-schema.mjs";
import { buildEvidence, OUT_PATH, REPO_ROOT } from "../../scripts/build-evidence.mjs";
import { evidence } from "@/lib/evidence";

const committed = readFileSync(OUT_PATH, "utf8");

describe("evidence file", () => {
  it("validates against the versioned schema", () => {
    expect(Evidence.safeParse(JSON.parse(committed)).success).toBe(true);
    expect(evidence.schema_version).toBe("psr-observatory-evidence/1.0.0");
    expect(evidence.source_revision.startsWith("41191d6")).toBe(true);
  });

  it("regenerates to identical bytes", () => {
    expect(buildEvidence()).toBe(committed);
  });

  it("binds every record to a hashed public source whose hash matches the file on disk", () => {
    const known = new Map(evidence.sources.map((s) => [s.path, s.sha256]));
    for (const source of evidence.sources) {
      const actual = createHash("sha256").update(readFileSync(join(REPO_ROOT, source.path))).digest("hex");
      expect(actual, source.path).toBe(source.sha256);
    }
    const all = [
      ...evidence.scores, ...evidence.contrasts, ...evidence.shifts, ...evidence.group_summaries, ...evidence.group_cells,
      ...evidence.scale_coverage, ...evidence.pit, ...evidence.frontier, ...evidence.registry, ...evidence.facts,
    ];
    expect(all.length).toBeGreaterThan(1500);
    for (const r of all) {
      expect(known.get(r.source_path), r.source_path).toBe(r.source_sha256);
      expect(r.study_id.length).toBeGreaterThan(0);
      expect(r.unit.length).toBeGreaterThan(0);
    }
  });

  it("contains no paper, manuscript or private artifact path", () => {
    for (const s of evidence.sources) {
      expect(s.path).not.toMatch(/\.(pdf|tex|zip)$/i);
      expect(s.path).not.toMatch(/paper|manuscript|declaration/i);
      expect(s.path).toMatch(/^(results|docs|artifacts)\//);
    }
    expect(committed).not.toMatch(/powerlifting-state-research-paper/);
  });
});

describe("scientific labelling and target separation", () => {
  it("keeps observed-assessment scores on target Y and comparator-panel records on latent target C", () => {
    expect(evidence.scores.every((r) => r.target === "Y" && r.unit === "kg")).toBe(true);
    expect(evidence.contrasts.every((r) => r.target === "Y")).toBe(true);
    expect(evidence.frontier.every((r) => r.target === "C")).toBe(true);
    const yStudies = new Set(evidence.scores.map((r) => r.study_id));
    const cStudies = new Set(evidence.frontier.map((r) => r.study_id));
    for (const id of yStudies) expect(cStudies.has(id)).toBe(false);
  });

  it("documents the CRPS sign convention and CI scope on every contrast", () => {
    expect(evidence.conventions.crps).toMatch(/lower-is-better/);
    expect(evidence.conventions.contrast_sign).toMatch(/positive means the first-named model is worse/);
    for (const c of evidence.contrasts) {
      expect(c.ci_scope).toMatch(/bootstrap/);
      expect(c.sign_note).toMatch(/positive means the first model is worse/);
      expect(c.ci_lo).toBeLessThanOrEqual(c.diff);
      expect(c.ci_hi).toBeGreaterThanOrEqual(c.diff);
    }
  });

  it("separates control from shift scenarios", () => {
    for (const r of evidence.scores) {
      expect(r.scenario_class).toBe(r.scenario === "CONTROL" ? "control" : "shift");
    }
    expect(new Set(evidence.scores.map((r) => r.scenario)).size).toBe(3);
  });

  it("flags restricted M10-M12 aggregates and nothing else as restricted", () => {
    const restricted = evidence.facts.filter((f) => f.access === "restricted_aggregate_only");
    expect(restricted.map((f) => f.stage)).toEqual(["M10-M12", "M10-M12", "M10-M12"]);
    for (const f of restricted) expect(f.limits).toMatch(/Restricted raw evidence, aggregate report only/);
    const others = [...evidence.scores, ...evidence.contrasts, ...evidence.frontier, ...evidence.registry];
    expect(others.every((r) => r.access === "public")).toBe(true);
  });

  it("has nine registry entries (one public-native) and 22 comparator identities across three latent-change targets", () => {
    expect(evidence.registry).toHaveLength(9);
    expect(evidence.registry.filter((r) => r.identity_authority === "PUBLIC_NATIVE")).toHaveLength(1);
    expect(new Set(evidence.frontier.map((r) => r.fitted_instance_id)).size).toBe(22);
    expect(evidence.frontier).toHaveLength(66);
  });
});

describe("documented values are reproduced from the sources", () => {
  const macro = (study: string, parent: string, model: string) =>
    evidence.scores.find((r) => r.study_id.includes(study) && r.parent === parent && r.scenario === "CONTROL" && r.model === model && r.lift === "macro")!;
  const round4 = (x: number) => Math.round(x * 1e4) / 1e4;

  it("RES-616 control macro CRPS: Ridge 6.6378/6.6281, GRU 6.7481/6.7197", () => {
    expect(round4(macro("observable", "TEST_A", "M1_C").crps)).toBe(6.6378);
    expect(round4(macro("observable", "TEST_B", "M1_C").crps)).toBe(6.6281);
    expect(round4(macro("observable", "TEST_A", "M2_C").crps)).toBe(6.7481);
    expect(round4(macro("observable", "TEST_B", "M2_C").crps)).toBe(6.7197);
  });

  it("RES-616 primary paired difference is positive (GRU worse) with an interval above zero", () => {
    const rows = evidence.contrasts.filter((c) => c.contrast === "M2_C-M1_C" && c.status === "PRIMARY" && c.scenario === "CONTROL");
    expect(rows).toHaveLength(2);
    for (const r of rows) {
      expect(r.diff).toBeGreaterThan(0.09);
      expect(r.ci_lo).toBeGreaterThan(0);
    }
  });

  it("RES-639 H_HISTORY minus B_MAG is +0.024194 / +0.018465 kg with intervals above zero", () => {
    const get = (parent: string) =>
      evidence.contrasts.find((c) => c.contrast === "H_HISTORY-B_MAG" && c.status === "PRIMARY" && c.parent === parent && c.metric === "crps")!;
    expect(get("TEST_A").diff).toBeCloseTo(0.024194, 6);
    expect(get("TEST_B").diff).toBeCloseTo(0.018465, 6);
    expect(get("TEST_A").ci_lo).toBeGreaterThan(0);
    expect(get("TEST_B").ci_lo).toBeGreaterThan(0);
  });

  it("G2 fact keeps the unsupported-not-impossible framing", () => {
    const g2 = evidence.facts.find((f) => f.id === "G2")!;
    expect(g2.statement).toMatch(/FULL_G2_IDENTIFICATION_UNSUPPORTED/);
    expect(g2.limits).toMatch(/not a proof of impossibility/);
  });
});

describe("the build fails on missing or contradicted sources", () => {
  const sandboxes: string[] = [];
  function sandbox(): string {
    const root = mkdtempSync(join(tmpdir(), "psr-evidence-"));
    sandboxes.push(root);
    for (const s of evidence.sources) {
      const target = join(root, s.path);
      mkdirSync(dirname(target), { recursive: true });
      cpSync(join(REPO_ROOT, s.path), target);
    }
    return root;
  }
  function run(root: string) {
    return spawnSync(process.execPath, [resolve(__dirname, "../../scripts/build-evidence.mjs"), "--check"], {
      env: { ...process.env, PSR_REPO_ROOT: root },
      encoding: "utf8",
    });
  }
  afterAll(() => sandboxes.forEach((d) => rmSync(d, { recursive: true, force: true })));

  it("passes on an unmodified copy", () => {
    const r = run(sandbox());
    expect(r.stderr).toBe("");
    expect(r.status).toBe(0);
  });

  it("fails when a source file is missing", () => {
    const root = sandbox();
    rmSync(join(root, "results/studies/observable_strength_forecasting/full/scores.csv"));
    const r = run(root);
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/missing source/);
  });

  it("fails when a score is altered so that documented numbers or manifest hashes contradict", () => {
    const root = sandbox();
    const file = join(root, "results/studies/observable_strength_forecasting/full/scores.csv");
    writeFileSync(file, readFileSync(file, "utf8").replace("TEST_A,CONTROL,M1_C,squat,3072,", "TEST_A,CONTROL,M1_C,squat,3072,9"));
    const r = run(root);
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/evidence build FAILED/);
  });

  it("fails when a study document no longer states the verified number", () => {
    const root = sandbox();
    const file = join(root, "docs/studies/g2-identifiability-decision.md");
    writeFileSync(file, readFileSync(file, "utf8").replaceAll("FULL_G2_IDENTIFICATION_UNSUPPORTED", "FULL_G2_IDENTIFICATION_SUPPORTED"));
    const r = run(root);
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/G2/);
  });

  it("fails when the regenerated file would differ from the committed one", () => {
    const root = sandbox();
    const file = join(root, "docs/studies/index.md");
    writeFileSync(file, `${readFileSync(file, "utf8")}\nextra line\n`);
    const r = run(root);
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/differs from a fresh regeneration/);
  });
});
