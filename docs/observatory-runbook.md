# PSR Observatory runbook

The Observatory lives in [`apps/observatory`](../apps/observatory) and does not modify the Python package, frozen results or study files. It is MIT licensed code with CC BY 4.0 documentation, like the rest of the repository.

## Local development

Node 22.12 or newer, full clone of this repository.

```sh
cd apps/observatory
npm ci
npm run dev
npm run lint && npm run typecheck && npm test && npm run build && npm run check:bundle
```

End-to-end tests: `npx playwright install chromium` (add `--with-deps` on Linux with sudo), then `npx playwright test`. The `no-webgl` project launches Chromium with GPU and WebGL disabled. On a machine without system libraries for Chromium (for example `libnspr4`, `libnss3`, `libasound2`), install them or point `LD_LIBRARY_PATH` at extracted copies.

## Evidence refresh

1. Update the tracked public sources in the repository root through the normal research process (never in the app).
2. `cd apps/observatory && npm run evidence`. Read any failure message: it names the missing source or the contradicted number or hash.
3. Commit the regenerated `data/evidence.v1.json` together with the source change. `npm run evidence:check` and CI require byte-identical regeneration.
4. When the pinned public revision changes, update `SOURCE_REVISION` in `scripts/evidence-schema.mjs`, which drives every GitHub permalink.

New facts must be added with `verified_strings` that occur verbatim in their source document. Do not add numbers by hand.

## Landing story and layout contract

The home page is one narrative in six acts (twelve beats), defined in `src/lib/story.ts`. Each beat has one message and one stage state; `sceneState(position)` is a pure function of the scroll position (unit tested), and every number comes from `buildStoryEvidence()` in `src/lib/story-evidence.ts`, which throws on any missing record. The 127 H_HISTORY summaries are a cited constant checked against `docs/studies/history-conditional-uncertainty.md` by a unit test. Conceptual visuals carry an "Illustrative simulation · not measured data" badge; evidence panels carry "Evidence · aggregate study results" with source path and sha256.

Safe zones (`data-zone` attributes), never overlapping, asserted on rendered bounding boxes by `tests/e2e/layout.spec.ts` at 1440×900, 1280×800, 768×1024, 390×844 and 360×800:

| Zone | Where |
| --- | --- |
| `header` | Sticky global navigation, exactly `--header-h` (56 px), one row at every width; a disclosure menu below 1024 px. |
| `text` | Reading column, one block per beat. |
| `stage-bar` | Act index with progress line and the illustration/evidence badge (stage row 1). |
| `stage-field` | 3D scene, fallback figure or evidence panel (stage row 2). |
| `stage-controls` | Layer focus, zoom/reset and hover readout (stage row 3). |
| `inline-visual` | Per-beat figure or evidence panel in the inline layout. |

The sticky split stage is used only for `(min-width: 960px) and (min-height: 600px) and (prefers-reduced-motion: no-preference)`; the same query appears in `Story.tsx` (`STAGE_QUERY`) and `story.module.css`, so server HTML already has the final layout. Otherwise there is no sticky element in the story at all.

## Fallbacks

| Condition | Mode | Behaviour |
| --- | --- | --- |
| Wide and tall viewport, WebGL available | `stage-webgl` | Sticky split stage; camera, layers and evidence panels follow native scroll; three.js is requested on first input or idle; demand rendering, DPR capped at 1.75, no frames off screen. |
| Wide viewport, WebGL unavailable, scene error or `?scene=off` | `stage-figure` | Same stage with the per-beat SVG figure (text alternative included) instead of the canvas. |
| Phones, tablets in portrait, short windows, `prefers-reduced-motion` | `inline` | Vertical story; each beat carries its own SVG figure or evidence panel; no sticky stage; the three.js chunk is never downloaded (`window.__THREE__` stays undefined, asserted in E2E). |
| Low-end device (4 or fewer cores, 4 GB or less memory, small coarse-pointer screen) or `?scene=low` | `stage-webgl` | DPR 1, no antialiasing, coarser curves. |

## Visual QA and performance record (RES-642 redesign)

Rendered audit before the redesign (commit `3bb9b76`): 36 (1440×900), 36 (1280×800), 49 (768×1024), 55 (390×844) and 60 (360×800) box intersections across 15 scroll checkpoints between story cards, legend, scene controls, progress bar and header; the header wrapped to 200 px at 768 px; `/forecast` and `/publication` were 531 px and 595 px wide on a 390 px phone, hidden by `body { overflow-x: hidden }`. After: zero intersections at every viewport and beat, no unclipped overflow on any route, header 56 px everywhere.

Lighthouse 12.8.2, local production build (`next start`), headless Chromium 1254, default mobile preset (simulated slow 4G, 4× CPU throttling), three runs per route; performance / accessibility / best practices / SEO:

| Route | Redesign, before font trim (perf) | Redesign, final (perf, 3 runs) | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | 85, 79, 85 | 91, 91, 89 | 100 | 100 | 100 | 2.4 s | 0 |
| `/journey` | 85, 88 (one run failed: NO_NAVSTART) | 96, 86, 85 | 100 | 100 | 100 | 2.4–3.1 s | 0.031 |
| `/forecast` | 85, 85, 86 | 90, 91, 92 | 100 | 100 | 100 | 2.5–2.7 s | 0.053 |
| `/benchmarks` | 87, 88, 85 | 88, 96, 97 | 100 | 100 | 100 | 2.4 s | 0 |
| `/` desktop preset | | 99 | 100 | 100 | 100 | 0.7 s | 0.043 |

The pre-redesign build was previously reported at 73–88 (mobile home); those runs were not repeated here. The decisive optimisation was the display serif: the variable optical-size and italic files (274 KB, preloaded) delayed first render; it now ships two static weights without preload. Client source links no longer import the 1.2 MB evidence file (`src/lib/source.ts` with build-time constants). Local lab numbers vary by several points between runs; they are not field data.

## Vercel settings (deployment is done outside this repository)

- Framework preset: Next.js. Root directory: `apps/observatory`.
- Install command: `npm ci`. Build command: `npm run build`. Output: default (`.next`).
- Node.js version: 22.x.
- "Include source files outside of the Root Directory in the Build Step" must stay enabled, because the evidence build reads `results/`, `docs/` and `artifacts/` at the repository root.
- Environment variables: none required. Optional `NEXT_PUBLIC_SITE_URL` sets the canonical metadata base. No secrets, no analytics.
- Security headers and the Content-Security-Policy are set in `next.config.mjs` and require no dashboard setting.

Deployed revision record (fill in after deployment):

| Field | Value |
| --- | --- |
| Vercel project | `psr-observatory`, id `prj_BDvUsRLFmOOacv3htymZ1eATe3gv`, team `julitocrztuga-2084s-projects` (`team_1ectqIpJs0Z1LTgNra873SqP`), linked to `Litju/powerlifting-state-research`, production branch `main` |
| Production URL | _pending_ |
| Deployed commit | _pending_ |
| Verified on | _pending_ |
