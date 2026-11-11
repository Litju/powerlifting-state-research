import type { Metadata } from "next";
import Link from "next/link";
import { Banner, PageHeader } from "@/components/Ui";
import ui from "@/components/ui.module.css";
import { evidence } from "@/lib/evidence";

export const metadata: Metadata = {
  title: "About, methods and limitations",
  description: "What the Observatory is, how its evidence is built and checked, and what it does not claim.",
};

export default function AboutPage() {
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="About, methods and limitations" title="What this is, and what it is not">
        <p>
          The Observatory is a reading and exploration layer over the public Powerlifting State Research repository. It presents synthetic-system results as aggregates with their sources, and it
          keeps negative results in front.
        </p>
      </PageHeader>

      <Banner title="Non-claims">
        <ul className={ui.list}>
          <li>No real-athlete validation. Every dataset is simulated.</li>
          <li>No prescriptive coaching and no causal physiological claim. Nothing here estimates a person&apos;s capacity, fatigue or adaptation.</li>
          <li>No peer-review, DOI, arXiv or journal status. Independent external human review has not occurred.</li>
          <li>No universal ranking of models, and no robustness beyond the two named shifts.</li>
        </ul>
      </Banner>

      <section className={ui.section} aria-labelledby="h-method">
        <h2 id="h-method">Methods</h2>
        <div className={ui.grid2}>
          <div>
            <h3>Three quantities, kept apart</h3>
            <p>
              <strong>C</strong> latent capacity, <strong>E</strong> = C(1 − g<sub>S</sub> S) expressed performance and <strong>Y</strong> the noisy observed assessment are different scientific
              quantities. Each record in the evidence file carries its target, and the interface never plots or ranks across targets.
            </p>
            <p>
              The <Link href="/lab">System lab</Link> is the only place values are computed in your browser. It is an illustrative demonstration of the public law and is not evidence.
            </p>
          </div>
          <div>
            <h3>Evidence pipeline</h3>
            <p>
              A build script reads tracked public aggregate files, records each file&apos;s SHA-256, recomputes macro scores, cross-checks documented numbers and manifest hashes, and validates a
              versioned schema. It fails the build on a missing or contradicted source and never falls back to invented values. The committed file is regenerated and compared byte for byte in tests
              and in CI.
            </p>
            <p>
              Current file: <code>{evidence.schema_version}</code>, {evidence.scores.length + evidence.contrasts.length + evidence.shifts.length + evidence.group_cells.length + evidence.scale_coverage.length + evidence.pit.length + evidence.frontier.length + evidence.registry.length + evidence.facts.length} records
              from {evidence.sources.length} sources.
            </p>
          </div>
        </div>
      </section>

      <section className={ui.section} aria-labelledby="h-limits">
        <h2 id="h-limits">Statistical limits you will meet on every page</h2>
        <ul className={ui.list}>
          <li>CRPS and NLL are lower-is-better. A paired difference is first minus second, so positive means the first model is worse.</li>
          <li>Control is a same-law evaluation. A shift evaluates frozen models on altered inputs. Ranking under shift and absolute degradation are separate results.</li>
          <li>
            Confidence-interval scope: stratified entity-cluster bootstrap, conditional on the fixed fitted models. It omits training-seed variation and selection effects. One GRU was fitted, so its
            seed stability is not tested.
          </li>
          <li>Pooled calibration is not subgroup or individual calibration. Statistical distinguishability is not practical significance.</li>
          <li>Two test parents and two named shifts give six dependent scenario sets, not six replications.</li>
        </ul>
      </section>

      <section className={ui.section} aria-labelledby="h-access">
        <h2 id="h-access">Accessibility, fallbacks and privacy</h2>
        <ul className={ui.list}>
          <li>Native scrolling, keyboard and touch. The 3D scene never captures the page scroll; its camera controls are buttons, arrow keys and horizontal drag.</li>
          <li>With reduced motion, the camera does not follow scrolling and the story reads as static sections with diagrams.</li>
          <li>Without WebGL, or on a low-end device, a semantic diagram replaces the scene. Every chart has a data table as an accessible alternative.</li>
          <li>No cookies, analytics or third-party requests. The only stored value is your light or dark theme choice in local storage.</li>
        </ul>
      </section>

      <section className={ui.section} aria-labelledby="h-rights">
        <h2 id="h-rights">Rights boundary</h2>
        <p>
          The site contains only public, rights-cleared aggregate evidence. Restricted numerical evidence appears solely as the public aggregate summary and is labelled as such. See{" "}
          <Link href="/publication">Publication</Link> for licenses and the status of the manuscript.
        </p>
      </section>
    </div>
  );
}
