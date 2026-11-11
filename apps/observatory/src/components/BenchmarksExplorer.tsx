"use client";

import { useMemo, useState } from "react";
import type { FrontierRecord, RegistryRecord } from "@/lib/evidence";
import { sourceUrl } from "@/lib/evidence";
import { LIFT_LABELS, fmt } from "@/lib/format";
import { Banner, Chip, Provenance, TargetChip } from "./Ui";
import { DataTable } from "./DataTable";
import { HBarChart } from "./charts";
import ui from "./ui.module.css";

type Authority = "all" | "HISTORICAL_PROJECTION" | "PUBLIC_NATIVE";
type Lift = "squat" | "bench_press" | "deadlift";
const LIFTS: Lift[] = ["squat", "bench_press", "deadlift"];
type Family = "all" | "NEW_STANDARDIZED_COMPARATOR" | "RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT";

const METHOD_LABELS: Record<string, string> = {
  context_mean: "Context mean",
  ridge: "Ridge",
  histogram_boosted_stumps: "Histogram boosted stumps",
  compact_neural: "Compact neural network",
  mechanistic_midpoint: "Mechanistic midpoint",
  mechanistic_ridge_residual: "Mechanistic + Ridge residual",
  "public-native-temporal-expert": "Temporal expert (GRU)",
};

function identityLabel(r: FrontierRecord): string {
  return `${METHOD_LABELS[r.method] ?? r.method} · ${r.seed === "ensemble" ? "ensemble" : `seed ${r.seed.slice(-3)}`}`;
}

export function RegistryExplorer({ registry }: { registry: RegistryRecord[] }) {
  const [authority, setAuthority] = useState<Authority>("all");
  const rows = useMemo(() => registry.filter((r) => authority === "all" || r.identity_authority === authority), [registry, authority]);
  return (
    <div>
      <div className={ui.controls}>
        <div className={ui.field}>
          <label htmlFor="reg-authority">Identity authority</label>
          <select id="reg-authority" value={authority} onChange={(e) => setAuthority(e.target.value as Authority)}>
            <option value="all">All nine entries</option>
            <option value="HISTORICAL_PROJECTION">Historical projections (8)</option>
            <option value="PUBLIC_NATIVE">Public-native variant (1)</option>
          </select>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <DataTable
          caption="Benchmark registry (artifacts/registries/benchmark-registry.json)"
          rows={rows}
          rowKey={(r) => r.slug}
          columns={[
            { key: "n", header: "Scientific formulation", value: (r) => r.display_name, render: (r) => <a href={sourceUrl(r.docs_path)}>{r.display_name}</a> },
            { key: "a", header: "Identity authority", value: (r) => r.identity_authority },
            { key: "h", header: "Historical state", value: (r) => r.historical_specimen_status },
            { key: "q", header: "Qualification", value: (r) => r.historical_qualification_state },
            { key: "i", header: "Public implementation", value: (r) => r.public_implementation_status },
            { key: "t", header: "Target ontology", value: (r) => r.target_ontology },
          ]}
        />
      </div>
      {rows[0] ? <Provenance path={rows[0].source_path} sha={rows[0].source_sha256} /> : null}
    </div>
  );
}

export function FrontierExplorer({ frontier }: { frontier: FrontierRecord[] }) {
  const [lift, setLift] = useState<Lift>("squat");
  const [family, setFamily] = useState<Family>("all");
  const rows = useMemo(
    () => frontier.filter((r) => r.lift === lift && (family === "all" || r.classification === family)).sort((a, b) => a.rmse_kg - b.rmse_kg),
    [frontier, lift, family],
  );
  const max = Math.max(1, ...rows.map((r) => r.rmse_kg)) * 1.12;
  const first = rows[0];
  return (
    <div data-testid="frontier-explorer">
      <div className={ui.controls}>
        <div className={ui.field}>
          <label htmlFor="fr-lift">Target lift (one target at a time)</label>
          <select id="fr-lift" value={lift} onChange={(e) => setLift(e.target.value as Lift)}>
            {LIFTS.map((k) => (
              <option key={k} value={k}>
                {LIFT_LABELS[k]}: capacity change
              </option>
            ))}
          </select>
        </div>
        <div className={ui.field}>
          <label htmlFor="fr-family">Candidate class</label>
          <select id="fr-family" value={family} onChange={(e) => setFamily(e.target.value as Family)}>
            <option value="all">All 22 identities</option>
            <option value="NEW_STANDARDIZED_COMPARATOR">New standardized comparators (18)</option>
            <option value="RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT">Immutable temporal expert (4)</option>
          </select>
        </div>
      </div>
      <p role="status" aria-live="polite" style={{ margin: "12px 0" }} data-testid="frontier-summary">
        <strong>{rows.length}</strong> fit or ensemble identities · {LIFT_LABELS[lift]} · <TargetChip target="C" /> unit kg · public IID realization
      </p>
      <HBarChart
        title={`Point RMSE for ${(LIFT_LABELS[lift] ?? lift).toLowerCase()} capacity change (kg)`}
        subtitle="Sorted within this single target; descriptive, not a leaderboard"
        rows={rows.map((r) => ({
          id: r.fitted_instance_id,
          label: identityLabel(r),
          value: r.rmse_kg,
          color: r.classification === "NEW_STANDARDIZED_COMPARATOR" ? "var(--c-latent)" : "var(--c-expressed)",
        }))}
        domain={[0, max]}
        unit="RMSE (kg)"
        ariaLabel={`Horizontal bar chart of point RMSE in kilograms for ${rows.length} model identities on ${LIFT_LABELS[lift]} capacity change.`}
        caption="Lower is better. Candidate representations, budgets, hardware and information privileges differ, so this is not an attribution study or a universal ranking. Different lifts are different targets and are never pooled."
      />
      <div style={{ marginTop: 16 }}>
        <DataTable
          caption={`Comparator panel, ${LIFT_LABELS[lift]} capacity change`}
          rows={rows}
          rowKey={(r) => r.fitted_instance_id}
          defaultSort={{ key: "rmse", dir: "asc" }}
          columns={[
            { key: "id", header: "Identity", value: (r) => identityLabel(r) },
            { key: "cls", header: "Class", value: (r) => (r.classification === "NEW_STANDARDIZED_COMPARATOR" ? "standardized comparator" : "immutable expert") },
            { key: "rmse", header: "RMSE (kg)", numeric: true, value: (r) => r.rmse_kg, render: (r) => fmt(r.rmse_kg, 3) },
            { key: "mae", header: "MAE (kg)", numeric: true, value: (r) => r.mae_kg, render: (r) => fmt(r.mae_kg, 3) },
            { key: "r2", header: "R²", numeric: true, value: (r) => r.r2, render: (r) => fmt(r.r2, 3) },
            { key: "p", header: "Parameters", numeric: true, value: (r) => r.parameter_count },
          ]}
        />
      </div>
      {first ? <Provenance path={first.source_path} sha={first.source_sha256} studyId={first.study_id} /> : null}
    </div>
  );
}

export function WorldsSeparated({ historical, publicNative }: { historical: number; publicNative: number }) {
  return (
    <div className={ui.grid3}>
      <div className={ui.card}>
        <h3>Historical worlds</h3>
        <p>
          <Chip>{historical} projections</Chip> No recovered public quantitative results. Cross-version numeric comparisons (36) are{" "}
          <code>REJECTED_FOR_NUMERICAL_COMPARISON</code>. They are listed, not scored.
        </p>
      </div>
      <div className={ui.card}>
        <h3>Public-native IID world</h3>
        <p>
          <TargetChip target="C" /> {publicNative} variant, 22 saved fit or ensemble identities, point error in kg for latent capacity change. Explored below, one lift at a time.
        </p>
      </div>
      <div className={ui.card}>
        <h3>Observed-assessment world</h3>
        <p>
          <TargetChip target="Y" /> RES-616 and RES-639 forecast the noisy future assessment with proper scores (CRPS, NLL). Different target, task and metric: see the{" "}
          <a href="/forecast">forecasting lab</a>.
        </p>
      </div>
    </div>
  );
}

export function RankingNotice() {
  return (
    <Banner title="No cross-target or cross-world ranking">
      <p>
        Latent capacity change (C), expressed performance (E) and the observed noisy assessment (Y) answer different questions, and the historical and public-native worlds have different dataset
        identities. A smaller number in one table is never comparable with a number in another. There is no universal scalar leaderboard.
      </p>
    </Banner>
  );
}
