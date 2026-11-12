"use client";

import { useMemo, useState } from "react";
import type { Evidence } from "@/lib/evidence";
import { shortHash, sourceUrl } from "@/lib/source";
import { LIFT_LABELS, SCENARIO_LABELS, fmt, modelLabel, signed } from "@/lib/format";
import {
  STUDY_MODELS,
  STUDY_PRIMARY_CONTRAST,
  contrastsAvailable,
  groupOptions,
  groupsAvailable,
  selectContrasts,
  selectModelRows,
  selectShifts,
  studyIdPrefix,
  type ForecastSelection,
  type LiftKey,
  type Parent,
  type Scenario,
  type StudyKey,
} from "@/lib/forecast";
import { Banner, Chip, TargetChip } from "./Ui";
import { DataTable } from "./DataTable";
import { CoverageStrip, ForestPlot, HBarChart, LineChart, PitHistogram, colorFor, type StripLevel } from "./charts";
import ui from "./ui.module.css";

export type ForecastData = Pick<Evidence, "scores" | "contrasts" | "shifts" | "group_cells" | "scale_coverage" | "pit" | "studies">;

type TabId = "accuracy" | "likelihood" | "calibration" | "shifts";
const TABS: { id: TabId; label: string }[] = [
  { id: "accuracy", label: "Accuracy · CRPS" },
  { id: "likelihood", label: "Likelihood · NLL" },
  { id: "calibration", label: "Calibration" },
  { id: "shifts", label: "Shifts" },
];

function Tabs({ value, onChange }: { value: TabId; onChange: (t: TabId) => void }) {
  function onKey(e: React.KeyboardEvent, i: number) {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = TABS[(i + d + TABS.length) % TABS.length]!;
    onChange(next.id);
    document.getElementById(`tab-${next.id}`)?.focus();
  }
  return (
    <div role="tablist" aria-label="Result views" className={ui.tabs}>
      {TABS.map((t, i) => (
        <button
          key={t.id}
          id={`tab-${t.id}`}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          aria-controls={`tabpanel-${t.id}`}
          tabIndex={value === t.id ? 0 : -1}
          onClick={() => onChange(t.id)}
          onKeyDown={(e) => onKey(e, i)}
          data-testid={`tab-${t.id}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

const STUDY_TITLES: Record<StudyKey, string> = {
  "RES-616": "Ridge vs GRU (RES-616)",
  "RES-639": "Scale models: B_GROUP, B_MAG, H_HISTORY (RES-639)",
};

export function ForecastExplorer({ data }: { data: ForecastData }) {
  const evidence = data as Evidence;
  const [sel, setSel] = useState<ForecastSelection>({ study: "RES-616", parent: "TEST_A", scenario: "CONTROL", lift: "macro", group: "all" });
  const [tab, setTab] = useState<TabId>("accuracy");
  const update = (patch: Partial<ForecastSelection>) =>
    setSel((s) => {
      const next = { ...s, ...patch };
      if (!groupsAvailable(next.study)) next.group = "all";
      return next;
    });

  const groups = useMemo(() => groupOptions(evidence), [evidence]);
  const rows = useMemo(() => selectModelRows(evidence, sel), [evidence, sel]);
  const contrasts = useMemo(() => selectContrasts(evidence, sel, "crps"), [evidence, sel]);
  const nllContrasts = useMemo(() => selectContrasts(evidence, sel, "nll"), [evidence, sel]);
  const shifts = useMemo(() => selectShifts(evidence, sel), [evidence, sel]);
  const first = rows[0];
  const pooled = sel.group === "all";
  const scenarioIsShift = sel.scenario !== "CONTROL";
  const study = evidence.studies.find((s) => s.id === sel.study)!;
  const primaryContrast = STUDY_PRIMARY_CONTRAST[sel.study];

  const unitSuffix = pooled ? "pooled over 12 plan x horizon strata" : `${sel.group.replace("/", ", horizon ")} days`;
  const liftLabel = LIFT_LABELS[sel.lift];

  const crpsMax = Math.max(1, ...rows.map((r) => r.crps)) * 1.12;
  const nllMax = Math.max(1, ...rows.map((r) => r.nll)) * 1.12;
  const widthMax = Math.max(1, ...rows.map((r) => r.width90)) * 1.12;

  const levels: StripLevel[] = useMemo(() => {
    const defs: { nominal: number; pick: (r: (typeof rows)[number]) => number | null }[] = [
      { nominal: 0.5, pick: (r) => r.cov50 },
      { nominal: 0.8, pick: (r) => (Number.isNaN(r.cov80) ? null : r.cov80) },
      { nominal: 0.9, pick: (r) => r.cov90 },
    ];
    return defs
      .map((d) => ({
        nominal: d.nominal,
        points: rows.flatMap((r) => {
          const v = d.pick(r);
          return v === null ? [] : [{ id: r.model, label: modelLabel(r.model), value: v, color: colorFor(r.model) }];
        }),
      }))
      .filter((l) => l.points.length > 0);
  }, [rows]);

  const scaleSeries = useMemo(() => {
    if (sel.study !== "RES-639") return [];
    const prefix = studyIdPrefix("RES-639");
    return STUDY_MODELS["RES-639"].map((model) => {
      const pts: [number, number][] = [];
      for (let q = 1; q <= 5; q += 1) {
        const cells = evidence.scale_coverage.filter(
          (c) =>
            c.study_id.startsWith(prefix) && c.parent === sel.parent && c.scenario === sel.scenario && c.model === model && c.scale_quintile === q && (sel.lift === "macro" || c.lift === sel.lift),
        );
        if (cells.length) pts.push([q, cells.reduce((a, c) => a + c.cov90, 0) / cells.length]);
      }
      return { id: model, label: modelLabel(model), color: colorFor(model), points: pts };
    });
  }, [evidence, sel]);

  const pitSeries = useMemo(() => {
    if (sel.study !== "RES-639") return [];
    return STUDY_MODELS["RES-639"].map((model) => {
      const fractions = Array.from(
        { length: 10 },
        (_, i) => evidence.pit.find((p) => p.parent === sel.parent && p.scenario === sel.scenario && p.model === model && p.pit_bin === i + 1)?.fraction ?? 0,
      );
      return { model, label: modelLabel(model), fractions };
    });
  }, [evidence, sel]);

  const scoreSourcePath = first?.source_path ?? "";
  return (
    <section aria-labelledby="explorer-title" data-testid="forecast-explorer">
      <h2 id="explorer-title">Inspect the aggregate results</h2>
      <p className={ui.note}>
        CRPS (kg) and NLL (nats per observation) are <strong>lower-is-better</strong>. A paired difference is <strong>first model minus second</strong>: positive means the first-named model is worse.
        Compare paired differences, not bar heights.
      </p>

      <form className={ui.controls} aria-label="Forecast selectors" onSubmit={(e) => e.preventDefault()}>
        <fieldset className={ui.field} style={{ border: 0, padding: 0, margin: 0 }}>
          <legend>Model comparison</legend>
          <div className={ui.seg} role="group" aria-label="Model comparison">
            {(Object.keys(STUDY_TITLES) as StudyKey[]).map((k) => (
              <button key={k} type="button" aria-pressed={sel.study === k} onClick={() => update({ study: k })} data-testid={`study-${k}`}>
                {STUDY_TITLES[k]}
              </button>
            ))}
          </div>
        </fieldset>
        <div className={ui.field}>
          <label htmlFor="sel-parent">Test parent</label>
          <select id="sel-parent" value={sel.parent} onChange={(e) => update({ parent: e.target.value as Parent })}>
            <option value="TEST_A">TEST_A</option>
            <option value="TEST_B">TEST_B</option>
          </select>
        </div>
        <div className={ui.field}>
          <label htmlFor="sel-lift">Lift</label>
          <select id="sel-lift" value={sel.lift} onChange={(e) => update({ lift: e.target.value as LiftKey })}>
            {Object.entries(LIFT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className={ui.field}>
          <label htmlFor="sel-scenario">Scenario</label>
          <select id="sel-scenario" value={sel.scenario} onChange={(e) => update({ scenario: e.target.value as Scenario })}>
            {Object.entries(SCENARIO_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className={ui.field}>
          <label htmlFor="sel-group">Plan / horizon</label>
          <select id="sel-group" value={sel.group} disabled={!groupsAvailable(sel.study)} onChange={(e) => update({ group: e.target.value })}>
            <option value="all">All strata, pooled</option>
            {groups.map((g) => (
              <option key={g} value={g}>
                {g.replace("/", " / ")} days
              </option>
            ))}
          </select>
        </div>
      </form>
      {!groupsAvailable(sel.study) ? (
        <p className={ui.prov} role="status">
          Plan and horizon strata are available only for RES-616: the RES-639 aggregate tables are not stratified by plan or horizon.
        </p>
      ) : (
        <p className={ui.prov} role="status">
          Group tables hold arms M1_C, M2_C and M2_G only and report CRPS, NLL, 90% coverage and 90% width; other arms and levels are therefore absent when a stratum is chosen.
        </p>
      )}

      <div role="status" aria-live="polite" data-testid="selection-summary" style={{ margin: "16px 0" }}>
        <p style={{ marginBottom: 6 }}>
          <strong>{rows.length}</strong> model {rows.length === 1 ? "record" : "records"} · {sel.parent} · {SCENARIO_LABELS[sel.scenario]} · {liftLabel} · {unitSuffix}
        </p>
        <p style={{ marginBottom: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <TargetChip target="Y" />
          <Chip>{scenarioIsShift ? "shift scenario: frozen models, changed inputs" : "control: same-law evaluation"}</Chip>
          <Chip>unit: kg (CRPS), nats per observation (NLL)</Chip>
          <Chip>public aggregate evidence</Chip>
        </p>
        {first ? (
          <p className={ui.prov} style={{ margin: 0 }}>
            source <a href={sourceUrl(scoreSourcePath)}>{scoreSourcePath}</a> · sha256 <span title={first.source_sha256}>{shortHash(first.source_sha256)}</span> · study {first.study_id}
          </p>
        ) : null}
      </div>

      <Tabs value={tab} onChange={setTab} />

      <div role="tabpanel" id="tabpanel-accuracy" aria-labelledby="tab-accuracy" hidden={tab !== "accuracy"} className={ui.tabpanel}>
        <h3>Paired CRPS differences with 95% intervals</h3>
        {contrastsAvailable(sel) ? (
          <ForestPlot
            title={`Paired CRPS difference (kg), ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}`}
            rows={contrasts.map((c) => ({
              id: `${c.contrast}-${c.status}`,
              label: `${c.contrast.replace("-", " minus ")}${c.status === "PRIMARY" ? " (primary)" : ""}`,
              diff: c.diff,
              lo: c.ci_lo,
              hi: c.ci_hi,
              color: c.contrast === primaryContrast ? "var(--c-boundary)" : "var(--fg)",
            }))}
            unit="kg"
            ariaLabel={`Forest plot of paired CRPS differences in kilograms with 95 percent bootstrap intervals for ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}.`}
            caption={`Interval scope: ${contrasts[0]?.ci_scope ?? study.nonclaims[0]}. Positive means the first-named model is worse.`}
          />
        ) : (
          <Banner kind="info" title="No interval for this slice">
            <p>
              Paired bootstrap intervals are published only for the pooled macro score within a scenario. They do not exist for single lifts or for plan/horizon strata, so none is drawn or estimated
              here.
            </p>
          </Banner>
        )}

        <div className={ui.grid2} style={{ marginTop: 32 }}>
          <HBarChart
            title="CRPS by model"
            subtitle={`${liftLabel}, ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}`}
            rows={rows.map((r) => ({ id: r.model, label: modelLabel(r.model), value: r.crps, color: colorFor(r.model) }))}
            domain={[0, crpsMax]}
            unit="CRPS (kg)"
            ariaLabel={`Horizontal bar chart of CRPS in kilograms by model for ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}, ${liftLabel}. Lower is better. Values are in the data table below.`}
            caption={`Lower is better. ${pooled ? "Macro or per-lift mean over all strata." : "Mean of per-lift stratum cells."}`}
          />
        </div>
        <h3 style={{ marginTop: 40 }}>Model records</h3>
        <DataTable
          caption={`Records for ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}, ${liftLabel}, ${unitSuffix}`}
          rows={rows}
          rowKey={(r) => r.model}
          defaultSort={{ key: "crps", dir: "asc" }}
          columns={[
            { key: "model", header: "Model", value: (r) => modelLabel(r.model) },
            { key: "n", header: "n", numeric: true, value: (r) => r.n },
            { key: "crps", header: "CRPS (kg)", numeric: true, value: (r) => r.crps, render: (r) => fmt(r.crps) },
            { key: "nll", header: "NLL (nats)", numeric: true, value: (r) => r.nll, render: (r) => fmt(r.nll) },
            { key: "cov90", header: "90% cov.", numeric: true, value: (r) => r.cov90, render: (r) => fmt(r.cov90, 3) },
            { key: "w90", header: "90% width (kg)", numeric: true, value: (r) => r.width90, render: (r) => fmt(r.width90, 2) },
            { key: "src", header: "Source", value: (r) => r.source_path, render: (r) => <a href={sourceUrl(r.source_path)}>{r.source_path.split("/").slice(-1)[0]}</a> },
          ]}
        />
      </div>

      <div role="tabpanel" id="tabpanel-likelihood" aria-labelledby="tab-likelihood" hidden={tab !== "likelihood"} className={ui.tabpanel}>
        <div className={ui.grid2}>
          <HBarChart
            title="Negative log-likelihood by model"
            subtitle="nats per observation"
            rows={rows.map((r) => ({ id: r.model, label: modelLabel(r.model), value: r.nll, color: colorFor(r.model) }))}
            domain={[0, nllMax]}
            unit="NLL (nats)"
            ariaLabel={`Horizontal bar chart of negative log-likelihood by model for ${sel.parent}. Lower is better.`}
            caption="Lower is better. NLL and CRPS can rank models differently; neither is adjusted for multiplicity."
          />
        </div>
        {contrastsAvailable(sel) && nllContrasts.length ? (
          <div style={{ marginTop: 16 }}>
            <DataTable
              caption={`Paired NLL differences (nats), ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}`}
              rowKey={(c) => `${c.contrast}-${c.status}`}
              rows={nllContrasts}
              columns={[
                { key: "c", header: "Contrast (first minus second)", value: (c) => c.contrast.replace("-", " minus ") },
                { key: "d", header: "Difference", numeric: true, value: (c) => c.diff, render: (c) => signed(c.diff, 4) },
                { key: "lo", header: "95% lower", numeric: true, value: (c) => c.ci_lo, render: (c) => signed(c.ci_lo, 4) },
                { key: "hi", header: "95% upper", numeric: true, value: (c) => c.ci_hi, render: (c) => signed(c.ci_hi, 4) },
              ]}
            />
          </div>
        ) : null}
      </div>

      <div role="tabpanel" id="tabpanel-calibration" aria-labelledby="tab-calibration" hidden={tab !== "calibration"} className={ui.tabpanel}>
        <div className={ui.grid2}>
          <CoverageStrip
            title="Interval coverage against nominal level"
            subtitle="Observed share of simulated assessments inside the central interval"
            levels={levels}
            legend={rows.map((r) => ({ label: modelLabel(r.model), color: colorFor(r.model) }))}
            ariaLabel={`Dot chart of observed coverage for central 50, 80 and 90 percent intervals by model, against the nominal level, for ${sel.parent}. Values are in the data table below.`}
            caption="Red line: nominal level. Pooled coverage is not subgroup or individual calibration; see the stratum selector for 90% coverage by plan and horizon (RES-616)."
          />
          <HBarChart
            title="Central 90% interval width"
            subtitle="kg"
            rows={rows.map((r) => ({ id: r.model, label: modelLabel(r.model), value: r.width90, color: colorFor(r.model) }))}
            domain={[0, widthMax]}
            digits={2}
            unit="90% interval width (kg)"
            ariaLabel={`Horizontal bar chart of central 90 percent interval width in kilograms by model for ${sel.parent}.`}
            caption="Narrower is sharper only if coverage is maintained. Widths in RES-616 depend only on lift, plan and horizon, not on individual histories."
          />
        </div>
        {sel.study === "RES-639" ? (
          <div className={ui.grid2} style={{ marginTop: 40 }}>
            <LineChart
              title="90% coverage by predicted-scale quintile"
              subtitle={`${liftLabel}, ${sel.parent}, ${SCENARIO_LABELS[sel.scenario]}`}
              series={[
                ...scaleSeries,
                {
                  id: "nominal",
                  label: "nominal 90%",
                  color: "var(--c-boundary)",
                  dashed: true,
                  points: [
                    [1, 0.9],
                    [5, 0.9],
                  ],
                },
              ]}
              xLabel="predicted-scale quintile (within lift)"
              yLabel="observed coverage"
              ariaLabel="Line chart of observed 90 percent coverage by predicted-scale quintile for three scale models against the nominal 0.90 level."
              caption="Coverage by lift-specific predicted-scale quintile across groups only. Pooled agreement is not individual calibration."
              tableRows={{
                head: ["Quintile", ...scaleSeries.map((s) => s.label)],
                body: [1, 2, 3, 4, 5].map((q) => [q, ...scaleSeries.map((s) => (s.points.find((p) => p[0] === q)?.[1] ?? Number.NaN).toFixed(3))]),
              }}
            />
            <PitHistogram
              title="PIT histogram (ten bins)"
              series={pitSeries}
              ariaLabel="Grouped bar chart of probability integral transform fractions in ten bins for three scale models, compared with the uniform value 0.10."
              caption="Uniform (0.10 per bin) indicates a calibrated predictive distribution on this pooled sample. PIT values were checked only against the stored point estimates."
            />
          </div>
        ) : null}
      </div>

      <div role="tabpanel" id="tabpanel-shifts" aria-labelledby="tab-shifts" hidden={tab !== "shifts"} className={ui.tabpanel}>
        <h3>Control versus shift: absolute degradation</h3>
        <p>
          Frozen models were evaluated unchanged on two named shifts. Ranking and absolute degradation are different questions. The six scenario sets come from two dependent parents; no general
          robustness claim follows.
        </p>
        <DataTable
          caption={`Macro CRPS by scenario, ${sel.parent}, ${sel.study}`}
          rows={shifts}
          rowKey={(s) => `${s.model}-${s.scenario}`}
          columns={[
            { key: "m", header: "Model", value: (s) => modelLabel(s.model) },
            { key: "sc", header: "Scenario", value: (s) => SCENARIO_LABELS[s.scenario] ?? s.scenario },
            { key: "cl", header: "Class", value: (s) => s.scenario_class },
            { key: "crps", header: "CRPS (kg)", numeric: true, value: (s) => s.crps_kg, render: (s) => fmt(s.crps_kg) },
            { key: "d", header: "vs control (kg)", numeric: true, value: (s) => s.d_crps_vs_control_kg, render: (s) => signed(s.d_crps_vs_control_kg, 4) },
            { key: "pct", header: "vs control (%)", numeric: true, value: (s) => s.d_crps_pct, render: (s) => signed(s.d_crps_pct, 2) },
            { key: "cov", header: "90% cov.", numeric: true, value: (s) => s.cov90, render: (s) => fmt(s.cov90, 3) },
            { key: "rank", header: "CRPS rank", numeric: true, value: (s) => s.rank_by_crps },
          ]}
        />
      </div>
    </section>
  );
}
