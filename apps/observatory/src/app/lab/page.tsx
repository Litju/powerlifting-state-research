import type { Metadata } from "next";
import { LabExplorer } from "@/components/LabExplorer";
import { PageHeader } from "@/components/Ui";
import ui from "@/components/ui.module.css";

export const metadata: Metadata = {
  title: "System lab",
  description: "Interactive C, E and Y equations of the public synthetic capacity and expression law, with a deterministic illustrative simulation.",
};

export default function LabPage() {
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="System model" title="Capacity, expression and observation">
        <p>
          Three different quantities are easy to confuse: what the system could do, what it did on the day, and what was recorded. Move the sliders to see how the law couples them.
        </p>
      </PageHeader>
      <div style={{ marginTop: 32 }}>
        <LabExplorer />
      </div>
    </div>
  );
}
