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

## Fallbacks

| Condition | Behaviour |
| --- | --- |
| Default | Sticky WebGL stage; camera and layer emphasis follow native scroll; demand rendering, DPR capped at 1.75, paused off screen or in a hidden tab. |
| `prefers-reduced-motion` | Mode `static`: no scroll scrubbing or progress bar; the stage is not sticky; each chapter has its own semantic diagram. User-initiated rotation still works. |
| WebGL unavailable or scene error | Mode `diagram`: SVG diagram with text alternative replaces the canvas. |
| Low-end device (4 or fewer cores, 4 GB or less memory, small coarse-pointer screen) | DPR 1, no antialiasing, coarser curves. `?scene=low` forces it, `?scene=off` forces the diagram for testing. |

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
