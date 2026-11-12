#!/usr/bin/env node
// Fails if the production build output contains paper/manuscript artifacts, private references or secrets.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const roots = [".next/static", ".next/server/app", "public"].filter((p) => {
  try {
    return statSync(p).isDirectory();
  } catch {
    return false;
  }
});
if (roots.length === 0) {
  console.error("bundle check FAILED: no build output found; run `npm run build` first");
  process.exit(1);
}
const forbiddenExt = new Set([".pdf", ".tex", ".zip", ".bib", ".docx", ".pt", ".pth", ".safetensors", ".ckpt", ".npz", ".parquet"]);
const forbiddenText = [
  /powerlifting-state-research-paper/i,
  /manuscript\.pdf/i,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /\bgh[pousr]_[A-Za-z0-9_]{20,}/,
  /\bsk-[A-Za-z0-9_-]{20,}/,
  /\bAKIA[0-9A-Z]{16}\b/,
  /\/home\/[a-z0-9_-]+\//i,
];
const problems = [];
let files = 0;
function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else {
      files += 1;
      if (forbiddenExt.has(extname(entry.name).toLowerCase())) problems.push(`forbidden file type: ${full}`);
      if (/\.(js|css|html|rsc|json|txt|svg|map)$/.test(entry.name) && !entry.name.endsWith(".map")) {
        const text = readFileSync(full, "utf8");
        for (const re of forbiddenText) if (re.test(text)) problems.push(`${re}: ${relative(".", full)}`);
      }
    }
  }
}
roots.forEach(walk);
if (problems.length) {
  console.error(`bundle check FAILED:\n${problems.join("\n")}`);
  process.exit(1);
}
console.log(`bundle check OK: ${files} files scanned, no paper, private or secret artifacts`);
