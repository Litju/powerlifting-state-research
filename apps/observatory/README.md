# PSR Observatory

An interactive, evidence-bound front end for the public Powerlifting State Research repository: a scroll-linked 3D state-space story, a deterministic illustrative system lab, the research journey, benchmark and forecasting explorers, and an honest publication page. Every number is read from a SHA-256-bound aggregate table; nothing is fitted or invented in the browser, and all systems are synthetic.

Stack: Next.js 16 (App Router, prerendered), React 19, strict TypeScript, CSS Modules, three + @react-three/fiber + @react-three/drei (lazy, `ssr: false`, demand frameloop, capped DPR), Motion for React (`useScroll`/`useTransform`), hand-rolled accessible SVG charts, zod, Vitest + React Testing Library, Playwright + axe. No third-party requests, fonts or telemetry.

## Run locally

Requires Node 22.12 or newer. The evidence build reads the repository root two levels up, so use a full clone.

```sh
cd apps/observatory
npm ci
npm run dev          # http://localhost:3000
npm run lint && npm run typecheck && npm test
npm run build        # runs the evidence check first (prebuild)
npm run check:bundle # scans build output for paper/private/secret artifacts
npx playwright install chromium
npx playwright test  # starts `next start` on :3100; projects: desktop, mobile, no-webgl
```

## Evidence

`npm run evidence` runs `scripts/build-evidence.mjs`, which reads tracked public sources in the repository root, recomputes macro CRPS/NLL, cross-checks documented values and manifest hashes, validates `scripts/evidence-schema.mjs` and writes `data/evidence.v1.json`. `npm run evidence:check` (also the `prebuild` step and a CI step) fails if the committed file differs by a single byte. The build fails on a missing or contradicted source and never falls back to invented values. See `docs/observatory-runbook.md`.

## Rights boundary

The private manuscript, its PDF, LaTeX, evidence archive and declarations are under a publication hold and are never copied, linked or bundled. `/publication` states "Manuscript in private preparation — public release pending.", has no DOI, no peer-review claim and no download. Restricted M10 to M12 evidence appears only as the public aggregate summary and is labelled as such.
