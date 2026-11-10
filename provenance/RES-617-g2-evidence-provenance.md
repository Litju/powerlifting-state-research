# RES-617 G2 evidence provenance and pointer correction

Read-only verification performed for the [G2 identifiability decision](../docs/studies/g2-identifiability-decision.md). No optimizer, fit, profile, simulation, cohort or model call was run. Verification consisted of SHA-256 hashing and reading preserved files. The restricted bundles themselves are not copied into this repository; only identities and aggregate counts appear here.

## Verified identities

| Evidence | Identity (SHA-256) | Check | Result |
| --- | --- | --- | --- |
| RES-592 primary bundle index | `5f5d3fefc21aae9fb362b2d0fc3b1df441ed8ca69160fcd88745aa07fd678c67` | hash of `bundle-sha256.json` equals the directory name; every indexed member rehashed | 334 members, 0 mismatches |
| RES-592 report | `be4fd26a9719c794751c76e79428d5e262df9c5b1337252566a72e786bc7e8e4` | hash of `results/report.md` | matches the RES-596 evidence matrix |
| RES-592 protocol realization | `ce80188fc908e3d715a1996c0064520133d32913aa449dd3a5243e4cb1dffb63` | read from the bundle and RES-596 index | consistent |
| RES-592 compute-rescue bundle index | `90fd1b3549f20799d6fb1fc2176cb5472026b19458cb86dd26d737e296c13232` | index hash equals directory name; members rehashed | 36 members, 0 mismatches |
| RES-592 rescue report | `59e0703b93b3b8a0ccf0ef559862b1b25b70b7d4f19bb63cbfa96070defe4410` | hash of `results/report.md` | matches the RES-596 evidence matrix |
| RES-557 final-integration bundle index | `82503f22e9d9aa7069b40a7bb5ce91180ecbbfc9810aba5bdfc76f0dab1b3bb5` | index hash and all members rehashed; archive hash compared with the seal receipt (`29490fd7c22feaeb834fa4f462240862e35bfb08d6ec9110508ffadbeaf337ee`) | 674 members, 0 mismatches; archive hash matches |
| RES-596 synthesis | report `91edf4437a10cec7dc4ffaaa5e2f6575b2e14e35bef39875e8347475c3f8247d`, evidence matrix `8297f0b8660fefd0f7ba4d58a75c667dc252cf6426f5f7e59715d6375d836b84`, source index `255c3549bd546bfa5e0cbd024bb6c996a018e84103c69b64ff1d68cb8bc22005` | file hashes recorded | G2 rows marked VERIFIED there; not independently recomputed |
| RES-289 public study | `psr:study:target-sufficient-structural-reconstruction-public-native@1.0.0~12aafcbac716`, realization `sha256:345de0028b7beeefdc355bf7112565bad2d5675e5bbed3a5c5901371436b5af1` | public repository files; covered by the repository integrity and release-freeze checks | unchanged |

The original source commit named by the RES-592 bundle is `b751cf4c9d44301b03861127ed94158d7c93fa3a`. Rights: the RES-592 package is private synthetic analysis with no new redistribution grant, so this repository records identities and aggregate findings only.

## Linear pointer discrepancy (preserved, not rewritten)

The RES-592 result comment of 2026-11-05 cites the primary bundle as

`5f5d3fefc21aae9fb362b2d0fc3b1df441ed8ca69160fcd88745aa07cdc7`

This string has 60 hexadecimal characters. Its first 56 characters agree with the verified index digest above; the final four are `cdc7` where the verified digest ends `fd678c67`. It therefore cannot identify any 64-character SHA-256 and does not name a different bundle. The correct full digest is `5f5d3fefc21aae9fb362b2d0fc3b1df441ed8ca69160fcd88745aa07fd678c67`. The original comment is left unedited; a correction comment was added to RES-592 and the digest is recorded here. Earlier RES-596 correctly classified the exact Linear-to-file pointer as unavailable; this verification resolves it.
