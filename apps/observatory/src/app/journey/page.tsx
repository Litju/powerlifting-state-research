import type { Metadata } from "next";
import { JourneyExplorer } from "@/components/JourneyExplorer";
import { PageHeader } from "@/components/Ui";
import ui from "@/components/ui.module.css";
import { evidence } from "@/lib/evidence";

export const metadata: Metadata = {
  title: "Research journey",
  description: "From observation inversion (G1) to history-conditioned uncertainty (RES-639): findings, negative results, statistical limits and source lineage.",
};

export default function JourneyPage() {
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="Research journey" title="Nine stages, and what each one did not show">
        <p>
          The program asks what can be inferred about a hidden synthetic system from noisy observations. Most conclusions are bounded or negative, and they are reported that way. Choose a stage to read
          the finding, its limits and its verified source.
        </p>
      </PageHeader>
      <div style={{ marginTop: 32 }}>
        <JourneyExplorer data={{ facts: evidence.facts, studies: evidence.studies, sources: evidence.sources }} />
      </div>
    </div>
  );
}
