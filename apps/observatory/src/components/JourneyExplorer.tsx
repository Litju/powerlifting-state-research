"use client";

import { useEffect, useState } from "react";
import type { Evidence } from "@/lib/evidence";
import { sourceUrl } from "@/lib/evidence";
import { signed } from "@/lib/format";
import { STAGES, factsFor, studiesFor } from "@/lib/journey";
import { Banner, Chip, Provenance, TargetChip } from "./Ui";
import ui from "./ui.module.css";
import styles from "./journey.module.css";

type JourneyData = Pick<Evidence, "facts" | "studies" | "sources">;

export function JourneyExplorer({ data }: { data: JourneyData }) {
  const [active, setActive] = useState(STAGES[0]!.id);
  useEffect(() => {
    const apply = () => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (STAGES.some((s) => s.id === id)) setActive(id);
    };
    apply();
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);
  const stage = STAGES.find((s) => s.id === active)!;
  const facts = factsFor(stage, data);
  const studies = studiesFor(stage, data);
  return (
    <div className={styles.layout}>
      <nav aria-label="Research stages">
        <ol className={styles.rail}>
          {STAGES.map((s, i) => (
            <li key={s.id}>
              <button
                type="button"
                id={`stage-tab-${s.id}`}
                className={styles.stageBtn}
                aria-pressed={s.id === active}
                aria-controls="stage-panel"
                data-testid={`stage-${s.id}`}
                onClick={() => {
                  setActive(s.id);
                  history.replaceState(null, "", `#${s.id}`);
                }}
              >
                <span className={styles.idx}>{String(i + 1).padStart(2, "0")}</span>
                {s.label}
              </button>
            </li>
          ))}
        </ol>
      </nav>
      <article id="stage-panel" className={styles.panel} aria-live="polite" aria-labelledby={`stage-tab-${stage.id}`} tabIndex={-1} data-testid="stage-panel">
        <p className={ui.eyebrow}>{stage.label}</p>
        <h2>{stage.question}</h2>
        <p className={styles.verdict}>{stage.verdict}</p>
        {facts.map((f) => (
          <section key={f.id} className={styles.fact} aria-label={f.title}>
            <h3>{f.title}</h3>
            <p style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <TargetChip target={f.target} />
              {f.access === "restricted_aggregate_only" ? <Chip kind="restricted">restricted raw evidence, aggregate report only</Chip> : <Chip>public aggregate</Chip>}
            </p>
            <p>{f.statement}</p>
            <Banner title="Limits">
              <p>{f.limits}</p>
            </Banner>
            <Provenance path={f.source_path} sha={f.source_sha256} extra={<div><dt>verified phrases</dt><dd>{f.verified_strings.length} checked at build</dd></div>} />
          </section>
        ))}
        {studies.map((s) => (
          <section key={s.id} className={styles.fact} aria-label={`${s.id} primary endpoint`}>
            <h3>Primary endpoint ({s.id}, paired macro CRPS, kg)</h3>
            <p>
              Disposition <code>{s.disposition}</code>. Positive differences mean the first-named model is worse.
            </p>
            <ul className={ui.list}>
              {Object.entries(s.primary).map(([parent, p]) => (
                <li key={parent}>
                  {parent}: {signed(p.diff, 6)} kg, 95% interval [{signed(p.ci_lo, 4)}, {signed(p.ci_hi, 4)}], {signed(p.rel_pct, 2)}%
                </li>
              ))}
            </ul>
            <p>
              <strong>Non-claims.</strong> {s.nonclaims.slice(0, 3).join("; ")}.
            </p>
            <Provenance path={s.summary_path} sha={data.sources.find((x) => x.path === s.summary_path)?.sha256 ?? ""} extra={<div><dt>manifest</dt><dd><a href={sourceUrl(s.manifest_path)}>{s.manifest_path}</a></dd></div>} />
          </section>
        ))}
        <h3>Lineage</h3>
        <p>{stage.lineage}</p>
      </article>
    </div>
  );
}
