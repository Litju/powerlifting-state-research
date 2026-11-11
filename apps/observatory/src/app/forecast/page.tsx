import type { Metadata } from "next";
import { ForecastExplorer } from "@/components/ForecastExplorer";
import { ForestPlot } from "@/components/charts";
import { Banner, PageHeader, Provenance, TargetChip } from "@/components/Ui";
import ui from "@/components/ui.module.css";
import { evidence, sourceUrl } from "@/lib/evidence";
import { signed } from "@/lib/format";
import { historyContrasts, ridgeVersusGru } from "@/lib/forecast";

export const metadata: Metadata = {
  title: "Forecasting and uncertainty lab",
  description: "Source-bound CRPS, NLL, coverage and paired-difference results for Ridge versus GRU and for B_GROUP, B_MAG and H_HISTORY on the observed synthetic assessment.",
};

export default function ForecastPage() {
  const ridge = ridgeVersusGru(evidence);
  const hist = historyContrasts(evidence).filter((c) => c.status === "PRIMARY" || c.contrast === "H_HISTORY-B_GROUP" || c.contrast === "B_MAG-B_GROUP");
  const data = {
    scores: evidence.scores,
    contrasts: evidence.contrasts,
    shifts: evidence.shifts,
    group_cells: evidence.group_cells,
    scale_coverage: evidence.scale_coverage,
    pit: evidence.pit,
    studies: evidence.studies,
  };
  const s616 = evidence.studies.find((s) => s.id === "RES-616")!;
  const s639 = evidence.studies.find((s) => s.id === "RES-639")!;
  const primary = hist.filter((c) => c.status === "PRIMARY");
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="Forecasting and uncertainty" title="Does the more complex model forecast better, and how sure is it?">
        <p>
          Two completed synthetic studies forecast the <em>future noisy strength assessment</em>, not latent capacity. Both returned negative primary findings. Every value below is read from a hashed
          aggregate table; nothing is simulated in the browser on this page.
        </p>
      </PageHeader>
      <p style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <TargetChip target="Y" />
      </p>
      <Banner kind="info" title="What this page can and cannot show">
        <p>
          Only aggregate tables that are tracked in the public repository are plotted. Per-athlete prediction distributions, per-row scores, weights and test truth are not public, so none is shown or
          reconstructed. Intervals are plotted only where the tables supply them (pooled macro contrasts).
        </p>
      </Banner>

      <section className={ui.section} aria-labelledby="h-ridge-gru">
        <h2 id="h-ridge-gru">Headline 1 · Ridge versus GRU on the observed assessment</h2>
        <p>
          Disposition <code>{s616.disposition}</code>. The GRU beats persistence but is slightly <em>worse</em> than Ridge on both independent test parents. Control scenario, macro CRPS, kg.
        </p>
        <ForestPlot
          title="M2 GRU minus M1 Ridge: paired macro CRPS difference (kg), control"
          rows={ridge.map((c) => ({ id: c.parent, label: c.parent, diff: c.diff, lo: c.ci_lo, hi: c.ci_hi, color: "var(--c-boundary)" }))}
          unit="kg"
          ariaLabel="Forest plot: GRU minus Ridge paired CRPS difference. Both parents are above zero, meaning the GRU is worse than Ridge."
          caption={`${ridge.map((c) => `${c.parent}: ${signed(c.diff)} kg [${signed(c.ci_lo)}, ${signed(c.ci_hi)}], ${c.rel_pct.toFixed(2)}% relative`).join("; ")}. ${ridge[0]?.ci_scope ?? ""}`}
        />
        {ridge[0] ? <Provenance path={ridge[0].source_path} sha={ridge[0].source_sha256} studyId={ridge[0].study_id} /> : null}
      </section>

      <section className={ui.section} aria-labelledby="h-history">
        <h2 id="h-history">Headline 2 · Do participant-visible histories improve the predictive scale?</h2>
        <p>
          Disposition <code>{s639.disposition}</code>. Relative to forecast magnitude alone (<code>B_MAG</code>), adding histories (<code>H_HISTORY</code>) is slightly worse:{" "}
          {primary.map((c) => `${c.parent} ${signed(c.diff, 6)} kg`).join(" and ")}, both intervals above zero. The frozen screen needed an improvement of at least 1% on both parents.
        </p>
        <ForestPlot
          title="Paired macro CRPS differences (kg), control"
          rows={hist.map((c) => ({
            id: `${c.parent}-${c.contrast}`,
            label: `${c.parent}: ${c.contrast.replace("-", " minus ")}`,
            diff: c.diff,
            lo: c.ci_lo,
            hi: c.ci_hi,
            color: c.status === "PRIMARY" ? "var(--c-boundary)" : "var(--fg)",
          }))}
          unit="kg"
          ariaLabel="Forest plot of paired CRPS differences. H_HISTORY minus B_MAG is above zero on both parents (worse). H_HISTORY and B_MAG are both below B_GROUP."
          caption={`Primary contrast highlighted in red. Descriptive contrasts against B_GROUP do not isolate magnitude from group-RMS estimation. ${hist[0]?.ci_scope ?? ""}`}
        />
        {hist[0] ? <Provenance path={hist[0].source_path} sha={hist[0].source_sha256} studyId={hist[0].study_id} /> : null}
        <p>
          Independent audit: <a href={sourceUrl(s639.audit_path ?? "")}>{s639.audit_path}</a> records {s639.audit_checks} recomputation checks with no failed check. Bootstrap intervals and PIT values are not
          independently recomputable because per-entity scores are not published.
        </p>
      </section>

      <section className={ui.section}>
        <ForecastExplorer data={data} />
      </section>

      <section className={ui.section} aria-labelledby="h-restricted">
        <h2 id="h-restricted">Earlier probabilistic studies (M10 to M12)</h2>
        <Banner kind="restricted" title="Restricted raw evidence, aggregate report only">
          <p>
            The conditional-scale, group-calibration and controlled-shift studies are reported publicly only as aggregates in{" "}
            <a href={sourceUrl("docs/studies/probabilistic-capacity-forecasting.md")}>docs/studies/probabilistic-capacity-forecasting.md</a>. Their cohorts, scores and fitted parameters are
            restricted, so there is nothing to explore interactively. Summary statements are on the <a href="/journey#RES-615">research journey</a>.
          </p>
        </Banner>
      </section>
    </div>
  );
}
