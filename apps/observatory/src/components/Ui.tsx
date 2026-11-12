import type { ReactNode } from "react";
import { shortHash, sourceUrl } from "@/lib/source";
import styles from "./ui.module.css";

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header>
      <p className={styles.eyebrow}>{eyebrow}</p>
      <h1 style={{ fontSize: "clamp(2rem, 4.6vw, 3.4rem)" }}>{title}</h1>
      {children ? <div className={styles.lede}>{children}</div> : null}
    </header>
  );
}

export function Banner({ kind = "warn", title, children }: { kind?: "warn" | "info" | "restricted"; title?: string; children: ReactNode }) {
  const cls = [styles.banner, kind === "info" ? styles.bannerInfo : kind === "restricted" ? styles.bannerRestricted : ""].join(" ");
  return (
    <aside className={cls} role="note" aria-label={title}>
      {title ? (
        <p>
          <strong>{title}</strong>
        </p>
      ) : null}
      {children}
    </aside>
  );
}

export function Chip({ kind, children }: { kind?: "C" | "E" | "Y" | "restricted"; children: ReactNode }) {
  const cls = [styles.chip, kind === "C" ? styles.chipC : kind === "E" ? styles.chipE : kind === "Y" ? styles.chipY : kind === "restricted" ? styles.chipRestricted : ""].join(" ");
  return <span className={cls}>{children}</span>;
}

export const TARGET_NAMES = { C: "target C (latent capacity)", E: "target E (expressed performance)", Y: "target Y (observed noisy assessment)" } as const;

export function TargetChip({ target }: { target: "C" | "E" | "Y" }) {
  return <Chip kind={target}>{TARGET_NAMES[target]}</Chip>;
}

export function Provenance({ path, sha, studyId, extra }: { path: string; sha: string; studyId?: string; extra?: ReactNode }) {
  return (
    <dl className={styles.prov} aria-label="Evidence provenance">
      <div>
        <dt>source</dt>
        <dd>
          <a href={sourceUrl(path)}>{path}</a>
        </dd>
      </div>
      <div>
        <dt>sha256</dt>
        <dd title={sha}>{shortHash(sha)}</dd>
      </div>
      {studyId ? (
        <div>
          <dt>study</dt>
          <dd>{studyId}</dd>
        </div>
      ) : null}
      {extra}
    </dl>
  );
}

export function Stat({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div className={styles.stat}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  );
}
