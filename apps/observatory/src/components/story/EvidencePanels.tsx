"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Interval, ParentKey, Src, StoryEvidence } from "@/lib/story-evidence";
import styles from "./panels.module.css";

const PARENTS: ParentKey[] = ["TEST_A", "TEST_B"];

const sgn = (v: number, d = 4) => `${v < 0 ? "−" : "+"}${Math.abs(v).toFixed(d)}`;
const ivl = (i: Interval, d = 4) => `${sgn(i.diff, d)} kg [${sgn(i.lo, d)}, ${sgn(i.hi, d)}]`;

function useWidth(fallback = 520): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setW(Math.max(260, Math.floor(el.getBoundingClientRect().width)));
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function ticks(lo: number, hi: number, n: number): number[] {
  const raw = (hi - lo) / n;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

function SourceLine({ evidence, items }: { evidence: StoryEvidence; items: { label: string; src: Src }[] }) {
  const base = `https://github.com/${evidence.repository}/blob/${evidence.revision}/`;
  return (
    <p className={styles.source}>
      {items.map((it, i) => (
        <span key={it.label}>
          {i > 0 ? " · " : null}
          {it.label} <a href={base + it.src.path}>{it.src.path.split("/").slice(-2).join("/")}</a>{" "}
          <span title={it.src.sha256}>sha256 {it.src.sha256.slice(0, 8)}</span>
        </span>
      ))}
    </p>
  );
}

function ParentSwitch({ value, onChange, label }: { value: ParentKey; onChange: (p: ParentKey) => void; label: string }) {
  return (
    <div className={styles.switch} role="group" aria-label={label}>
      {PARENTS.map((p) => (
        <button key={p} type="button" aria-pressed={value === p} onClick={() => onChange(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}

function Panel({
  id,
  slot,
  badge,
  title,
  controls,
  children,
  caption,
  method,
  table,
  readout,
}: {
  id: string;
  slot: string;
  badge: string;
  title: string;
  controls?: ReactNode;
  children: ReactNode;
  caption: ReactNode;
  method: ReactNode;
  table: { caption: string; head: string[]; rows: (string | number)[][] };
  readout?: string;
}) {
  return (
    <figure className={styles.panel} data-panel={id} data-slot={slot} aria-labelledby={`${slot}-${id}-title`}>
      <div className={styles.head}>
        <p className={styles.badge}>
          <span aria-hidden="true" className={styles.badgeDot} />
          {badge}
        </p>
        <p id={`${slot}-${id}-title`} className={styles.title}>
          {title}
        </p>
      </div>
      {controls ? <div className={styles.controls}>{controls}</div> : null}
      {children}
      <p className={styles.readout} aria-live="polite" data-testid={`${slot}-${id}-readout`}>
        {readout ?? " "}
      </p>
      <figcaption className={styles.caption}>{caption}</figcaption>
      <details className={styles.data}>
        <summary>Method, source and data</summary>
        <div className={styles.method}>{method}</div>
        <div className={styles.tableWrap}>
          <table>
            <caption>{table.caption}</caption>
            <thead>
              <tr>
                {table.head.map((h) => (
                  <th key={h} scope="col">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (j === 0 ? <th key={j} scope="row">{c}</th> : <td key={j}>{c}</td>))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

/* ---------------------------------------------------------------- Act III: G2 identification */

export function G2Panel({ evidence, slot }: { evidence: StoryEvidence; slot: string }) {
  const g = evidence.g2;
  const [noise, setNoise] = useState<"native" | "doubled">("native");
  const [k, n] = noise === "native" ? g.convergedNative : g.convergedDoubled;
  const cols = 16;
  const rows = Math.ceil(n / cols);
  const [ref, w] = useWidth();
  const cell = Math.min(18, Math.floor((w - 2) / cols));
  const size = cell * cols;
  return (
    <Panel
      id="g2"
      slot={slot}
      badge="Evidence · G2 · public aggregate report"
      title={`${k} of ${n} full-model fits converged`}
      controls={
        <div className={styles.switch} role="group" aria-label="Observation noise level">
          {(["native", "doubled"] as const).map((v) => (
            <button key={v} type="button" aria-pressed={noise === v} onClick={() => setNoise(v)}>
              {v === "native" ? "Native noise" : "Doubled noise"}
            </button>
          ))}
        </div>
      }
      readout={`${noise === "native" ? "Native" : "Doubled"} observation noise: ${k} of ${n} maximum-likelihood starts converged (${((100 * k) / n).toFixed(1)}%).`}
      caption={
        <>
          <strong className={styles.verdict}>{g.disposition}</strong> on current evidence. Not a proof of impossibility.
        </>
      }
      method={
        <>
          Each square is one full maximum-likelihood start for the 16-parameter model, filled if it converged. Separately, {g.stationary[0]} of {g.stationary[1]} RES-592 starts were
          independently stationary; local rank is {g.localRank[0]}/{g.localRank[1]} but condition numbers are large. {g.limits}
          <SourceLine evidence={evidence} items={[{ label: "source", src: g.source }]} />
        </>
      }
      table={{
        caption: "G2 numerical admission counts (aggregate report)",
        head: ["Quantity", "Count", "Of"],
        rows: [
          ["Converged full-MLE starts, native noise", g.convergedNative[0], g.convergedNative[1]],
          ["Converged full-MLE starts, doubled noise", g.convergedDoubled[0], g.convergedDoubled[1]],
          ["Independently stationary RES-592 starts", g.stationary[0], g.stationary[1]],
          ["Local Jacobian rank", g.localRank[0], g.localRank[1]],
        ],
      }}
    >
      <div ref={ref} className={styles.plot}>
        <svg width={size} height={rows * cell} viewBox={`0 0 ${size} ${rows * cell}`} role="img" aria-label={`Unit chart: ${k} of ${n} starts converged.`} data-testid="g2-waffle">
          {Array.from({ length: n }, (_, i) => {
            const x = (i % cols) * cell;
            const y = Math.floor(i / cols) * cell;
            const on = i < k;
            return <rect key={i} x={x + 1.5} y={y + 1.5} width={cell - 3} height={cell - 3} rx={2} className={on ? styles.cellOn : styles.cellOff} />;
          })}
        </svg>
      </div>
    </Panel>
  );
}

/* ---------------------------------------------------------------- Act IV: Ridge versus GRU */

function IntervalRow({
  y,
  x,
  iv,
  label,
  emphasis,
  onFocus,
  name,
}: {
  y: number;
  x: (v: number) => number;
  iv: Interval;
  label: string;
  emphasis: boolean;
  onFocus: () => void;
  name: string;
}) {
  return (
    <g
      tabIndex={0}
      role="img"
      aria-label={`${name}: ${ivl(iv)}`}
      className={[styles.iv, emphasis ? styles.ivOn : ""].join(" ")}
      onPointerEnter={onFocus}
      onFocus={onFocus}
    >
      <rect x={0} y={y - 16} width={x(iv.hi) + 40} height={32} className={styles.hit} />
      <text x={8} y={y + 4} className={styles.rowLabel}>
        {label}
      </text>
      <line x1={x(iv.lo)} x2={x(iv.hi)} y1={y} y2={y} className={styles.ivLine} />
      <line x1={x(iv.lo)} x2={x(iv.lo)} y1={y - 6} y2={y + 6} className={styles.ivLine} />
      <line x1={x(iv.hi)} x2={x(iv.hi)} y1={y - 6} y2={y + 6} className={styles.ivLine} />
      <circle cx={x(iv.diff)} cy={y} r={5.5} className={styles.ivDot} />
    </g>
  );
}

export function RidgePanel({ evidence, slot }: { evidence: StoryEvidence; slot: string }) {
  const r = evidence.ridge;
  const [parent, setParent] = useState<ParentKey>("TEST_A");
  const [hover, setHover] = useState<string | null>(null);
  const [ref, w] = useWidth();
  const scores = r.parents[parent].scores;
  // Absolute CRPS strip (positions, so the axis need not start at zero; values are labelled).
  const left = 96;
  const right = 24;
  const lo = 6;
  const hi = 9.5;
  const xs = (v: number) => left + ((v - lo) / (hi - lo)) * (w - left - right);
  const dLo = Math.min(0, ...PARENTS.map((p) => r.parents[p].diff.lo)) - 0.02;
  const dHi = Math.max(...PARENTS.map((p) => r.parents[p].diff.hi)) + 0.02;
  const xd = (v: number) => left + ((v - dLo) / (dHi - dLo)) * (w - left - right);
  const d = r.parents[parent].diff;
  return (
    <Panel
      id="ridge"
      slot={slot}
      badge="Evidence · RES-616 · public aggregate"
      title="The GRU forecast the next assessment slightly worse than Ridge"
      controls={<ParentSwitch value={parent} onChange={setParent} label="Independent test parent" />}
      readout={hover ?? `${parent}: GRU minus Ridge ${ivl(d)}, ${sgn(d.relPct, 2)}% relative. Positive means the GRU is worse.`}
      caption={<>Macro CRPS (kg) on the observed synthetic assessment Y, control scenario. Lower is better.</>}
      method={
        <>
          Interval: {r.ciScope} Disposition <code>{r.disposition}</code>.
          <SourceLine
            evidence={evidence}
            items={[
              { label: "scores", src: r.scoreSource },
              { label: "contrasts", src: r.contrastSource },
            ]}
          />
        </>
      }
      table={{
        caption: "RES-616 control macro CRPS (kg) and paired GRU minus Ridge difference",
        head: ["Parent", "Persistence", "Ridge", "GRU", "GRU − Ridge", "95% lower", "95% upper"],
        rows: PARENTS.map((p) => {
          const s = r.parents[p].scores;
          const di = r.parents[p].diff;
          return [p, ...s.map((x) => x.crps.toFixed(4)), sgn(di.diff), sgn(di.lo), sgn(di.hi)];
        }),
      }}
    >
      <div ref={ref} className={styles.plot}>
        <p className={styles.plotLabel}>CRPS, kg · {parent}</p>
        <svg width={w} height={92} viewBox={`0 0 ${w} 92`} aria-hidden="true">
          {ticks(lo, hi, 4).map((t) => (
            <g key={t}>
              <line x1={xs(t)} x2={xs(t)} y1={6} y2={70} className={styles.grid} />
              <text x={xs(t)} y={86} className={styles.tick} textAnchor="middle">
                {t}
              </text>
            </g>
          ))}
          {scores.map((s, i) => {
            const y = 14 + i * 24;
            return (
              <g key={s.model} onPointerEnter={() => setHover(`${parent} ${s.label}: CRPS ${s.crps.toFixed(4)} kg`)}>
                <rect x={0} y={y - 12} width={w} height={24} className={styles.hit} />
                <text x={8} y={y + 4} className={styles.rowLabel}>
                  {s.label}
                </text>
                <line x1={xs(lo)} x2={xs(s.crps)} y1={y} y2={y} className={styles.lollipop} />
                <circle cx={xs(s.crps)} cy={y} r={5} className={s.model === "M2_C" ? styles.dotE : s.model === "M1_C" ? styles.dotC : styles.dotN} />
                <text x={xs(s.crps) + 10} y={y + 4} className={styles.value}>
                  {s.crps.toFixed(3)}
                </text>
              </g>
            );
          })}
        </svg>
        <p className={styles.plotLabel}>Paired difference, GRU − Ridge, kg, with 95% interval</p>
        <svg width={w} height={110} viewBox={`0 0 ${w} 110`} aria-hidden="false" role="group" aria-label="Paired differences for both test parents">
          {ticks(dLo, dHi, 4).map((t) => (
            <g key={t}>
              <line x1={xd(t)} x2={xd(t)} y1={6} y2={78} className={styles.grid} />
              <text x={xd(t)} y={94} className={styles.tick} textAnchor="middle">
                {t === 0 ? "0" : sgn(t, 2)}
              </text>
            </g>
          ))}
          <line x1={xd(0)} x2={xd(0)} y1={2} y2={80} className={styles.zero} />
          {PARENTS.map((p, i) => (
            <IntervalRow
              key={p}
              name={`${p} GRU minus Ridge`}
              y={24 + i * 32}
              x={xd}
              iv={r.parents[p].diff}
              label={p}
              emphasis={p === parent}
              onFocus={() => setHover(`${p}: GRU minus Ridge ${ivl(r.parents[p].diff)}, ${sgn(r.parents[p].diff.relPct, 2)}% relative`)}
            />
          ))}
          <text x={w - right} y={108} className={styles.tick} textAnchor="end">
            GRU worse →
          </text>
          <text x={left} y={108} className={styles.tick}>
            ← GRU better
          </text>
        </svg>
      </div>
    </Panel>
  );
}

/* ---------------------------------------------------------------- Act V: B_GROUP → B_MAG → H_HISTORY */

export function UncertaintyPanel({ evidence, step, slot }: { evidence: StoryEvidence; step: number; slot: string }) {
  const s = evidence.scale;
  const [parent, setParent] = useState<ParentKey>("TEST_A");
  const [hover, setHover] = useState<string | null>(null);
  const [ref, w] = useWidth();
  const models = s.parents.TEST_A.scores.map((x) => x.model);
  const all = PARENTS.flatMap((p) => s.parents[p].scores.map((x) => x.crps));
  const yLo = Math.floor(Math.min(...all) * 20) / 20 - 0.05;
  const yHi = Math.ceil(Math.max(...all) * 20) / 20 + 0.05;
  const H = 170;
  const top = 12;
  const bottom = 34;
  const left = 52;
  const right = 92;
  const xm = (i: number) => left + (i * (w - left - right)) / (models.length - 1);
  const ys = (v: number) => top + ((yHi - v) / (yHi - yLo)) * (H - top - bottom);
  const cur = s.parents[parent];
  const contrasts = [
    { key: "mag", label: "B_MAG − B_GROUP", iv: cur.magVsGroup, primary: false },
    { key: "hist", label: "H_HISTORY − B_MAG", iv: cur.historyVsMag, primary: true },
  ];
  const dLo = Math.min(...contrasts.map((c) => c.iv.lo)) - 0.02;
  const dHi = Math.max(0, ...contrasts.map((c) => c.iv.hi)) + 0.02;
  const labelW = Math.min(150, Math.round(w * 0.36));
  const xd = (v: number) => labelW + ((v - dLo) / (dHi - dLo)) * (w - labelW - 20);
  return (
    <Panel
      id="uncertainty"
      slot={slot}
      badge="Evidence · RES-639 · public aggregate"
      title={step >= 1 ? `Adding ${s.historyFeatures} history features made the forecasts slightly worse` : "Same Ridge forecast, three ways to set its uncertainty"}
      controls={<ParentSwitch value={parent} onChange={setParent} label="Independent test parent" />}
      readout={hover ?? `${parent}: H_HISTORY − B_MAG ${ivl(cur.historyVsMag, 4)}; B_MAG − B_GROUP ${ivl(cur.magVsGroup, 4)}.`}
      caption={
        <>
          Macro CRPS (kg) on observed synthetic Y, control scenario; lower is better. B_MAG − B_GROUP is descriptive only: the scale-fitting procedures also differ, so that gain is not attributable to magnitude
          alone.
        </>
      }
      method={
        <>
          Primary contrast: H_HISTORY − B_MAG (positive = histories worse). Interval: {s.ciScope} Disposition <code>{s.disposition}</code>
          {s.auditChecks ? `; independent audit: ${s.auditChecks} recomputation checks` : ""}.
          <SourceLine
            evidence={evidence}
            items={[
              { label: "scores", src: s.scoreSource },
              { label: "contrasts", src: s.contrastSource },
            ]}
          />
        </>
      }
      table={{
        caption: "RES-639 control macro CRPS (kg) and paired differences",
        head: ["Parent", "B_GROUP", "B_MAG", "H_HISTORY", "B_MAG − B_GROUP [95%]", "H_HISTORY − B_MAG [95%]"],
        rows: PARENTS.map((p) => [p, ...s.parents[p].scores.map((x) => x.crps.toFixed(4)), ivl(s.parents[p].magVsGroup), ivl(s.parents[p].historyVsMag)]),
      }}
    >
      <div ref={ref} className={styles.plot} data-step={step}>
        <p className={styles.plotLabel}>CRPS, kg · both parents</p>
        <svg width={w} height={H} viewBox={`0 0 ${w} ${H}`} aria-hidden="true">
          {ticks(yLo, yHi, 4).map((t) => (
            <g key={t}>
              <line x1={left} x2={w - right} y1={ys(t)} y2={ys(t)} className={styles.grid} />
              <text x={left - 8} y={ys(t) + 4} className={styles.tick} textAnchor="end">
                {t.toFixed(1)}
              </text>
            </g>
          ))}
          {models.map((m, i) => (
            <text key={m} x={xm(i)} y={H - 10} className={styles.axisLabel} textAnchor="middle">
              {m}
            </text>
          ))}
          {PARENTS.map((p) => {
            const pts = s.parents[p].scores.map((x, i) => [xm(i), ys(x.crps)] as const);
            const on = p === parent;
            return (
              <g key={p} className={[styles.slope, on ? styles.slopeOn : ""].join(" ")}>
                <path d={`M${pts[0]![0]},${pts[0]![1]} L${pts[1]![0]},${pts[1]![1]}`} className={styles.slopeLine} />
                <path d={`M${pts[1]![0]},${pts[1]![1]} L${pts[2]![0]},${pts[2]![1]}`} className={[styles.slopeLine, styles.slopeUp].join(" ")} />
                {s.parents[p].scores.map((x, i) => (
                  <g key={x.model} onPointerEnter={() => setHover(`${p} ${x.model}: CRPS ${x.crps.toFixed(4)} kg`)}>
                    <circle cx={xm(i)} cy={ys(x.crps)} r={14} className={styles.hit} />
                    <circle cx={xm(i)} cy={ys(x.crps)} r={5} className={x.model === "H_HISTORY" ? styles.dotE : x.model === "B_MAG" ? styles.dotC : styles.dotN} />
                  </g>
                ))}
                <text x={pts[2]![0] + 10} y={pts[2]![1] + 4} className={styles.value}>
                  {p}
                </text>
              </g>
            );
          })}
        </svg>
        <div className={styles.reveal} data-on={step >= 1}>
          <p className={styles.plotLabel}>Paired differences, {parent}, kg, with 95% interval</p>
          <svg width={w} height={96} viewBox={`0 0 ${w} 96`} role="group" aria-label={`Paired differences for ${parent}`}>
            {ticks(dLo, dHi, 4).map((t) => (
              <g key={t}>
                <line x1={xd(t)} x2={xd(t)} y1={6} y2={70} className={styles.grid} />
                <text x={xd(t)} y={88} className={styles.tick} textAnchor="middle">
                  {t === 0 ? "0" : sgn(t, 2)}
                </text>
              </g>
            ))}
            <line x1={xd(0)} x2={xd(0)} y1={2} y2={72} className={styles.zero} />
            {contrasts.map((c, i) => (
              <IntervalRow
                key={c.key}
                name={`${parent} ${c.label}${c.primary ? ", primary" : ", descriptive"}`}
                y={22 + i * 30}
                x={xd}
                iv={c.iv}
                label={c.label}
                emphasis={c.primary}
                onFocus={() => setHover(`${parent} ${c.label}${c.primary ? " (primary)" : " (descriptive)"}: ${ivl(c.iv, 4)}`)}
              />
            ))}
          </svg>
        </div>
      </div>
    </Panel>
  );
}
