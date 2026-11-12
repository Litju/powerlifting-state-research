import Link from "next/link";
import { Story } from "@/components/story/Story";
import { Stat } from "@/components/Ui";
import ui from "@/components/ui.module.css";
import story from "@/components/story/story.module.css";
import { evidence } from "@/lib/evidence";
import { signed } from "@/lib/format";

const EXPLORE = [
  { href: "/lab", title: "System lab", text: "Move the time constants and gains of the public law and watch C, E and Y respond. An illustrative demonstration." },
  { href: "/journey", title: "Research journey", text: "Nine stages from observation inversion to history-conditioned uncertainty, with limits and sources." },
  { href: "/benchmarks", title: "Benchmarks", text: "Nine registry entries, a 22-identity model panel, and why different worlds are never ranked together." },
  { href: "/forecast", title: "Forecasting lab", text: "CRPS, NLL, coverage and paired differences with intervals for Ridge, GRU and three uncertainty models." },
  { href: "/publication", title: "Publication", text: "Manuscript under review, release pending. Public material, licenses and how to cite the software." },
  { href: "/about", title: "About and limits", text: "Methods, non-claims, accessibility and the rights boundary." },
];

export default function HomePage() {
  const p616 = evidence.studies.find((s) => s.id === "RES-616")!.primary;
  const p639 = evidence.studies.find((s) => s.id === "RES-639")!.primary;
  return (
    <>
      <Story />
      <div className={[ui.page, story.afterStory].join(" ")}>
        <section aria-labelledby="h-glance">
          <p className={ui.eyebrow}>Findings at a glance</p>
          <h2 id="h-glance">Two honest negatives on the observed assessment</h2>
          <p className={ui.lede}>Paired macro CRPS differences in kilograms, control scenario, first model minus second; positive means the first model is worse. Synthetic data only.</p>
          <div className={ui.grid3} style={{ marginTop: 24 }}>
            <Stat value={signed(p616.TEST_A!.diff, 4)} label="GRU minus Ridge, TEST_A (RES-616). Ridge is better." />
            <Stat value={signed(p616.TEST_B!.diff, 4)} label="GRU minus Ridge, TEST_B (RES-616). Ridge is better." />
            <Stat value={signed(p639.TEST_A!.diff, 6)} label="H_HISTORY minus B_MAG, TEST_A (RES-639). Histories did not help." />
            <Stat value={signed(p639.TEST_B!.diff, 6)} label="H_HISTORY minus B_MAG, TEST_B (RES-639). Histories did not help." />
          </div>
        </section>
        <section className={ui.section} aria-labelledby="h-explore">
          <h2 id="h-explore">Explore</h2>
          <div className={ui.grid3}>
            {EXPLORE.map((e) => (
              <div className={ui.card} key={e.href}>
                <h3>
                  <Link href={e.href}>{e.title}</Link>
                </h3>
                <p>{e.text}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
