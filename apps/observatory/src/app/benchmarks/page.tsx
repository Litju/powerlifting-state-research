import type { Metadata } from "next";
import { FrontierExplorer, RankingNotice, RegistryExplorer, WorldsSeparated } from "@/components/BenchmarksExplorer";
import { PageHeader } from "@/components/Ui";
import ui from "@/components/ui.module.css";
import { evidence } from "@/lib/evidence";

export const metadata: Metadata = {
  title: "Benchmarks and comparison",
  description: "The nine-entry benchmark registry, the 22-identity public-native model panel, and why incomparable worlds are kept apart.",
};

export default function BenchmarksPage() {
  const historical = evidence.registry.filter((r) => r.identity_authority === "HISTORICAL_PROJECTION").length;
  const publicNative = evidence.registry.length - historical;
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="Benchmarks and comparison" title="Worlds, targets and what may be compared">
        <p>A benchmark fixes a world, a target, a forecast origin, the visible information and the evaluation. Change any of them and numbers stop being comparable.</p>
      </PageHeader>
      <RankingNotice />
      <section className={ui.section} aria-labelledby="h-worlds">
        <h2 id="h-worlds">Three incomparable evidence worlds</h2>
        <WorldsSeparated historical={historical} publicNative={publicNative} />
      </section>
      <section className={ui.section} aria-labelledby="h-registry">
        <h2 id="h-registry">Registry of nine benchmark entries</h2>
        <p>
          Eight reconstructed historical specimens and one independent public-native variant. The historical projection and the executable native variant have separate identities because their
          sampling designs differ.
        </p>
        <RegistryExplorer registry={evidence.registry} />
      </section>
      <section className={ui.section} aria-labelledby="h-panel">
        <h2 id="h-panel">The public-native model panel</h2>
        <p>
          Seven learner families, 22 saved fit or ensemble identities, three latent capacity-change targets, all on the public IID realization. The table is the unmodified output of the comparator
          frontier file.
        </p>
        <FrontierExplorer frontier={evidence.frontier} />
      </section>
    </div>
  );
}
