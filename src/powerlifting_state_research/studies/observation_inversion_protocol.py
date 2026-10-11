"""Frozen, independent RES-287 study design; no benchmark identity changes."""

from dataclasses import dataclass

from ..contracts.serialization import sha256_record


@dataclass(frozen=True, slots=True)
class ObservationInversionProtocol:
    version: str = "1.0.0"
    question: str = "What do assessment and velocity identify about P, C, A, R and parameters?"
    world_id: str = "psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e"
    observation_id: str = (
        "psr:observation-model:latent-capacity-transient-performance-observation@1.0.0~9147ed8f5372"
    )
    entities: int = 32
    population_seed: int = 287101
    observation_seed: int = 287102
    bootstrap_seed: int = 287103
    bootstrap_replicates: int = 1000
    lengths: tuple[int, ...] = (1, 4, 16, 32)
    cadences_days: tuple[int, ...] = (1, 7)
    noise_scales: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)
    channels: tuple[str, ...] = ("assessment", "velocity", "combined", "load")
    methods: tuple[str, ...] = ("last", "mean")
    targets: tuple[str, ...] = ("P223_kg", "C223_kg", "P230_kg")
    metrics: tuple[str, ...] = ("rmse_kg", "mae_kg", "bias_kg", "invalid_count")
    split_rule: str = "evaluation-only: all 32 entities; no fitting, selection or training split"
    realization_rule: str = (
        "IID 16 coordinates per entity; template=(entity+lift_index)%4; future continue; "
        "separate entity/lift observation streams; union of backwards days ending 223; "
        "save base assessment/velocity errors and load fraction; scale errors without resampling"
    )
    information_rule: str = (
        "Estimator accepts only lift name and assessment/load/velocity observations through 223. "
        "No latent truth, parameters, population coordinates or future observations. "
        "Load-only is a noisy assessment proxy because load fraction is bounded."
    )
    inversion_rule: str = (
        "assessment=a; velocity=L/(1-0.6*(v-endpoint)/span); load=L/0.695; "
        "combined inverse delta-method variance weighted assessment and velocity; "
        "variance assessment=(CV*a)^2, velocity=(0.6*L*sigma/span/r^2)^2; "
        "zero noise uses equal weights; r outside [0.4,1] yields invalid; "
        "combined rejects invalid velocity; no dropping, clipping or imputation"
    )
    uncertainty_rule: str = (
        "Paired entity bootstrap 1000 resamples; percentile 95% RMSE and "
        "combined-minus-assessment RMSE intervals per lift/condition/target; "
        "descriptive same-law synthetic uncertainty, no physiological inference"
    )
    hypotheses: tuple[str, ...] = (
        "H1 noiseless channel inverses recover P to absolute tolerance 1e-10 kg",
        "H2 single-time mean observation Jacobian for (A,R) has rank at most one",
        "H3 noiseless P inversion does not in general recover C",
        "H4 combined-minus-assessment RMSE interval below zero supports finite-sample improvement",
        "H5 longer history means may trade variance reduction for dynamic bias",
    )
    diagnostics: str = (
        "Single-state constructive level set; known-parameter free-initial-state rest-map "
        "Jacobian at A=R=0.3 with gaps 1,7,28 days; analytical versus central difference "
        "step1e-6 tolerance1e-6; midpoint six squat-coordinate sensitivity on all four "
        "templates at weekly observations using steps1e-5 and5e-6, relative rank threshold1e-8; "
        "constant continue input reference-stimulus equivalence with coordinates0.2 and0.8; "
        "small reference-coordinate perturbation0.01 on template0; no global proof from rank"
    )
    failure_rule: str = (
        "FAIL execution on source/protocol/hash drift, nonfinite truth, mismatch or H1 failure. "
        "Invalid inverse makes whole metric cell INCONCLUSIVE with null metrics. "
        "Interval spanning zero means INCONCLUSIVE for H4; rank is local diagnostic only. "
        "Global identification on native templates and physiological identification unresolved."
    )


PROTOCOL = ObservationInversionProtocol()
PROTOCOL_DIGEST = sha256_record(PROTOCOL)
STUDY_ID = f"psr:study:observation-inversion-public-native@1.0.0~{PROTOCOL_DIGEST[7:19]}"
