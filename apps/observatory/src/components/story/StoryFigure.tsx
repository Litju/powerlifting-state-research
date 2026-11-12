"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { inverseIllustration } from "@/lib/inverse";
import { DEFAULT_PARAMS, LAST_HISTORY_DAY, ORIGIN_DAY, simulate } from "@/lib/sim";
import { BEATS, type Layer } from "@/lib/story";
import styles from "./figure.module.css";

/** Plain-language description of each conceptual beat's figure (the figures carry no information that is not here). */
export const FIGURE_DESCRIPTIONS: Record<string, string> = {
  observe: "Thirty-two weekly noisy assessments Y of one simulated athlete, plotted against time in days. No model is shown.",
  question: "The same assessments, each with a vertical band of about plus or minus ten percent showing the illustrative measurement uncertainty.",
  capacity: "Latent capacity C rises smoothly from about 150 kilograms and levels off. The assessments are faded.",
  suppression: "Expressed performance E runs below capacity C; the shaded gap between them is the transient suppression.",
  noise: "Each assessment Y is joined to expressed performance E by a short line: the observation noise.",
  inverse: "Several alternative capacity curves, from other parameter settings of the same law, all fit the 32 assessments about as well as the true one, yet end at different capacities.",
  boundary: "A vertical boundary after day 223 separates the visible history from the forecast period. Dashed lines show capacity continuing or falling depending on the plan; three hollow points are future assessments.",
  ledger: "The complete picture: capacity C, expressed performance E, assessments Y, the information boundary and plan-dependent futures.",
};

function useWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [w, setW] = useState(560);
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

function useFigureData() {
  return useMemo(() => {
    const cont = simulate({ ...DEFAULT_PARAMS, plan: "continue" });
    const cess = simulate({ ...DEFAULT_PARAMS, plan: "cessation" });
    const inv = inverseIllustration();
    const vals = [...cont.series.map((p) => p.C), ...cont.series.map((p) => p.E), ...cont.assessments.map((a) => a.y * 1.1), ...cont.assessments.map((a) => a.y * 0.9), ...inv.shown.map((c) => c.cLast)];
    return { cont, cess, inv, lo: Math.floor(Math.min(...vals) / 10) * 10, hi: Math.ceil(Math.max(...vals) / 10) * 10 };
  }, []);
}

export function StoryFigure({ beatId, id, height }: { beatId: string; id: string; height?: number }) {
  const beat = BEATS.find((b) => b.id === beatId)!;
  const on = (l: Layer) => beat.layers[l] ?? 0;
  const { cont, cess, inv, lo, hi } = useFigureData();
  const [ref, w] = useWidth();
  const h = height ?? Math.round(Math.min(340, Math.max(220, w * 0.58)));
  const m = { top: 18, right: w < 420 ? 30 : 44, bottom: 30, left: 40 };
  const x = (d: number) => m.left + (d / 279) * (w - m.left - m.right);
  const y = (v: number) => m.top + ((hi - v) / (hi - lo)) * (h - m.top - m.bottom);
  const path = (pts: [number, number][]) => pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  const hist = cont.series.slice(0, ORIGIN_DAY);
  const cPath = path(hist.map((p) => [p.day, p.C]));
  const ePath = path(hist.map((p) => [p.day, p.E]));
  const gapPath = `${cPath}${hist
    .slice()
    .reverse()
    .map((p) => `L${x(p.day).toFixed(1)},${y(p.E).toFixed(1)}`)
    .join("")}Z`;
  const obs = cont.assessments.filter((a) => !a.future);
  const fut = cont.assessments.filter((a) => a.future);
  const cv = DEFAULT_PARAMS.assessmentCv;
  const yTicks = [];
  for (let v = Math.ceil(lo / 20) * 20; v <= hi; v += 20) yTicks.push(v);
  const titleId = `${id}-t`;
  const descId = `${id}-d`;
  return (
    <div ref={ref} className={styles.wrap} data-figure={beatId}>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-labelledby={`${titleId} ${descId}`} className={styles.svg} data-testid="schematic">
        <title id={titleId}>Illustrative simulation, not measured data</title>
        <desc id={descId}>{FIGURE_DESCRIPTIONS[beatId] ?? FIGURE_DESCRIPTIONS.ledger}</desc>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={w - m.right} y1={y(t)} y2={y(t)} className={styles.grid} />
            <text x={m.left - 6} y={y(t) + 4} textAnchor="end" className={styles.tick}>
              {t}
            </text>
          </g>
        ))}
        <text x={m.left - 6} y={m.top - 6} textAnchor="end" className={styles.tick}>
          kg
        </text>
        {[0, 56, 112, 168, 224, 279].map((d) => (
          <text key={d} x={x(d)} y={h - 10} textAnchor="middle" className={styles.tick}>
            {d === 279 ? "day 279" : d}
          </text>
        ))}

        {on("boundary") ? (
          <g opacity={on("boundary")}>
            <rect x={x(LAST_HISTORY_DAY + 0.5)} y={m.top} width={x(279) - x(LAST_HISTORY_DAY + 0.5)} height={h - m.top - m.bottom} className={styles.future} />
            <line x1={x(LAST_HISTORY_DAY + 0.5)} x2={x(LAST_HISTORY_DAY + 0.5)} y1={m.top - 4} y2={h - m.bottom} className={styles.boundary} />
            <text x={x(LAST_HISTORY_DAY + 0.5) - 6} y={m.top + 10} textAnchor="end" className={styles.note}>
              history ends 223
            </text>
          </g>
        ) : null}
        {on("gap") ? <path d={gapPath} className={styles.gap} opacity={on("gap")} /> : null}
        {on("candidates")
          ? inv.shown.map((c, i) => (
              <path key={i} d={path(c.series.slice(0, ORIGIN_DAY).filter((_, k) => k % 3 === 0 || k === ORIGIN_DAY - 1).map((p) => [p.day, p.C]))} className={[styles.cand, styles.draw].join(" ")} />
            ))
          : null}
        {on("C") ? <path d={cPath} className={[styles.C, beat.draws?.includes("C") ? styles.draw : ""].join(" ")} opacity={on("C")} /> : null}
        {on("E") ? <path d={ePath} className={[styles.E, beat.draws?.includes("E") ? styles.draw : ""].join(" ")} opacity={on("E")} /> : null}
        {on("future") ? (
          <g opacity={on("future")}>
            <path d={path(cont.series.slice(ORIGIN_DAY - 1).map((p) => [p.day, p.C]))} className={[styles.C, styles.dashed].join(" ")} />
            <path d={path(cess.series.slice(ORIGIN_DAY - 1).map((p) => [p.day, p.C]))} className={[styles.C, styles.dotted].join(" ")} />
            <path d={path(cont.series.slice(ORIGIN_DAY - 1).map((p) => [p.day, p.E]))} className={[styles.E, styles.dashed].join(" ")} />
            {fut.map((a) => (
              <circle key={a.day} cx={x(a.day)} cy={y(a.y)} r={5} className={styles.yFuture} />
            ))}
          </g>
        ) : null}
        {on("residual")
          ? obs.map((a) => <line key={a.day} x1={x(a.day)} x2={x(a.day)} y1={y(cont.series[a.day]!.E)} y2={y(a.y)} className={styles.residual} opacity={on("residual")} />)
          : null}
        {on("band") ? obs.map((a) => <line key={a.day} x1={x(a.day)} x2={x(a.day)} y1={y(a.y * (1 - 1.96 * cv))} y2={y(a.y * (1 + 1.96 * cv))} className={styles.band} opacity={on("band")} />) : null}
        {on("Y") ? (
          <g opacity={on("Y")}>
            {obs.map((a) => (
              <circle key={a.day} cx={x(a.day)} cy={y(a.y)} r={w < 420 ? 3.4 : 4} className={styles.Y} />
            ))}
          </g>
        ) : null}

        {/* Direct labels: identity never relies on colour alone. */}
        {on("C") > 0.5 ? (
          <text x={x(150)} y={y(cont.series[150]!.C) - 10} className={styles.label}>
            C capacity
          </text>
        ) : null}
        {on("E") > 0.5 ? (
          <text x={x(100)} y={y(cont.series[100]!.E) + 22} className={styles.label}>
            E expressed
          </text>
        ) : null}
        {on("Y") > 0.5 && !on("C") ? (
          <text x={x(4)} y={y(Math.max(...obs.slice(0, 12).map((a) => a.y))) - 16} className={styles.label}>
            Y observed
          </text>
        ) : null}
        {on("candidates") ? (
          <text x={x(ORIGIN_DAY - 2)} y={y(inv.cRange[1]) - 8} textAnchor="end" className={styles.note}>
            day-223 capacity {inv.cRange[0].toFixed(0)}–{inv.cRange[1].toFixed(0)} kg across {inv.accepted} fits
          </text>
        ) : null}
      </svg>
      <p className={styles.caption}>Illustrative simulation · not measured data</p>
    </div>
  );
}
