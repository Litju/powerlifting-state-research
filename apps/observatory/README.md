# PSR Observatory

The interactive, evidence-bound companion to the public Powerlifting State Research repository. It tells the research as one story: **what can noisy observations of strength performance actually tell us about a hidden system?** Every number is read from a SHA-256-bound aggregate evidence file. Nothing is fitted or invented in the browser, and every system shown is synthetic.

## What is in it

| Route | Purpose |
| --- | --- |
| `/` | Six-act story, twelve scroll beats. I the observation (only noisy Y) · II the hidden system (C, then E and suppression, then noise) · III the identification problem (an illustrative inverse problem, then the real G2 counts) · IV forecasting (information boundary, then RES-616 Ridge vs GRU) · V predictive uncertainty (RES-639 B_GROUP → B_MAG → H_HISTORY) · VI what the evidence supports. |
| `/journey` | The nine research stages in the order they were carried out, each with a one-line verdict and expandable statement, limits, hashed sources and lineage (`/journey#G2` deep links). |
| `/forecast` | Conclusion first, then the primary forest plots, then filters (study, parent, lift, scenario, plan/horizon) above Accuracy · Likelihood · Calibration · Shifts tabs. |
| `/benchmarks` | What makes two numbers comparable, then the three evidence worlds, the nine-entry registry and the 22-identity model panel, one target at a time. |
| `/lab` | A deterministic illustrative simulator of the public law; labelled demonstration, not evidence. |
| `/publication`, `/about` | Open-science material, licences, citation, methods and limits. The manuscript is in private preparation and its public release is pending; none of it is served. |

Conceptual visuals carry an "Illustrative simulation · not measured data" badge. Evidence panels carry "Evidence · aggregate study results" with the source path and sha256, a parent switch, hover/focus readouts and a data table.

## Architecture

- **Layout contract.** One fixed 56 px header (`--header-h`). On wide, tall screens without reduced motion, the story is a two-column grid: a natively scrolling reading column and a sticky stage below the header. The stage has three reserved rows (act index and badge, field, controls), so nothing overlays the text. Otherwise every beat carries its own inline figure or panel and there is no sticky element. Safe zones are declared with `data-zone` and asserted on rendered boxes by `tests/e2e/layout.spec.ts`.
- **Choreography.** `src/lib/story.ts` defines acts and beats. `sceneState(position)` is a pure, unit-tested function from scroll position to camera pose, layer emphasis, progressive drawing and evidence-panel cross-fades.
- **3D.** three + @react-three/fiber + @react-three/drei, requested only in stage mode on first input or idle. Rendering is on demand with DPR capped at 1.75. Labels are projected DOM nodes. Phones never download the three.js chunk.
- **Evidence.** `scripts/build-evidence.mjs` regenerates `data/evidence.v1.json` from tracked public sources. `src/lib/story-evidence.ts` builds the small server-side payload the story needs and throws on any missing record. Client components take source permalinks from build-time constants (`src/lib/source.ts`), never from the evidence file.
- **Design system.** CSS Modules with tokens in `src/app/globals.css`. Newsreader and IBM Plex are fetched at build by `next/font` and self-hosted, so the site makes no runtime third-party requests and no font files are committed. Mark palettes pass a colour-vision and contrast validator. Text never uses series colours.

Stack: Next.js 16 (App Router, prerendered), React 19, strict TypeScript, Motion for React, hand-rolled accessible SVG charts, zod, Vitest + React Testing Library, Playwright + axe. No telemetry.

## Run locally

Requires Node 22.12 or newer. The evidence build reads the repository root two levels up, so use a full clone.

```sh
cd apps/observatory
npm ci
npm run dev          # http://localhost:3000
npm run lint && npm run typecheck && npm test
npm run build        # runs the evidence check first (prebuild)
npm start            # production server on http://localhost:3000
npm run check:bundle # scans build output for paper/private/secret artifacts
npx playwright install chromium
npx playwright test  # starts `next start` on :3100; projects: desktop, mobile, no-webgl
```

Useful query flags: `?scene=off` forces the SVG stage, `?scene=low` forces low-end rendering.

## Evidence

`npm run evidence` reads tracked public sources in the repository root, recomputes macro CRPS/NLL, cross-checks documented values and manifest hashes, validates `scripts/evidence-schema.mjs` and writes `data/evidence.v1.json`. `npm run evidence:check` (also `prebuild` and a CI step) fails if the committed file differs by one byte. See `docs/observatory-runbook.md` for refresh steps, fallbacks, the layout contract, and the visual QA and Lighthouse record.

## Rights boundary

The private manuscript, its PDF, LaTeX, evidence archive and declarations are under a publication hold and are never copied, linked or bundled. `/publication` states "Manuscript in private preparation — public release pending.", with no DOI, no peer-review claim and no download. Restricted M10 to M12 evidence appears only as the public aggregate summary and is labelled as such.
