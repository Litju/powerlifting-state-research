"use client";

import { useEffect, useState } from "react";
import type { Evidence } from "@/lib/evidence";
import { signed } from "@/lib/format";
import { STAGES, factsFor, studiesFor, type Stage } from "@/lib/journey";
import { sourceUrl } from "@/lib/source";
import { Chip, Provenance, TargetChip } from "./Ui";
import ui from "./ui.module.css";
import styles from "./journey.module.css";

type JourneyData = Pick<Evidence, "facts" | "studies" | "sources">;

const TONE: Record<Stage["tone"], string> = {
  negative: "Negative finding",
  limited: "Bounded finding",
  descriptive: "Descriptive only",
};

/**
 * The research journey as a chronological timeline. Each stage shows its question and a one-line verdict; the
 * verified statement, limits, source hashes and lineage are one click away. Deep links (#G2) open their stage.
 */
export function JourneyExplorer({ data }: { data: JourneyData }) {
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    const apply = () => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (!STAGES.some((s) => s.id === id)) return;
      setOpen((prev) => new Set(prev).add(id));
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
    };
    apply();
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);

  function toggle(id: string, isOpen: boolean) {
    setOpen((prev) => {
      if (prev.has(id) === isOpen) return prev;
      const next = new Set(prev);
      if (isOpen) next.add(id);
      else next.delete(id);
      return next;
    });
    if (isOpen && typeof history !== "undefined") history.replaceState(null, "", `#${id}`);
  }

  return (
    <ol className={styles.timeline} aria-label="Research stages in the order they were carried out">
      {STAGES.map((stage, i) => {
        const facts = factsFor(stage, data);
        const studies = studiesFor(stage, data);
        return (
          <li key={stage.id} id={stage.id} className={styles.stage} data-tone={stage.tone}>
            <div className={styles.marker} aria-hidden="true">
              <span>{String(i + 1).padStart(2, "0")}</span>
            </div>
            <div className={styles.body}>
              <p className={styles.label}>
                {stage.label} <span className={styles.tone}>{TONE[stage.tone]}</span>
              </p>
              <h2 className={styles.question}>{stage.question}</h2>
              <p className={styles.verdict}>{stage.verdict}</p>
              <details className={styles.details} open={open.has(stage.id)} onToggle={(e) => toggle(stage.id, (e.currentTarget as HTMLDetailsElement).open)}>
                <summary data-testid={`stage-${stage.id}`}>Evidence, limits and sources</summary>
                <div className={styles.panel} data-testid={`stage-panel-${stage.id}`}>
                  {facts.map((f) => (
                    <section key={f.id} className={styles.fact} aria-label={f.title}>
                      <h3>{f.title}</h3>
                      <p className={styles.chips}>
                        <TargetChip target={f.target} />
                        {f.access === "restricted_aggregate_only" ? <Chip kind="restricted">restricted raw evidence, aggregate report only</Chip> : <Chip>public aggregate</Chip>}
                      </p>
                      <p>{f.statement}</p>
                      <p className={styles.limits}>
                        <strong>Limits.</strong> {f.limits}
                      </p>
                      <Provenance
                        path={f.source_path}
                        sha={f.source_sha256}
                        extra={
                          <div>
                            <dt>verified phrases</dt>
                            <dd>{f.verified_strings.length} checked at build</dd>
                          </div>
                        }
                      />
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
                      <p className={styles.limits}>
                        <strong>Non-claims.</strong> {s.nonclaims.slice(0, 3).join("; ")}.
                      </p>
                      <Provenance
                        path={s.summary_path}
                        sha={data.sources.find((x) => x.path === s.summary_path)?.sha256 ?? ""}
                        extra={
                          <div>
                            <dt>manifest</dt>
                            <dd>
                              <a href={sourceUrl(s.manifest_path)}>{s.manifest_path}</a>
                            </dd>
                          </div>
                        }
                      />
                    </section>
                  ))}
                  <p className={styles.lineage}>
                    <strong>Lineage.</strong> {stage.lineage}
                  </p>
                </div>
              </details>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
