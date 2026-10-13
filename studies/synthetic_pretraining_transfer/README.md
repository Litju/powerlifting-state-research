# Synthetic pretraining transfer

G4 is a retrospective study identity. The historical record contains registry
metadata only. RES-292 is a separate, frozen PUBLIC_NATIVE experiment; it does
not reconstruct an unavailable historical protocol or result.

The experiment compares original public training rows, finite donor-copy
bootstrap rows, cross-fitted Summary Ridge pseudo-labels, public fine-tuning,
and a compute-matched public-only control. Every split, seed, label source,
model update budget, and claim boundary is fixed in [protocol.json](protocol.json).
The participant-information boundary is specified in
[formal-specification.md](formal-specification.md), and the evidence status is
recorded in [historical-lineage.md](historical-lineage.md).

No independently generated source-truth labels are created. The empirical
bootstrap copies finite public donor rows. Pseudo-labels are conditional
predictions from a public-data surrogate. Neither is an independent sample of
the source world.
