// Public-repository identity for client-side source links, read once from the committed evidence file at build or test
// time and inlined as environment constants. Client components therefore never import (and bundle) the evidence JSON.
import { readFileSync } from "node:fs";

const evidence = JSON.parse(readFileSync(new URL("../data/evidence.v1.json", import.meta.url), "utf8"));
if (!/^[\w.-]+\/[\w.-]+$/.test(evidence.source_repository) || !/^[0-9a-f]{40}$/.test(evidence.source_revision)) {
  throw new Error("evidence.v1.json: invalid source_repository or source_revision");
}
export const SOURCE_ENV = {
  NEXT_PUBLIC_PSR_REPOSITORY: evidence.source_repository,
  NEXT_PUBLIC_PSR_REVISION: evidence.source_revision,
};
