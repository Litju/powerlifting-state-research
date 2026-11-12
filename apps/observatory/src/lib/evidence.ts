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

export { REPO_URL, REVISION, REVISION_SHORT, shortHash, sourceUrl } from "./source";
