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
      <PageHeader eyebrow="Research journey" title="Nine stages, in the order they were done">
        <p>
          Each stage asked one question about a hidden synthetic system observed through noise. Most answers are bounded or negative, and they are reported that way. Open a stage for the verified
          statement, its limits, the hashed source and its lineage.
        </p>
      </PageHeader>
      <JourneyExplorer data={{ facts: evidence.facts, studies: evidence.studies, sources: evidence.sources }} />
    </div>
  );
}
