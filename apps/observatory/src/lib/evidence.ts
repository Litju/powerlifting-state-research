import type { z } from "zod";
import type { Evidence as EvidenceSchema } from "../../scripts/evidence-schema.mjs";
import raw from "../../data/evidence.v1.json";

export type Evidence = z.infer<typeof EvidenceSchema>;
export type ScoreRecord = Evidence["scores"][number];
export type ContrastRecord = Evidence["contrasts"][number];
export type ShiftRecord = Evidence["shifts"][number];
export type GroupCellRecord = Evidence["group_cells"][number];
export type GroupSummaryRecord = Evidence["group_summaries"][number];
export type ScaleCoverageRecord = Evidence["scale_coverage"][number];
export type PitRecord = Evidence["pit"][number];
export type FrontierRecord = Evidence["frontier"][number];
export type RegistryRecord = Evidence["registry"][number];
export type FactRecord = Evidence["facts"][number];
export type StudyRecord = Evidence["studies"][number];

export const evidence = raw as unknown as Evidence;

export const REPO_URL = `https://github.com/${evidence.source_repository}`;
export const REVISION = evidence.source_revision;
export const REVISION_SHORT = REVISION.slice(0, 7);

/** Permalink to a tracked public file at the pinned revision (main@41191d6). */
export function sourceUrl(path: string): string {
  return `${REPO_URL}/blob/${REVISION}/${path}`;
}

export function shortHash(hash: string): string {
  return `${hash.slice(0, 8)}…${hash.slice(-4)}`;
}
