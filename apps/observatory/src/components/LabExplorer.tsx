"use client";

import { useMemo, useState } from "react";
import { DEFAULT_PARAMS, FUTURE_ASSESSMENT_DAYS, LAST_HISTORY_DAY, ORIGIN_DAY, PLAN_LABELS, capacityChange, simulate, type Plan, type SimParams } from "@/lib/sim";
import { Banner } from "./Ui";
import { DataTable } from "./DataTable";
import { LineChart } from "./charts";
import ui from "./ui.module.css";

interface SliderDef {
  key: "tauA" | "tauS" | "gainA" | "gainS" | "intensity" | "dose";
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}

const SLIDERS: SliderDef[] = [
  { key: "tauA", label: "Adaptation time constant tau_A", min: 14, max: 140, step: 1, unit: "days" },
  { key: "tauS", label: "Suppression time constant tau_S", min: 2, max: 30, step: 1, unit: "days" },
  { key: "gainA", label: "Adaptation gain g_A", min: 0.05, max: 0.5, step: 0.01, unit: "" },
  { key: "gainS", label: "Suppression gain g_S", min: 0.02, max: 0.4, step: 0.01, unit: "" },
  { key: "intensity", label: "Intensity i (relative load)", min: 0.4, max: 0.95, step: 0.01, unit: "" },
  { key: "dose", label: "Daily dose d (relative)", min: 0.2, max: 2, step: 0.05, unit: "" },
];

export function LabExplorer() {
  const [params, setParams] = useState<SimParams>(DEFAULT_PARAMS);
  const result = useMemo(() => simulate(params), [params]);
  const set = <K extends keyof SimParams>(k: K, v: SimParams[K]) => setParams((p) => ({ ...p, [k]: v }));
  const cPts = result.series.map((p) => [p.day, p.C] as [number, number]);
  const ePts = result.series.map((p) => [p.day, p.E] as [number, number]);
  const yHist = result.assessments.filter((a) => !a.future).map((a) => [a.day, a.y] as [number, number]);
  const yFut = result.assessments.filter((a) => a.future).map((a) => [a.day, a.y] as [number, number]);
  const futureRows = FUTURE_ASSESSMENT_DAYS.map((day) => {
    const point = result.series[day]!;
    const y = result.assessments.find((a) => a.day === day)!.y;
    return { day, dC: capacityChange(result, day), E: point.E, C: point.C, y };
  });
  const lastC = result.series[LAST_HISTORY_DAY - 1]!;
  return (
    <div data-testid="lab-explorer">
      <Banner title="Illustrative demonstration, not research evidence, not athlete data">
        <p>
          This panel runs the public capacity/expression law with parameters you choose. It is deterministic (fixed noise seed), uses no data, and is not fitted to or validated against anyone. It illustrates
          what the equations imply, nothing about real people.
        </p>
      </Banner>

      <div className={ui.grid2} style={{ marginTop: 24 }}>
        <div>
          <h2>Equations (public simulator)</h2>
          <div className={ui.eq} role="group" tabIndex={0} aria-label="Capacity and expression equations">
            <div>
              <var>s</var>
              <sub>t</sub> = <var>d</var>
              <sub>t</sub>
              <var>i</var>
              <sub>t</sub> / (<var>d</var>
              <sub>t</sub>
              <var>i</var>
              <sub>t</sub> + <var>s</var>
              <sub>ref</sub>), <var>s</var>
              <sub>ref</sub> = 0.6 (1 − <var>r</var>
              <sub>ref</sub>) / <var>r</var>
              <sub>ref</sub>
            </div>
            <div>
              <var>A</var>
              <sub>t</sub> = α<sub>A</sub> <var>A</var>
              <sub>t−1</sub> + (1 − α<sub>A</sub>) <var>s</var>
              <sub>t</sub>, <var>C</var>
              <sub>t</sub> = <var>B</var> (1 + <var>g</var>
              <sub>A</sub> <var>A</var>
              <sub>t</sub>)
            </div>
            <div>
              <var>S</var>
              <sub>t</sub> = α<sub>S</sub> <var>S</var>
              <sub>t−1</sub> + (1 − α<sub>S</sub>) <var>s</var>
              <sub>t</sub>, <var>E</var>
              <sub>t</sub> = <var>C</var>
              <sub>t</sub> (1 − <var>g</var>
              <sub>S</sub> <var>S</var>
              <sub>t</sub>)
            </div>
            <div>
              α<sub>A</sub> = exp(−1/τ<sub>A</sub>), α<sub>S</sub> = exp(−1/τ<sub>S</sub>), <var>Y</var>
              <sub>t</sub> = <var>E</var>
              <sub>t</sub> (1 + ε), ε ~ N(0, cv²)
            </div>
          </div>
          <ul className={ui.list} style={{ marginTop: 16 }}>
            <li>
              <strong>C</strong> is latent capacity and is never observed. <strong>E</strong> is expressed performance: capacity temporarily suppressed by recent stimulus. <strong>Y</strong> is the noisy
              assessment, the only one of the three a participant-visible record contains.
            </li>
            <li>
              Assessments are drawn on days 6, 13, …, 223 (history) and 237, 251, 279 (future). Load and velocity channels exist in the public simulator but are not drawn here; this demonstration shows
              the assessment channel only.
            </li>
            <li>
              Information boundary: history ends on day {LAST_HISTORY_DAY}; the forecast origin is day {ORIGIN_DAY}. The plan changes the dose from the origin onward.
            </li>
          </ul>
        </div>

        <form className={ui.controls} style={{ flexDirection: "column", alignItems: "stretch" }} aria-label="Simulation parameters" onSubmit={(e) => e.preventDefault()}>
          <fieldset className={ui.field} style={{ border: 0, padding: 0, margin: 0 }}>
            <legend>Plan from day {ORIGIN_DAY}</legend>
            <div className={ui.seg} role="group" aria-label="Plan">
              {(Object.keys(PLAN_LABELS) as Plan[]).map((p) => (
                <button key={p} type="button" aria-pressed={params.plan === p} onClick={() => set("plan", p)} data-testid={`plan-${p}`}>
                  {PLAN_LABELS[p]}
                </button>
              ))}
            </div>
          </fieldset>
          {SLIDERS.map((s) => (
            <div className={ui.field} key={s.key}>
              <label htmlFor={`sl-${s.key}`}>
                {s.label}: <output htmlFor={`sl-${s.key}`}>{params[s.key]}</output> {s.unit}
              </label>
              <input id={`sl-${s.key}`} type="range" min={s.min} max={s.max} step={s.step} value={params[s.key]} onChange={(e) => set(s.key, Number(e.target.value))} />
            </div>
          ))}
          <div>
            <button type="button" className={ui.btn} onClick={() => setParams(DEFAULT_PARAMS)} data-testid="lab-reset">
              Reset to defaults
            </button>
          </div>
        </form>
      </div>

      <div className={ui.grid2} style={{ marginTop: 32 }}>
        <LineChart
          title="C, E and Y over 280 days (illustrative)"
          subtitle="arbitrary kilogram-like units; baseline B = 150"
          series={[
            { id: "C", label: "C latent capacity", color: "var(--c-latent)", points: cPts },
            { id: "E", label: "E expressed performance", color: "var(--c-expressed)", points: ePts },
          ]}
          markers={[
            { id: "Yh", label: "Y noisy assessment (history)", color: "var(--c-observed)", points: yHist },
            { id: "Yf", label: "Y future assessment (under plan)", color: "var(--c-observed)", points: yFut, hollow: true },
          ]}
          vline={{ x: ORIGIN_DAY, label: "origin 224" }}
          xLabel="day"
          yLabel="performance (illustrative kg)"
          ariaLabel={`Line chart of illustrative latent capacity, expressed performance and noisy assessments over 280 days with the information boundary at day ${ORIGIN_DAY}.`}
          caption="Illustrative demonstration: deterministic output of the public law with the chosen parameters. Not research evidence."
          tableRows={{ head: ["Day", "C", "E"], body: result.series.filter((p) => p.day % 14 === 0 || p.day === 279).map((p) => [p.day, p.C.toFixed(2), p.E.toFixed(2)]) }}
        />
        <LineChart
          title="Internal states A and S"
          subtitle="adaptation (slow) and suppression (fast), 0 to 1"
          series={[
            { id: "A", label: "A adaptation state", color: "var(--c-latent)", points: result.series.map((p) => [p.day, p.A]) },
            { id: "S", label: "S suppression state", color: "var(--c-expressed)", points: result.series.map((p) => [p.day, p.S]) },
          ]}
          vline={{ x: ORIGIN_DAY, label: "origin 224" }}
          xLabel="day"
          yLabel="state"
          ariaLabel="Line chart of illustrative adaptation and suppression states over 280 days."
          caption="E = C(1 − g_S S): when S rises after a step-up, E is pulled below C although C keeps rising."
          tableRows={{ head: ["Day", "A", "S"], body: result.series.filter((p) => p.day % 14 === 0 || p.day === 279).map((p) => [p.day, p.A.toFixed(3), p.S.toFixed(3)]) }}
        />
      </div>

      <h2 style={{ marginTop: 32 }}>Future assessments under plan: {PLAN_LABELS[params.plan]}</h2>
      <DataTable
        caption={`Illustrative values; C at day ${LAST_HISTORY_DAY} is ${lastC.C.toFixed(2)}`}
        rows={futureRows}
        rowKey={(r) => String(r.day)}
        columns={[
          { key: "day", header: "Assessment day", numeric: true, value: (r) => r.day },
          { key: "dC", header: "ΔC = C − C223", numeric: true, value: (r) => r.dC, render: (r) => r.dC.toFixed(2) },
          { key: "E", header: "E", numeric: true, value: (r) => r.E, render: (r) => r.E.toFixed(2) },
          { key: "y", header: "Y (noisy)", numeric: true, value: (r) => r.y, render: (r) => r.y.toFixed(2) },
        ]}
      />
      <p style={{ marginTop: 12 }}>
        Under cessation the latent change ΔC is nonpositive, yet E and a noisy Y can still rise because suppression recovers. That is why the public RES-616 forecast target is the assessment Y and
        applies no truncation to it.
      </p>
    </div>
  );
}
