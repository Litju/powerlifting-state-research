# Public Surrogate Reconstruction

## Historical record

G3 / ALI-543 and pl_study_g3_public_surrogate survive as study metadata and aliases. The public G3 homes contain no rights-cleared original protocol, row data, learner, fitted model, or result. The former PROVEN label is a bootstrap classification, not a scientific finding. See historical-lineage.md.

## New RES-290 experiment

RES-290 adds an independent PUBLIC_NATIVE experiment under this study home. It is not a reconstruction or reproduction of historical G3. The protocol and evidence hashes are frozen in protocol.json and frozen-evidence.json before new realizations are generated. The learner receives only the frozen participant-visible data fields, fitting/development labels, and evaluation inputs. Evaluation truth and public generator code remain authority-side.

The methods are an empirical finite-support row resampler, summary Ridge, and a generic sequence-aware random-feature Ridge. The latter is the single nonlinear candidate. Conditional point prediction and complete observable-record sampling are measured separately. The experiment does not use a mechanistic estimator, source-equation reconstruction, neural tournament, new dependency, canonical M3/M4 training result, private artifact, or historical score.

From the repository root, run `uv run --locked python -m powerlifting_state_research.studies.public_surrogate_reconstruction` to create the immutable result directory. Run the same command with `--check` to verify the frozen sources, learner boundary, output hashes, and deterministic replay. The runner refuses to overwrite an existing result directory.
