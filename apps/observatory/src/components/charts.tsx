"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChartTable } from "./DataTable";
import styles from "./charts.module.css";

export const MODEL_COLORS: Record<string, string> = {
  M0_C: "var(--fg-muted)",
  M1_C: "var(--c-latent)",
  M2_C: "var(--c-expressed)",
  M1_G: "var(--c-observed)",
  M2_G: "var(--ok)",
  B_GROUP: "var(--fg-muted)",
  B_MAG: "var(--c-latent)",
  H_HISTORY: "var(--c-expressed)",
};
export const colorFor = (model: string) => MODEL_COLORS[model] ?? "var(--fg-muted)";

function useWidth(initial = 640): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWidth(Math.max(260, Math.floor(el.getBoundingClientRect().width)));
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function niceTicks(min: number, max: number, count = 5): number[] {
  const span = max - min || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const first = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let v = first; v <= max + step * 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

export function ChartFrame({
  title,
  subtitle,
  caption,
  table,
  legend,
  children,
  ariaLabel,
  frameRef,
}: {
  title: string;
  subtitle?: string;
  caption: ReactNode;
  table: { caption: string; head: string[]; body: (string | number)[][] };
  legend?: { label: string; color: string }[];
  children: ReactNode;
  ariaLabel: string;
  frameRef?: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <figure className={styles.figure}>
      <p className={styles.title}>{title}</p>
      {subtitle ? <p className={styles.sub}>{subtitle}</p> : null}
      <div ref={frameRef} role="img" aria-label={ariaLabel}>
        {children}
      </div>
      {legend ? (
        <ul className={styles.legend} aria-label="Legend">
          {legend.map((l) => (
            <li key={l.label}>
              <span className={styles.swatch} style={{ background: l.color }} aria-hidden="true" />
              {l.label}
            </li>
          ))}
        </ul>
      ) : null}
      <figcaption>{caption}</figcaption>
      <ChartTable {...table} />
    </figure>
  );
}

export interface BarRow {
  id: string;
  label: string;
  value: number;
  color: string;
}

/** Horizontal bars. Bars start at the domain minimum (zero unless stated); value labels are printed. */
export function HBarChart({
  title,
  subtitle,
  rows,
  domain,
  digits = 3,
  unit,
  reference,
  caption,
  ariaLabel,
}: {
  title: string;
  subtitle?: string;
  rows: BarRow[];
  domain: [number, number];
  digits?: number;
  unit: string;
  reference?: { value: number; label: string };
  caption: ReactNode;
  ariaLabel: string;
}) {
  const [ref, width] = useWidth();
  const labelW = width < 480 ? Math.round(width * 0.38) : 220;
  const margin = { top: 8, right: 64, bottom: 28, left: labelW };
  const rowH = 30;
  const h = margin.top + margin.bottom + rows.length * rowH;
  const x = (v: number) => margin.left + ((v - domain[0]) / (domain[1] - domain[0])) * (width - margin.left - margin.right);
  const ticks = niceTicks(domain[0], domain[1], width < 480 ? 3 : 5);
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      caption={caption}
      ariaLabel={ariaLabel}
      frameRef={ref}
      table={{ caption: `${title} (${unit})`, head: ["Model", unit], body: rows.map((r) => [r.label, r.value.toFixed(digits)]) }}
    >
      {rows.length === 0 ? (
        <p className={styles.empty}>No records for this selection.</p>
      ) : (
        <svg className={styles.svg} viewBox={`0 0 ${width} ${h}`} width={width} height={h} aria-hidden="true">
          {ticks.map((t) => (
            <g key={t}>
              <line className={styles.grid} x1={x(t)} x2={x(t)} y1={margin.top} y2={h - margin.bottom} />
              <text className={styles.tick} x={x(t)} y={h - 10} textAnchor="middle">
                {t}
              </text>
            </g>
          ))}
          {rows.map((r, i) => {
            const y = margin.top + i * rowH;
            const w = Math.max(1, x(r.value) - x(domain[0]));
            return (
              <g key={r.id}>
                <text className={styles.label} x={margin.left - 8} y={y + rowH / 2 + 4} textAnchor="end">
                  {r.label.length > (width < 480 ? 18 : 32) ? `${r.label.slice(0, width < 480 ? 17 : 31)}…` : r.label}
                </text>
                <rect x={x(domain[0])} y={y + 5} width={w} height={rowH - 12} fill={r.color} />
                <text className={styles.tick} x={x(r.value) + 6} y={y + rowH / 2 + 4} style={{ fill: "var(--fg)" }}>
                  {r.value.toFixed(digits)}
                </text>
              </g>
            );
          })}
          {reference ? (
            <g>
              <line className={styles.ref} x1={x(reference.value)} x2={x(reference.value)} y1={margin.top} y2={h - margin.bottom} />
              <text className={styles.tick} x={x(reference.value)} y={margin.top + 2} textAnchor="middle" style={{ fill: "var(--c-boundary)" }}>
                {reference.label}
              </text>
            </g>
          ) : null}
          <line className={styles.axis} x1={x(domain[0])} x2={x(domain[0])} y1={margin.top} y2={h - margin.bottom} />
        </svg>
      )}
    </ChartFrame>
  );
}

export interface ForestRow {
  id: string;
  label: string;
  diff: number;
  lo: number;
  hi: number;
  color: string;
}

/** Point estimates with 95% intervals around a zero line. Positive = first-named model worse. */
export function ForestPlot({
  title,
  subtitle,
  rows,
  unit,
  caption,
  ariaLabel,
  digits = 4,
}: {
  title: string;
  subtitle?: string;
  rows: ForestRow[];
  unit: string;
  caption: ReactNode;
  ariaLabel: string;
  digits?: number;
}) {
  const [ref, width] = useWidth();
  const labelW = width < 480 ? Math.round(width * 0.36) : 250;
  const margin = { top: 22, right: 20, bottom: 44, left: labelW };
  const rowH = 34;
  const h = margin.top + margin.bottom + rows.length * rowH;
  const lo = Math.min(0, ...rows.map((r) => r.lo));
  const hi = Math.max(0, ...rows.map((r) => r.hi));
  const pad = (hi - lo) * 0.08 || 0.01;
  const dom: [number, number] = [lo - pad, hi + pad];
  const x = (v: number) => margin.left + ((v - dom[0]) / (dom[1] - dom[0])) * (width - margin.left - margin.right);
  const ticks = niceTicks(dom[0], dom[1], width < 480 ? 3 : 5);
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      caption={caption}
      ariaLabel={ariaLabel}
      frameRef={ref}
      table={{
        caption: `${title} (${unit})`,
        head: ["Contrast (first minus second)", "Difference", "95% lower", "95% upper"],
        body: rows.map((r) => [r.label, r.diff.toFixed(digits), r.lo.toFixed(digits), r.hi.toFixed(digits)]),
      }}
    >
      {rows.length === 0 ? (
        <p className={styles.empty}>No paired contrast is published for this selection.</p>
      ) : (
        <svg className={styles.svg} viewBox={`0 0 ${width} ${h}`} width={width} height={h} aria-hidden="true">
          {ticks.map((t) => (
            <g key={t}>
              <line className={styles.grid} x1={x(t)} x2={x(t)} y1={margin.top} y2={h - margin.bottom} />
              <text className={styles.tick} x={x(t)} y={h - 26} textAnchor="middle">
                {t}
              </text>
            </g>
          ))}
          <line className={styles.ref} x1={x(0)} x2={x(0)} y1={margin.top - 6} y2={h - margin.bottom} />
          <text className={styles.tick} x={x(0)} y={12} textAnchor="middle" style={{ fill: "var(--c-boundary)" }}>
            0 = no difference
          </text>
          {rows.map((r, i) => {
            const y = margin.top + i * rowH + rowH / 2;
            return (
              <g key={r.id}>
                <text className={styles.label} x={margin.left - 10} y={y + 4} textAnchor="end">
                  {r.label.length > (width < 480 ? 17 : 36) ? `${r.label.slice(0, width < 480 ? 16 : 35)}…` : r.label}
                </text>
                <line x1={x(r.lo)} x2={x(r.hi)} y1={y} y2={y} stroke={r.color} strokeWidth={3} />
                <line x1={x(r.lo)} x2={x(r.lo)} y1={y - 6} y2={y + 6} stroke={r.color} strokeWidth={2} />
                <line x1={x(r.hi)} x2={x(r.hi)} y1={y - 6} y2={y + 6} stroke={r.color} strokeWidth={2} />
                <rect x={x(r.diff) - 5} y={y - 5} width={10} height={10} fill={r.color} transform={`rotate(45 ${x(r.diff)} ${y})`} />
              </g>
            );
          })}
          <text className={styles.tick} x={margin.left} y={h - 6}>
            ← first model better
          </text>
          <text className={styles.tick} x={width - margin.right} y={h - 6} textAnchor="end">
            first model worse →
          </text>
        </svg>
      )}
    </ChartFrame>
  );
}

export interface StripLevel {
  nominal: number;
  points: { id: string; label: string; value: number; color: string }[];
}

/** Observed coverage against nominal level. The red line marks the nominal value. */
export function CoverageStrip({
  title,
  subtitle,
  levels,
  caption,
  ariaLabel,
  legend,
}: {
  title: string;
  subtitle?: string;
  levels: StripLevel[];
  caption: ReactNode;
  ariaLabel: string;
  legend: { label: string; color: string }[];
}) {
  const [ref, width] = useWidth();
  const margin = { top: 8, right: 24, bottom: 30, left: 76 };
  const rowH = 52;
  const h = margin.top + margin.bottom + levels.length * rowH;
  const dom: [number, number] = [0.7, 1];
  const x = (v: number) => margin.left + ((Math.min(Math.max(v, dom[0]), dom[1]) - dom[0]) / (dom[1] - dom[0])) * (width - margin.left - margin.right);
  const ticks = [0.7, 0.8, 0.9, 1];
  const body: (string | number)[][] = [];
  for (const level of levels) for (const p of level.points) body.push([`${p.label} @ nominal ${Math.round(level.nominal * 100)}%`, `${(p.value * 100).toFixed(2)}%`]);
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      caption={caption}
      ariaLabel={ariaLabel}
      frameRef={ref}
      legend={legend}
      table={{ caption: title, head: ["Model at nominal level", "Observed coverage"], body }}
    >
      {levels.length === 0 ? (
        <p className={styles.empty}>No coverage records for this selection.</p>
      ) : (
        <svg className={styles.svg} viewBox={`0 0 ${width} ${h}`} width={width} height={h} aria-hidden="true">
          {ticks.map((t) => (
            <g key={t}>
              <line className={styles.grid} x1={x(t)} x2={x(t)} y1={margin.top} y2={h - margin.bottom} />
              <text className={styles.tick} x={x(t)} y={h - 10} textAnchor="middle">
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}
          {levels.map((level, i) => {
            const y = margin.top + i * rowH + rowH / 2;
            return (
              <g key={level.nominal}>
                <text className={styles.label} x={margin.left - 10} y={y + 4} textAnchor="end">
                  nominal {Math.round(level.nominal * 100)}%
                </text>
                <line className={styles.grid} x1={margin.left} x2={width - margin.right} y1={y} y2={y} />
                <line className={styles.ref} x1={x(level.nominal)} x2={x(level.nominal)} y1={y - 20} y2={y + 20} />
                {level.points.map((p, j) => (
                  <circle key={p.id} cx={x(p.value)} cy={y + (j - (level.points.length - 1) / 2) * 7} r={5} fill={p.color} stroke="var(--bg-raised)" strokeWidth={1.5} />
                ))}
              </g>
            );
          })}
        </svg>
      )}
    </ChartFrame>
  );
}

export function PitHistogram({
  title,
  series,
  caption,
  ariaLabel,
}: {
  title: string;
  series: { model: string; label: string; fractions: number[] }[];
  caption: ReactNode;
  ariaLabel: string;
}) {
  const [ref, width] = useWidth();
  const margin = { top: 10, right: 12, bottom: 28, left: 40 };
  const h = 200;
  const max = 0.13;
  const bins = 10;
  const innerW = width - margin.left - margin.right;
  const y = (v: number) => h - margin.bottom - (v / max) * (h - margin.top - margin.bottom);
  const groupW = innerW / bins;
  const barW = Math.max(2, (groupW - 4) / Math.max(1, series.length));
  const body: (string | number)[][] = [];
  for (let b = 0; b < bins; b += 1) body.push([`bin ${b + 1}`, ...series.map((s) => (s.fractions[b] ?? 0).toFixed(4))]);
  return (
    <ChartFrame
      title={title}
      caption={caption}
      ariaLabel={ariaLabel}
      frameRef={ref}
      legend={series.map((s) => ({ label: s.label, color: colorFor(s.model) }))}
      table={{ caption: title, head: ["PIT bin", ...series.map((s) => s.label)], body }}
    >
      <svg className={styles.svg} viewBox={`0 0 ${width} ${h}`} width={width} height={h} aria-hidden="true">
        {[0, 0.05, 0.1].map((t) => (
          <g key={t}>
            <line className={styles.grid} x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} />
            <text className={styles.tick} x={margin.left - 6} y={y(t) + 4} textAnchor="end">
              {t.toFixed(2)}
            </text>
          </g>
        ))}
        {Array.from({ length: bins }, (_, b) =>
          series.map((s, k) => {
            const v = s.fractions[b] ?? 0;
            return <rect key={`${b}-${s.model}`} x={margin.left + b * groupW + 2 + k * barW} y={y(v)} width={barW - 1} height={y(0) - y(v)} fill={colorFor(s.model)} />;
          }),
        )}
        <line className={styles.ref} x1={margin.left} x2={width - margin.right} y1={y(0.1)} y2={y(0.1)} />
        <text className={styles.tick} x={width - margin.right} y={y(0.1) - 4} textAnchor="end" style={{ fill: "var(--c-boundary)" }}>
          uniform = 0.10
        </text>
        {Array.from({ length: bins }, (_, b) => (
          <text key={b} className={styles.tick} x={margin.left + b * groupW + groupW / 2} y={h - 10} textAnchor="middle">
            {b + 1}
          </text>
        ))}
      </svg>
    </ChartFrame>
  );
}

export interface LineSeries {
  id: string;
  label: string;
  color: string;
  dashed?: boolean;
  points: [number, number][];
}

export function LineChart({
  title,
  subtitle,
  series,
  markers = [],
  vline,
  xLabel,
  yLabel,
  caption,
  ariaLabel,
  tableRows,
}: {
  title: string;
  subtitle?: string;
  series: LineSeries[];
  markers?: { id: string; label: string; color: string; points: [number, number][]; hollow?: boolean }[];
  vline?: { x: number; label: string };
  xLabel: string;
  yLabel: string;
  caption: ReactNode;
  ariaLabel: string;
  tableRows: { head: string[]; body: (string | number)[][] };
}) {
  const [ref, width] = useWidth();
  const margin = { top: 14, right: 16, bottom: 40, left: 52 };
  const h = width < 480 ? 280 : 340;
  const all = [...series.flatMap((s) => s.points), ...markers.flatMap((m) => m.points)];
  const xs = all.map((p) => p[0]);
  const ys = all.map((p) => p[1]);
  const xd: [number, number] = [Math.min(...xs), Math.max(...xs)];
  const ymin = Math.min(...ys);
  const ymax = Math.max(...ys);
  const ypad = (ymax - ymin) * 0.06 || 1;
  const yd: [number, number] = [ymin - ypad, ymax + ypad];
  const x = (v: number) => margin.left + ((v - xd[0]) / (xd[1] - xd[0] || 1)) * (width - margin.left - margin.right);
  const y = (v: number) => h - margin.bottom - ((v - yd[0]) / (yd[1] - yd[0] || 1)) * (h - margin.top - margin.bottom);
  const xt = niceTicks(xd[0], xd[1], width < 480 ? 4 : 7);
  const yt = niceTicks(yd[0], yd[1], 5);
  const path = (pts: [number, number][]) => pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      caption={caption}
      ariaLabel={ariaLabel}
      frameRef={ref}
      legend={[...series.map((s) => ({ label: s.label, color: s.color })), ...markers.map((m) => ({ label: m.label, color: m.color }))]}
      table={{ caption: title, head: tableRows.head, body: tableRows.body }}
    >
      <svg className={styles.svg} viewBox={`0 0 ${width} ${h}`} width={width} height={h} aria-hidden="true">
        {yt.map((t) => (
          <g key={t}>
            <line className={styles.grid} x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} />
            <text className={styles.tick} x={margin.left - 6} y={y(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        {xt.map((t) => (
          <text key={t} className={styles.tick} x={x(t)} y={h - margin.bottom + 16} textAnchor="middle">
            {t}
          </text>
        ))}
        <text className={styles.tick} x={(margin.left + width - margin.right) / 2} y={h - 6} textAnchor="middle">
          {xLabel}
        </text>
        <text className={styles.tick} x={12} y={margin.top + 4} transform={`rotate(-90 12 ${margin.top + 4})`} textAnchor="end">
          {yLabel}
        </text>
        {vline ? (
          <g>
            <line className={styles.ref} x1={x(vline.x)} x2={x(vline.x)} y1={margin.top} y2={h - margin.bottom} />
            <text className={styles.tick} x={x(vline.x) - 4} y={margin.top + 10} textAnchor="end" style={{ fill: "var(--c-boundary)" }}>
              {vline.label}
            </text>
          </g>
        ) : null}
        {series.map((s) => (
          <path key={s.id} d={path(s.points)} fill="none" stroke={s.color} strokeWidth={2.2} strokeDasharray={s.dashed ? "6 4" : undefined} />
        ))}
        {markers.map((m) =>
          m.points.map((p, i) => (
            <circle key={`${m.id}-${i}`} cx={x(p[0])} cy={y(p[1])} r={3.4} fill={m.hollow ? "var(--bg-raised)" : m.color} stroke={m.color} strokeWidth={1.6} />
          )),
        )}
        <line className={styles.axis} x1={margin.left} x2={width - margin.right} y1={h - margin.bottom} y2={h - margin.bottom} />
        <line className={styles.axis} x1={margin.left} x2={margin.left} y1={margin.top} y2={h - margin.bottom} />
      </svg>
    </ChartFrame>
  );
}
