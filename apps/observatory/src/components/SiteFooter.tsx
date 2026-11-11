import Link from "next/link";
import { REPO_URL, REVISION, REVISION_SHORT } from "@/lib/evidence";
import styles from "./shell.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <div>
          <strong>Synthetic systems only.</strong>
          <p>
            Every number here describes simulated assessments in declared synthetic worlds. Nothing is athlete data, a coaching
            prescription, a physiological measurement or evidence about real people.
          </p>
        </div>
        <div>
          <strong>Evidence</strong>
          <p>
            Bound to the public repository at{" "}
            <a href={`${REPO_URL}/tree/${REVISION}`}>
              main@<code>{REVISION_SHORT}</code>
            </a>
            . Code and data are MIT; documentation is CC BY 4.0. No analytics or third-party telemetry.
          </p>
        </div>
        <div>
          <strong>Status</strong>
          <p>
            Manuscript under review, release pending. No DOI, no peer-review claim. See <Link href="/publication">Publication</Link>.
          </p>
        </div>
      </div>
    </footer>
  );
}
