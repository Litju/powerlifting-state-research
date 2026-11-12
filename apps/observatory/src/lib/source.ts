/**
 * Links to tracked files in the public repository at the pinned evidence revision. The two constants are inlined at
 * build time from data/evidence.v1.json (scripts/source-env.mjs), so this module is safe to use in client components
 * without bundling the evidence file.
 */
const REPOSITORY = process.env.NEXT_PUBLIC_PSR_REPOSITORY ?? "";
export const REVISION = process.env.NEXT_PUBLIC_PSR_REVISION ?? "";
export const REVISION_SHORT = REVISION.slice(0, 7);
export const REPO_URL = `https://github.com/${REPOSITORY}`;

/** Permalink to a tracked public file at the pinned revision. */
export function sourceUrl(path: string): string {
  return `${REPO_URL}/blob/${REVISION}/${path}`;
}

export function shortHash(hash: string): string {
  return `${hash.slice(0, 8)}…${hash.slice(-4)}`;
}
