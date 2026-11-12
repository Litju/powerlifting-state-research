import type { Metadata } from "next";
import { Banner, Chip, PageHeader } from "@/components/Ui";
import ui from "@/components/ui.module.css";
import { REPO_URL, REVISION, REVISION_SHORT, evidence, shortHash, sourceUrl } from "@/lib/evidence";
import { MATERIAL } from "@/lib/publication";

export const metadata: Metadata = {
  title: "Publication and open science",
  description: "Manuscript in private preparation — public release pending. Public research material, reproducibility levels, licenses and how to cite the software repository.",
};

const KIND_TITLES = {
  overview: "Overview",
  study: "Study reports and documentation",
  evidence: "Evidence files used by this Observatory",
  rights: "Reproducibility, rights and licensing",
} as const;

export default function PublicationPage() {
  const deployed = process.env.VERCEL_GIT_COMMIT_SHA;
  const sha = (path: string) => evidence.sources.find((s) => s.path === path)?.sha256;
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="Publication and open science" title="Manuscript in private preparation — public release pending">
        <p>The research reported on this site is public. A manuscript is in private preparation. It is not public, it is not available here, and no part of it is served by this site.</p>
      </PageHeader>

      <Banner title="Publication status" kind="warn">
        <p data-testid="publication-status">
          <strong>Manuscript in private preparation — public release pending.</strong> There is no DOI, no accepted or peer-reviewed article, no preprint identifier and no downloadable manuscript on this site.
        </p>
        <p>
          <strong>Pending condition (publication gate).</strong> A reader and download will be added only after the exact manuscript file has been rebuilt and verified, and the owner has separately
          approved its license and public release. Until then, this page links only to public research material in the open repository.
        </p>
      </Banner>

      <section className={ui.section} aria-labelledby="h-material">
        <h2 id="h-material">Public research material</h2>
        <p>
          Every link points to a tracked file in the public repository at{" "}
          <a href={`${REPO_URL}/tree/${REVISION}`}>
            main@<code>{REVISION_SHORT}</code>
          </a>
          . Evidence files carry the SHA-256 recorded by this Observatory at build time.
        </p>
        {(Object.keys(KIND_TITLES) as (keyof typeof KIND_TITLES)[]).map((kind) => (
          <div key={kind} style={{ marginTop: 24 }}>
            <h3>{KIND_TITLES[kind]}</h3>
            <ul className={ui.list}>
              {MATERIAL.filter((m) => m.kind === kind).map((m) => (
                <li key={m.path}>
                  <a href={sourceUrl(m.path)}>{m.title}</a> <code>{m.path}</code>
                  {sha(m.path) ? (
                    <>
                      {" "}
                      <span className={ui.prov} title={sha(m.path)}>
                        sha256 {shortHash(sha(m.path)!)}
                      </span>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
        <Banner kind="restricted" title="Restricted raw evidence, aggregate report only">
          <p>
            The numerical evidence behind the earlier conditional-scale, group-calibration and controlled-shift studies (M10 to M12) is restricted. Only the public aggregate summary is shown. Hashes
            identify those artifacts but do not grant access or redistribution rights.
          </p>
        </Banner>
      </section>

      <section className={ui.section} aria-labelledby="h-repro">
        <h2 id="h-repro">Reproducibility levels</h2>
        <div className={ui.grid2}>
          <div className={ui.card}>
            <h3>
              <Chip>Level A</Chip> Public inspection
            </h3>
            <p>Read the code, protocols, reports, manifests and aggregate tables in the public clone, and regenerate this Observatory&apos;s evidence file from them byte for byte.</p>
          </div>
          <div className={ui.card}>
            <h3>
              <Chip>Level B</Chip> Numerical reproduction
            </h3>
            <p>
              Reproduce numerical findings from the original artifacts. Available for the public IID world and the RES-616 and RES-639 studies at the stated tolerance; unavailable for restricted M10 to M12
              evidence. These are access levels, not grades of scientific validity.
            </p>
          </div>
        </div>
      </section>

      <section className={ui.section} aria-labelledby="h-license">
        <h2 id="h-license">Licenses</h2>
        <ul className={ui.list}>
          <li>
            Code and data in the public repository: <strong>MIT</strong>. The Observatory application is part of that repository and MIT licensed.
          </li>
          <li>
            Project-authored documentation (Markdown): <strong>CC BY 4.0</strong>. The generated public dataset requires CC BY 4.0 attribution. Individual manifests govern model, data and result artifacts.
          </li>
          <li>No manuscript, preprint or private artifact is distributed by this site, and none is bundled in its build.</li>
        </ul>
      </section>

      <section className={ui.section} aria-labelledby="h-cite">
        <h2 id="h-cite">How to cite</h2>
        <p>Cite the software repository. There is no article to cite and no DOI has been minted.</p>
        <pre className={ui.eq} style={{ whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", fontSize: "0.85rem" }} data-testid="citation">
{`Powerlifting State Research (software), version 0.1.0.
Powerlifting State Research contributors. MIT license.
${REPO_URL}
Commit ${REVISION}`}
        </pre>
        <p>
          Machine-readable form: <a href={sourceUrl("CITATION.cff")}>CITATION.cff</a>.
        </p>
      </section>

      <section className={ui.section} aria-labelledby="h-build">
        <h2 id="h-build">This build</h2>
        <ul className={ui.list}>
          <li>
            Evidence schema <code>{evidence.schema_version}</code> bound to public revision <code>{REVISION_SHORT}</code> ({evidence.sources.length} hashed sources).
          </li>
          <li>Deployed Observatory commit: {deployed ? <code>{deployed.slice(0, 12)}</code> : "not recorded in this build"}.</li>
        </ul>
      </section>
    </div>
  );
}
