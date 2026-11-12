import Link from "next/link";
import type { ReactNode } from "react";
import { inverseIllustration } from "@/lib/inverse";
import { ACTS } from "@/lib/story";
import type { StoryEvidence } from "@/lib/story-evidence";
import styles from "./story.module.css";

const sgn = (v: number, d = 3) => `${v < 0 ? "−" : "+"}${Math.abs(v).toFixed(d)}`;

function Takeaway({ children }: { children: ReactNode }) {
  return <p className={styles.takeaway}>{children}</p>;
}

function Eq({ children, label }: { children: ReactNode; label: string }) {
  return (
    <p className={styles.eq} aria-label={label}>
      {children}
    </p>
  );
}

/** The words of each beat. One message per beat; detail lives on the linked routes. */
export function BeatContent({ beatId, evidence }: { beatId: string; evidence: StoryEvidence }): ReactNode {
  const r = evidence.ridge.parents;
  const s = evidence.scale.parents;
  switch (beatId) {
    case "observe":
      return (
        <>
          <p className={styles.kicker}>
            <span className={styles.numeral}>Act I</span> The observation
          </p>
          <p className={styles.display}>All we ever see is&nbsp;Y.</p>
          <p className={styles.lede}>
            Thirty-two weekly strength assessments of one simulated athlete. Each point is a single noisy measurement. Test the same athlete again and the score would differ.
          </p>
          <p className={styles.fine}>Illustration from the public simulator. No real athlete, no measured data.</p>
        </>
      );
    case "question":
      return (
        <>
          <p className={styles.lede}>The model that produced these points is not visible in them. The whole project comes down to one question:</p>
          <h1 className={styles.question}>What can noisy observations of strength performance actually tell us about a hidden system?</h1>
          <p>Each measurement has a band of about ±10% around it. That band is the limit on what the data can tell us, and everything that follows depends on it.</p>
          <nav aria-label="The six acts" className={styles.toc}>
            <ol>
              {ACTS.map((a) => (
                <li key={a.id}>
                  <a href={`#${a.id}`}>
                    <span className={styles.tocNum}>{a.numeral}</span> {a.kicker}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        </>
      );
    case "capacity":
      return (
        <>
          <p>
            <strong>Latent capacity C</strong> adapts slowly as training accumulates, over weeks rather than days. A coach would want to know it, but no measurement contains it.
          </p>
          <Eq label="C equals B times one plus g A times A">
            C = B (1 + g<sub>A</sub> A)
          </Eq>
          <Takeaway>C is the target nobody can observe directly.</Takeaway>
        </>
      );
    case "suppression":
      return (
        <>
          <p>
            <strong>Expressed performance E</strong> is capacity reduced by <strong>suppression S</strong>. S is a fast, temporary effect of recent work that builds and fades within days. In the 3D view, S is the depth axis that pulls E away from C.
          </p>
          <Eq label="E equals C times one minus g S times S">
            E = C (1 − g<sub>S</sub> S)
          </Eq>
          <Takeaway>Performance on the day is not capacity.</Takeaway>
        </>
      );
    case "noise":
      return (
        <>
          <p>
            <strong>Each observation Y</strong> is E plus measurement noise. Every assessment passes through E. Even a perfect, noiseless inversion therefore recovers E, not C. In the noiseless condition of study G1, the last observation&apos;s squat expression error was zero, while capacity RMSE was still {Number(evidence.g1.kg).toFixed(2)} kg.
          </p>
          <Eq label="Y equals E times one plus epsilon">Y = E (1 + ε)</Eq>
          <Takeaway>Observations constrain E. They reach C only indirectly.</Takeaway>
        </>
      );
    case "inverse": {
      const inv = inverseIllustration();
      return (
        <>
          <p>
            Recovering the parameters from Y means running the model backwards, which is an <em>inverse problem</em>. Even in this toy example, a coarse search over {inv.gridSize.toLocaleString("en")} parameter settings finds{" "}
            <strong>{inv.accepted}</strong> that fit the 32 points within {Math.round((inv.tolerance - 1) * 100)}% of the generating model&apos;s own error.
          </p>
          <p>
            Those fits disagree about what is hidden: capacity on day 223 ranges from {inv.cRange[0].toFixed(0)} to {inv.cRange[1].toFixed(0)} kg. The value that actually generated the data is {inv.truth.cLast.toFixed(0)} kg.
          </p>
          <p className={styles.fine}>A demonstration inside the illustrative simulation, not a result about the research model.</p>
        </>
      );
    }
    case "g2":
      return (
        <>
          <p>
            Study <strong>G2</strong> tested this inverse problem at scale for the full 16-parameter model. At native noise only {evidence.g2.convergedNative[0]} of {evidence.g2.convergedNative[1]} maximum-likelihood starts converged. Local rank is {evidence.g2.localRank[0]}/{evidence.g2.localRank[1]}, but the problem is badly conditioned.
          </p>
          <p className={styles.code}>{evidence.g2.disposition}</p>
          <Takeaway>Identification is unsupported on the current evidence. That is not a proof that it is impossible.</Takeaway>
        </>
      );
    case "boundary":
      return (
        <>
          <p>
            Instead of recovering hidden physiology, forecast the next <strong>observable</strong> assessment. A model sees each history up to <strong>day 223</strong>, a declared training plan starts at day 224, and the model predicts assessments that have not happened yet.
          </p>
          <Takeaway>Y can be checked against what happens next. C cannot.</Takeaway>
        </>
      );
    case "ridge":
      return (
        <>
          <p>
            Study <strong>RES-616</strong> compared a linear Ridge model with a GRU neural network on two independent test sets, scored by CRPS in kg (lower is better). The GRU clearly beat simply repeating the last assessment, but it was <em>worse</em> than Ridge on both test sets:
          </p>
          <ul className={styles.facts}>
            <li>
              TEST_A {sgn(r.TEST_A.diff.diff)} kg <span>[{sgn(r.TEST_A.diff.lo)}, {sgn(r.TEST_A.diff.hi)}]</span>
            </li>
            <li>
              TEST_B {sgn(r.TEST_B.diff.diff)} kg <span>[{sgn(r.TEST_B.diff.lo)}, {sgn(r.TEST_B.diff.hi)}]</span>
            </li>
          </ul>
          <Takeaway>The more complex model did not forecast better.</Takeaway>
        </>
      );
    case "scale":
      return (
        <>
          <p>
            CRPS scores the whole predictive distribution, not just its centre. Study <strong>RES-639</strong> kept the Ridge forecast fixed and changed only how its uncertainty was set:
          </p>
          <dl className={styles.defs}>
            <div>
              <dt>B_GROUP</dt>
              <dd>one spread per group</dd>
            </div>
            <div>
              <dt>B_MAG</dt>
              <dd>spread that depends on the forecast magnitude</dd>
            </div>
            <div>
              <dt>H_HISTORY</dt>
              <dd>B_MAG plus {evidence.scale.historyFeatures} participant-visible history features</dd>
            </div>
          </dl>
        </>
      );
    case "history":
      return (
        <>
          <p>
            You might expect more history to sharpen the uncertainty. It did not. Compared with B_MAG, H_HISTORY was slightly <em>worse</em> on both test sets:
          </p>
          <ul className={styles.facts}>
            <li>
              TEST_A {sgn(s.TEST_A.historyVsMag.diff, 4)} kg <span>[{sgn(s.TEST_A.historyVsMag.lo, 4)}, {sgn(s.TEST_A.historyVsMag.hi, 4)}]</span>
            </li>
            <li>
              TEST_B {sgn(s.TEST_B.historyVsMag.diff, 4)} kg <span>[{sgn(s.TEST_B.historyVsMag.lo, 4)}, {sgn(s.TEST_B.historyVsMag.hi, 4)}]</span>
            </li>
          </ul>
          <p className={styles.fine}>
            B_MAG beat B_GROUP, but the two models also set their spread with different fitting procedures. That gain therefore cannot be attributed to forecast magnitude alone.
          </p>
          <Takeaway>Adding information did not improve the uncertainty estimate.</Takeaway>
        </>
      );
    case "ledger":
      return (
        <>
          <div className={styles.ledger}>
            <div>
              <h3>Supported</h3>
              <ul>
                <li>Forward simulation and local sensitivity of the public law.</li>
                <li>Noiseless observations recover E, not C (G1).</li>
                <li>Ridge forecast the next Y better than the tested GRU (RES-616).</li>
                <li>B_MAG beat the tested H_HISTORY (RES-639).</li>
              </ul>
            </div>
            <div>
              <h3>Unsupported</h3>
              <ul>
                <li>Recovering all 16 hidden parameters (G2), on current evidence.</li>
                <li>Attributing B_MAG’s gain over B_GROUP to forecast magnitude alone.</li>
                <li>General robustness beyond two named within-support shifts.</li>
              </ul>
            </div>
            <div>
              <h3>Not established</h3>
              <ul>
                <li>Any real-athlete validity. Every number here is synthetic.</li>
                <li>Physiological, causal or coaching claims.</li>
                <li>GRU training-seed stability (not tested).</li>
                <li>Independent peer review. The manuscript is in private preparation and its public release is pending.</li>
              </ul>
            </div>
          </div>
          <Takeaway>Negative results narrow what can honestly be claimed. They are reported here as clearly as the positive ones.</Takeaway>
          <ul className={styles.next} aria-label="Continue exploring">
            <li>
              <Link href="/journey">
                <span>Research journey</span> Every stage, with its limits and sources
              </Link>
            </li>
            <li>
              <Link href="/forecast">
                <span>Forecasting lab</span> CRPS, NLL, calibration and subgroups
              </Link>
            </li>
            <li>
              <Link href="/benchmarks">
                <span>Benchmarks</span> What may be compared, and what may not
              </Link>
            </li>
            <li>
              <Link href="/lab">
                <span>System lab</span> Move the law’s parameters yourself
              </Link>
            </li>
            <li>
              <Link href="/publication">
                <span>Open science</span> Sources, licences and how to cite
              </Link>
            </li>
          </ul>
        </>
      );
    default:
      return null;
  }
}
