"""Central historical alias and source-identity records."""

from __future__ import annotations

from ..contracts.components import HistoricalProvenance

HISTORICAL_SOURCES: dict[str, HistoricalProvenance] = {
    "seasonal_five_target_load_velocity_performance_forecasting": HistoricalProvenance(
        specimen_id="pl_legacy_capacity_early",
        historical_aliases=(
            "pl_legacy_capacity_early",
            "seasonal_capacity_fatigue_five_target_forecasting",
            "Seasonal Capacity–Fatigue Forecasting with Five Performance Targets",
            "initial Powerlifting task",
            "Worlds-phase task",
            "accumulation/intensification/taper/Worlds-specific peak phases",
            "Powerlifting synthetic seasonal five-output forecast — early specimen",
            "Legacy Five-Output (Early)",
            "psr:benchmark-spec:pl-legacy-capacity-early-historical-mapping@1.0.0~0d3239fc6e4b",
        ),
        historical_parent_specimen_id=None,
        parentage_status="ROOT_SPECIMEN",
        source_technical_label="Seasonal Multi-Output Performance Forecasting — Early Synthetic Capacity/Fatigue World",
        source_system_focus="Seasonal synthetic capacity/fatigue and load-velocity outputs; no real-athlete validation.",
        source_prediction_setting=(
            "Use past/completed records available at each query time; future meet outcomes and "
            "future/in-session records are excluded. No declared future-plan input."
        ),
        source_research_question=(
            "Within the early synthetic seasonal capacity/fatigue world, how well can a model forecast "
            "target-load velocity, reference-velocity load, session shift, next-set velocity loss, and "
            "competition-day capacity from records available at each query time? This characterizes the "
            "archived synthetic task; it does not establish real-athlete validity or latent-state "
            "identification."
        ),
        source_research_question_evidence="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
        historical_objective="UNKNOWN",
        historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
        source_qualification_status="NOT_QUALIFIED; no benchmark-level receipt recovered",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:pl-legacy-capacity-early-sampling-design@1.0.0~200b45f1c717",
            "evaluation_id": "psr:evaluation:legacy-prediction-physical-consistency-blend@1.0.0~a67b640c37ae",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-legacy-capacity-early-historical-mapping@1.0.0~0d3239fc6e4b",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:legacy-multi-channel-field-observation@1.0.0~4c95cbb9d46a",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:legacy-five-target-set@1.0.0~d0a410b2edfc",
            "representation_id": "psr:representation:published-legacy-tables@1.0.0~467ad9987e65",
            "scientific_system_config_id": "psr:scientific-system-config:pl-legacy-capacity-early-historical-system@1.0.0~d1d25689bb87",
            "task_id": "psr:task:five-seasonal-powerlifting-outputs@1.0.0~cc696be87ed4",
            "world_id": "psr:world:early-seasonal-capacity-load-velocity-world@1.0.0~168dadf66c15",
        },
        source_component_changes={
            "changed_from_parent": [],
            "held_constant_from_parent": [],
            "primary_design_axis": "Root specimen: initial seasonal synthetic capacity/fatigue world, "
            "multi-channel observations, five-output task, legacy "
            "physical-consistency evaluation.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "What objective motivated the first task?",
            "What were the exact RNG seed and final scorer aggregation?",
            "Was benchmark qualification performed?",
        ),
        attached_audit_aliases=(),
    ),
    "class_normalized_cross_lift_five_target_performance_forecasting": HistoricalProvenance(
        specimen_id="pl_legacy_capacity_refined",
        historical_aliases=(
            "pl_legacy_capacity_refined",
            "class_normalized_cross_lift_capacity_fatigue_forecasting",
            "Class-Normalized Cross-Lift Capacity–Fatigue Forecasting with Five Targets",
            "July refinement",
            "synthetic male Open Classic/raw cohort",
            "Powerlifting synthetic seasonal five-output forecast — refined specimen",
            "Legacy Five-Output (Refined)",
            "psr:benchmark-spec:pl-legacy-capacity-refined-historical-mapping@1.0.0~7fa649664339",
        ),
        historical_parent_specimen_id="pl_legacy_capacity_early",
        parentage_status="RECOVERED_LINEAGE; rationale UNKNOWN",
        source_technical_label="Seasonal Multi-Output Performance Forecasting — Refined Synthetic Cross-Lift World",
        source_system_focus="Refined synthetic seasonal capacity/fatigue, male Open Classic/raw cohort stylization.",
        source_prediction_setting="Past/completed context at each query; future outcomes excluded; no declared future-plan input.",
        source_research_question=(
            "Within the refined synthetic male Open Classic/raw cross-lift world, how well can a model "
            "forecast the five outputs at held-out late-season/Worlds-phase queries using past or "
            "completed public records? This is conditional on the synthetic generator, not real-athlete "
            "validity or latent-state recovery."
        ),
        source_research_question_evidence="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
        historical_objective="UNKNOWN",
        historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
        source_qualification_status="NOT_QUALIFIED; no benchmark-level receipt recovered",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:pl-legacy-capacity-refined-sampling-design@1.0.0~66448b8642d5",
            "evaluation_id": "psr:evaluation:refined-prediction-physical-consistency-blend@1.0.0~dceb437baad4",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-legacy-capacity-refined-historical-mapping@1.0.0~7fa649664339",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:refined-field-velocity-and-lpt@1.0.0~141fae096dc7",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:legacy-five-target-set@1.0.0~d0a410b2edfc",
            "representation_id": "psr:representation:refined-legacy-tables@1.0.0~94f112f44552",
            "scientific_system_config_id": "psr:scientific-system-config:pl-legacy-capacity-refined-historical-system@1.0.0~307f8a9057ef",
            "task_id": "psr:task:five-seasonal-powerlifting-outputs@1.0.0~cc696be87ed4",
            "world_id": "psr:world:refined-class-normalized-seasonal-cross-lift-world@1.0.0~c7dcec83d1f8",
        },
        source_component_changes={
            "changed_from_parent": [
                "WORLD: capacity/state formulas",
                "OBSERVATION_MODEL: field-observation implementation",
                "DATASET_SPEC/REALIZATION: cohort and generated sample",
            ],
            "held_constant_from_parent": [
                "Five named prediction output types at scientific-question level"
            ],
            "primary_design_axis": "Multi-axis rewrite: WORLD/state formulas, observation implementation, "
            "cohort and data changed; five target types remained.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "What problem triggered the July rewrite and what effect was expected?",
            "What scorer aggregation/seed governs canonical replay?",
            "Was qualification performed?",
        ),
        attached_audit_aliases=(),
    ),
    "held_out_final_origin_five_target_performance_evaluation": HistoricalProvenance(
        specimen_id="pl_legacy_target_domain_split",
        historical_aliases=(
            "pl_legacy_target_domain_split",
            "final_origin_target_domain_evaluation",
            "Final-Origin Target-Domain Evaluation of Seasonal Performance Forecasts",
            "target-domain validation split",
            "CUDA reference proof",
            "Powerlifting synthetic seasonal five-output forecast — final-origin split",
            "Legacy Target-Domain Split",
            "psr:benchmark-spec:pl-legacy-target-domain-split-historical-mapping@1.0.0~04e5927ef362",
        ),
        historical_parent_specimen_id="pl_legacy_capacity_refined",
        parentage_status="RECOVERED_LINEAGE",
        source_technical_label="Final-Origin Transfer Evaluation for Five Seasonal Powerlifting Outputs",
        source_system_focus=(
            "Five-output forecasting in refined synthetic cross-lift world with final-origin held-out "
            "evaluation."
        ),
        source_prediction_setting=(
            "Past/completed observations only. Training origins 200/260/315/340; validation/hidden at "
            "340→365; no declared future-plan input."
        ),
        source_research_question=(
            "Using the refined synthetic world, can predictors trained on four 25-day origins (200, 260, "
            "315, 340) predict the same five outputs for an independent held-out final-origin draw at "
            "340→365? This tests transfer within the synthetic target domain, not human or general-domain "
            "transfer."
        ),
        source_research_question_evidence="CONTEMPORANEOUS_RESEARCH_QUESTION",
        historical_objective="Add public validation from the final held-out target domain using independent split streams.",
        historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
        source_qualification_status="NOT_QUALIFIED; split objective resolved, no qualification receipt",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:pl-legacy-target-domain-split-sampling-design@1.0.0~fd842c9e9b0c",
            "evaluation_id": "psr:evaluation:target-domain-public-validation@1.0.0~31076d7ca05d",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-legacy-target-domain-split-historical-mapping@1.0.0~04e5927ef362",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:refined-field-velocity-and-lpt@1.0.0~141fae096dc7",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:legacy-five-target-set@1.0.0~d0a410b2edfc",
            "representation_id": "psr:representation:refined-legacy-tables@1.0.0~94f112f44552",
            "scientific_system_config_id": "psr:scientific-system-config:pl-legacy-target-domain-split-historical-system@1.0.0~307f8a9057ef",
            "task_id": "psr:task:five-outputs-with-mixed-origin-25-day-labels@1.0.0~36e65b57cb2e",
            "world_id": "psr:world:refined-class-normalized-seasonal-cross-lift-world@1.0.0~c7dcec83d1f8",
        },
        source_component_changes={
            "changed_from_parent": [
                "DATASET_SPEC/REALIZATION: independent streams and final-origin "
                "validation/hidden samples",
                "TASK: mixed training origins and 25-day final forecast",
                "EVALUATION: public validation at final target domain",
            ],
            "held_constant_from_parent": [
                "WORLD and capacity/velocity equations",
                "OBSERVATION_MODEL",
                "Five target types",
            ],
            "primary_design_axis": "DATASET/TASK/EVALUATION: independent split streams, four earlier "
            "origins, final-origin public validation/hidden queries.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "Did final-origin validation improve selection or prediction?",
            "Can legacy scorer/seed be recovered for normalized reevaluation?",
            "Was benchmark qualification performed?",
        ),
        attached_audit_aliases=(),
    ),
    "four_target_load_velocity_and_competition_performance_forecasting": HistoricalProvenance(
        specimen_id="pl_c21_stable_slope_tilt",
        historical_aliases=(
            "pl_c21_stable_slope_tilt",
            "stable_slope_tilt_four_target_forecasting",
            "Stable-Slope/Tilt Four-Target Athlete-State Forecasting",
            "C21.2",
            "C21-athlete-state-stable-slope-tilt-seed3115",
            "phase4_c21_2_temporal_interface",
            "Powerlifting synthetic four-output forecast — C21 stable-slope/tilt",
            "C21 Stable-Slope/Tilt",
            "psr:benchmark-spec:pl-c21-stable-slope-tilt-historical-mapping@1.0.0~c840b6ca6f79",
        ),
        historical_parent_specimen_id="pl_legacy_target_domain_split",
        parentage_status="RECOVERED_LINEAGE; rationale UNKNOWN",
        source_technical_label="Four-Target 25-Day Athlete-State Forecasting under a Stable-Slope/Tilt World",
        source_system_focus="Synthetic athlete-specific stable-slope/tilt state model; four targets P1/P2/P4/P5.",
        source_prediction_setting=(
            "Point-in-time histories; temporal features end at the current completed event. No "
            "future-plan field in recovered public interface."
        ),
        source_research_question=(
            "Within the stable-slope/tilt formulation stable-slope/tilt synthetic world, how accurately "
            "can models forecast P1/P2/P4/P5 from available histories at four origins, including day "
            "340→365? This does not establish causal training effects, real-athlete accuracy, or "
            "state/parameter recovery."
        ),
        source_research_question_evidence="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
        historical_objective="UNKNOWN",
        historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
        source_qualification_status="NOT_QUALIFIED; checkpoint/public scalar is not benchmark qualification",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:pl-c21-stable-slope-tilt-sampling-design@1.0.0~30f3942a0a2b",
            "evaluation_id": "psr:evaluation:c21-c22-four-target-release-contract@1.0.0~a17c43781876",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-c21-stable-slope-tilt-historical-mapping@1.0.0~c840b6ca6f79",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:c21-field-velocity-rpe-rir-readiness@1.0.0~bab5eaa0e137",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:four-target-p1-p2-p4-p5@1.0.0~1ded2f48e4a3",
            "representation_id": "psr:representation:c21-c22-temporal-interface@1.0.0~ee6b1d7aace1",
            "scientific_system_config_id": "psr:scientific-system-config:pl-c21-stable-slope-tilt-historical-system@1.0.0~7fa3ef894b7c",
            "task_id": "psr:task:four-25-day-athlete-state-outputs@1.0.0~9a575a70b41e",
            "world_id": "psr:world:c21-athlete-state-stable-slope-tilt-world@1.0.0~8956f2327a14",
        },
        source_component_changes={
            "changed_from_parent": [
                "WORLD/system: C21 stable-slope/tilt model",
                "OBSERVATION_MODEL and DATASET_SPEC/REALIZATION",
                "TASK/QOI: P3 dropped; P1/P2/P4/P5 retained",
                "REPRESENTATION and weighted EVALUATION",
            ],
            "held_constant_from_parent": [
                "Three lifts",
                "Synthetic domain",
                "Final target day 365",
            ],
            "primary_design_axis": "Multi-axis: new C21 world/state/population and data; P3 removed; "
            "four-target weighted task/evaluation.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "What motivated stable-slope/tilt formulation.2 and dropping P3?",
            "Was stable-slope/tilt formulation independently qualified?",
            "What metric produced scalar 0.16719849?",
        ),
        attached_audit_aliases=(),
    ),
    "performance_forecasting_under_schedule_exposure_reporting_heterogeneity": HistoricalProvenance(
        specimen_id="pl_c22_schedule_exposure",
        historical_aliases=(
            "pl_c22_schedule_exposure",
            "training_schedule_exposure_heterogeneity_forecasting",
            "Training Schedule/Exposure Heterogeneity Forecasting",
            "schedule_exposure_heterogeneity_forecasting",
            "Schedule/Exposure Heterogeneity Four-Target Forecasting",
            "C22.4",
            "C22-schedule-exposure-v4",
            "local/c22.4-freeze",
            "repair/c22.4-final-interface-and-pregpu-gate",
            "Powerlifting synthetic four-output forecast — C22 schedule/exposure",
            "C22 Schedule/Exposure",
            "psr:benchmark-spec:pl-c22-schedule-exposure-historical-mapping@1.0.0~aac9e4d190d9",
        ),
        historical_parent_specimen_id="pl_c21_stable_slope_tilt",
        parentage_status="RECOVERED_LINEAGE; one C22.4 specimen only",
        source_technical_label="Four-Target Forecasting under Heterogeneous Schedule and Exposure",
        source_system_focus=(
            "stable-slope/tilt formulation latent-state core with schedule/exposure formulation "
            "schedule/exposure/population and reporting-heterogeneity layer."
        ),
        source_prediction_setting=(
            "Point-in-time completed histories for 25-day forecast; no declared future-plan input in "
            "recovered interface."
        ),
        source_research_question=(
            "Within the schedule/exposure formulation synthetic schedule/exposure world, can models "
            "forecast P1/P2/P4/P5 over 25 days from completed histories as schedules and reports vary? No "
            "schedule/exposure formulation result establishes that added heterogeneity improves "
            "prediction."
        ),
        source_research_question_evidence="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
        historical_objective=(
            "Add schedule/exposure and reporting heterogeneity over stable-slope/tilt formulation core "
            "while retaining the four-target 25-day contract; triggering need or expected gain is "
            "UNKNOWN."
        ),
        historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
        source_qualification_status="NOT_EVALUATED; no schedule/exposure formulation-specific result or qualification receipt",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:pl-c22-schedule-exposure-sampling-design@1.0.0~6fcc1c11df19",
            "evaluation_id": "psr:evaluation:c21-c22-four-target-release-contract@1.0.0~a17c43781876",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-c22-schedule-exposure-historical-mapping@1.0.0~aac9e4d190d9",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:c22-schedule-reporting-observation@1.0.0~c624f7e4e737",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:four-target-p1-p2-p4-p5@1.0.0~1ded2f48e4a3",
            "representation_id": "psr:representation:c21-c22-temporal-interface@1.0.0~ee6b1d7aace1",
            "scientific_system_config_id": "psr:scientific-system-config:pl-c22-schedule-exposure-historical-system@1.0.0~24e13266e267",
            "task_id": "psr:task:four-25-day-athlete-state-outputs@1.0.0~9a575a70b41e",
            "world_id": "psr:world:c22-heterogeneous-schedule-exposure-world@1.0.0~55a292e3b1c6",
        },
        source_component_changes={
            "changed_from_parent": [
                "WORLD/system: schedule/exposure law over C21 core",
                "OBSERVATION_MODEL: reporting biases/context",
                "DATASET_SPEC/REALIZATION: regenerated sample/hashes",
            ],
            "held_constant_from_parent": [
                "C21 latent-state core",
                "TASK/QOI: four 25-day P1/P2/P4/P5 targets",
                "REPRESENTATION and weighted EVALUATION",
            ],
            "primary_design_axis": "Add schedule/exposure/population heterogeneity and "
            "observation/reporting bias over C21 core; regenerated data, seed "
            "3128.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "What need motivated schedule/exposure heterogeneity?",
            "Which dose-history/v4 label was intended; were unresolved intermediate variants "
            "materialized?",
            "Was schedule/exposure formulation independently evaluated or qualified?",
        ),
        attached_audit_aliases=(),
    ),
    "observed_origin_referenced_capacity_change_forecasting": HistoricalProvenance(
        specimen_id="pl_response_v1_t0_public_2048",
        historical_aliases=(
            "pl_response_v1_t0_public_2048",
            "observed_origin_performance_change_forecasting",
            "Observed-Origin Performance-Change Forecasting",
            "World-V1",
            "powerlifting.big3.response.dose_memory.v1",
            "T0_CURRENT",
            "response-world T0",
            "Powerlifting synthetic response forecast — V1 T0 observed-origin target",
            "V1 T0 Observed-Origin Change",
            "psr:benchmark-spec:pl-response-v1-t0-public-2048-historical-mapping@1.0.0~f3f6a6a18178",
        ),
        historical_parent_specimen_id="pl_c22_schedule_exposure",
        parentage_status="CANDIDATE_EDGE_ONLY; direct parent and motive UNKNOWN per RES-265",
        source_technical_label="Observed-Origin Performance-Change Forecasting under the dose-history Dose-Memory World",
        source_system_focus=(
            "Dose-memory response world; target subtracts noisy observed-origin assessment from future "
            "modeled capacity."
        ),
        source_prediction_setting=(
            "Origin 224; use observations through origin and complete declared future dose/intensity "
            "plan. Future realized outcomes are unavailable."
        ),
        source_research_question=(
            "At dose-history origin 224, can a model using noisy observations through origin and the "
            "participant-visible dose/intensity plan predict C(origin+h−1)−A_origin for squat, bench, "
            "deadlift at h=14/28/56? A_origin is noisy, so this is not pure latent capacity change, "
            "causal effect, or directly comparable to latent-origin/parsimonious latent capacity-change."
        ),
        source_research_question_evidence="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
        historical_objective="UNKNOWN",
        historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
        source_qualification_status="FINAL_ADJUDICATION_BLOCKED; authoritative response-world scorer/truth absent",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:v1-response-shared-sampling-inputs@1.0.0~23bb079da836",
            "evaluation_id": "psr:evaluation:v1-t0-public-only-sre@1.0.0~2181dbc99f16",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-response-v1-t0-public-2048-historical-mapping@1.0.0~f3f6a6a18178",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:v1-performance-assessment-load-velocity@1.0.0~ac2781dad306",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:future-capacity-minus-noisy-origin-assessment@1.0.0~b7e407fe2b81",
            "representation_id": "psr:representation:v1-response-feature-schema-v2@1.0.0~e9db564d4b3b",
            "scientific_system_config_id": "psr:scientific-system-config:pl-response-v1-t0-public-2048-historical-system@1.0.0~ef1191fb1eb5",
            "task_id": "psr:task:v1-t0-observed-origin-performance-change@1.0.0~6fedfb6051bb",
            "world_id": "psr:world:v1-dose-memory-response-world@1.0.0~11b6f0033502",
        },
        source_component_changes={
            "changed_from_parent": [
                "Candidate edge only: WORLD, OBSERVATION_MODEL, DATASET, TASK/QOI, "
                "EVALUATION differ from C22.4",
                "Direct parent and held-constant components UNKNOWN",
            ],
            "held_constant_from_parent": ["UNKNOWN; no unique C22.4 parent established"],
            "primary_design_axis": "New dose-memory WORLD, observation/export, dataset, T0 target/TASK, "
            "and evaluation; direct predecessor/motive unresolved.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "Was the schedule/exposure formulation the direct dose-history parent and observed-origin "
            "authorized target?",
            "What was authoritative observed-origin scorer/truth and final result?",
            "Can import/runtime provenance be made exact?",
        ),
        attached_audit_aliases=(),
    ),
    "latent_origin_capacity_change_forecasting": HistoricalProvenance(
        specimen_id="pl_response_v1_t1_capacity_change",
        historical_aliases=(
            "pl_response_v1_t1_capacity_change",
            "World-V1 T1",
            "ALI-252 target migration",
            "powerlifting.big3.latent_capacity_change.v1",
            "Powerlifting synthetic response forecast — V1 T1 latent capacity change",
            "V1 T1 Latent Capacity Change",
            "psr:benchmark-spec:pl-response-v1-t1-capacity-change-historical-mapping@1.0.0~0f9b63025bd1",
        ),
        historical_parent_specimen_id="pl_response_v1_t0_public_2048",
        parentage_status="DIRECT_TARGET_MIGRATION; STRONG_ISOLATION",
        source_technical_label="Latent Capacity-Change Forecasting under the dose-history Dose-Memory World",
        source_system_focus=(
            "dose-history dose-memory synthetic world and latent capacity-change target; later "
            "adjudication found exact target-bearing formulation under-supported."
        ),
        source_prediction_setting=(
            "Origin 224; dose-history observations through origin and complete declared future "
            "dose/intensity plan; future realized outcomes unavailable."
        ),
        source_research_question=(
            "At dose-history origin 224, using noisy pre-origin observations and participant-visible "
            "declared future dose/intensity plan, how accurately can a model forecast "
            "ΔC=C(origin+h−1)−C(origin−1) for three lifts at h=14/28/56, keeping measurement noise in "
            "inputs and out of target? Conditional synthetic prediction, not causal effect, "
            "latent-coordinate recovery, or human validity."
        ),
        source_research_question_evidence="CONTEMPORANEOUS_RESEARCH_QUESTION",
        historical_objective=(
            "Replace observed-origin noisy observed-origin baseline with latent origin capacity, removing "
            "origin measurement error from target while retaining noisy measurement as input."
        ),
        historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
        source_qualification_status="PUBLIC_DIAGNOSTICS_ONLY; no fresh hidden latent-origin challenge/final Guide qualification",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:v1-response-shared-sampling-inputs@1.0.0~23bb079da836",
            "evaluation_id": "psr:evaluation:v1-t1-public-only-diagnostics@1.0.0~60c57c4744de",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-response-v1-t1-capacity-change-historical-mapping@1.0.0~0f9b63025bd1",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "UNRESOLVED_DIRECT_ID",
            "observation_model_id": "psr:observation-model:v1-performance-assessment-load-velocity@1.0.0~ac2781dad306",
            "population_id": None,
            "population_id_status": "UNRESOLVED_DIRECT_ID",
            "qoi_id": "psr:qoi:latent-capacity-change@1.0.0~675491124046",
            "representation_id": "psr:representation:v1-response-feature-schema-v2@1.0.0~e9db564d4b3b",
            "scientific_system_config_id": "psr:scientific-system-config:pl-response-v1-t1-capacity-change-historical-system@1.0.0~ef1191fb1eb5",
            "task_id": "psr:task:latent-capacity-change@1.0.0~44fc77353e7a",
            "world_id": "psr:world:v1-dose-memory-response-world@1.0.0~11b6f0033502",
        },
        source_component_changes={
            "changed_from_parent": [
                "TASK/QOI: target changed to latent-origin capacity difference",
                "DATASET_REALIZATION: labels changed on all 2,048 equal semantic inputs",
                "EVALUATION identity changed; SRE formula family retained",
            ],
            "held_constant_from_parent": [
                "WORLD",
                "OBSERVATION_MODEL",
                "2,048 semantic inputs",
                "REPRESENTATION",
                "SRE/equal-lift aggregation family",
            ],
            "primary_design_axis": "One-axis estimand/label migration; same WORLD/observation/2,048 "
            "inputs/representation; TASK/QOI, labels, realization, and evaluation "
            "identity changed.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "No fresh latent-origin hidden challenge/final qualification.",
            "Can dose-history import/runtime be reconstructed exactly?",
            "Can dose-history mechanisms/public attacks be assessed under complete protocol?",
        ),
        attached_audit_aliases=(),
    ),
    "latent_capacity_change_with_transient_expression_forecasting": HistoricalProvenance(
        specimen_id="pl_response_v2_parsimonious_production",
        historical_aliases=(
            "pl_response_v2_parsimonious_production",
            "parsimonious_latent_capacity_change_forecasting",
            "Parsimonious Latent Capacity-Change Forecasting with Transient Performance Expression",
            "World-V2",
            "powerlifting.big3.response.parsimonious.v2",
            "powerlifting.big3.latent_capacity_change.dataset.v2",
            "ALI-370 release identity",
            "Powerlifting synthetic response forecast — V2 parsimonious capacity change",
            "V2 Parsimonious Capacity Change",
            "psr:benchmark-spec:pl-response-v2-parsimonious-production-historical-mapping@1.0.0~548604c18ac7",
        ),
        historical_parent_specimen_id="pl_response_v1_t1_capacity_change",
        parentage_status="DIRECT_SCIENTIFIC_SUCCESSOR; MULTI_AXIS_CHANGE",
        source_technical_label="Parsimonious Latent Capacity-Change Forecasting under a Synthetic Powerlifting World",
        source_system_focus=(
            "A/C/R/P separation: chronic adaptation A, derived capacity C, transient R affecting "
            "expressed performance P, recorded observations."
        ),
        source_prediction_setting=(
            "Cutoff day 224; 32 weekly observations/lift through day223 plus declared plan/context "
            "visible; latent coordinates, targets, future realized outcomes/observations hidden."
        ),
        source_research_question=(
            "At day224, given 32 weekly performance observations/lift through day223, visible declared "
            "plan and task-allowed context, can a model predict DeltaC=C(origin+h−1)−C(origin−1) for "
            "three lifts at horizons 14/28/56 under World-parsimonious latent capacity-change? This is "
            "conditional synthetic prediction, not human response, biological ID, intervention efficacy, "
            "or OOD generalization."
        ),
        source_research_question_evidence="CONTEMPORANEOUS_RESEARCH_QUESTION",
        historical_objective=(
            "Replace under-supported target-bearing dose-history formulations with a simpler empirically "
            "bounded synthetic world that preserves latent capacity-change target meaning and "
            "origin/horizons."
        ),
        historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
        source_qualification_status="QUALIFIED_SYNTHETIC_SPECIMEN; expected ALI-386 readiness receipt SHA 59108e3e… missing",
        source_component_ids={
            "dataset_spec_id": "psr:dataset-spec:pl-response-v2-parsimonious-production-sampling-design@1.0.0~7098655518cd",
            "evaluation_id": "psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f",
            "historical_benchmark_spec_id": "psr:benchmark-spec:pl-response-v2-parsimonious-production-historical-mapping@1.0.0~548604c18ac7",
            "intervention_regime_id": None,
            "intervention_regime_id_status": "COMMITTED_BY_SYSTEM_CONFIG",
            "observation_model_id": "psr:observation-model:world-v2-performance-expression-observation@1.0.0~c8a52272a9cd",
            "population_id": None,
            "population_id_status": "COMMITTED_BY_SYSTEM_CONFIG",
            "qoi_id": "psr:qoi:latent-capacity-change@1.0.0~675491124046",
            "representation_id": "psr:representation:world-v2-participant-inputs-json-v2@1.0.0~2c2c7f0222c6",
            "scientific_system_config_id": "psr:scientific-system-config:pl-response-v2-parsimonious-production-historical-system@1.0.0~81141316f605",
            "task_id": "psr:task:latent-capacity-change@1.0.0~44fc77353e7a",
            "world_id": "psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e",
        },
        source_component_changes={
            "changed_from_parent": [
                "WORLD/system: C/R/P semantics separated",
                "Population/intervention members committed through new config; direct "
                "IDs not separately assigned",
                "OBSERVATION_MODEL, DATASET_SPEC/REALIZATION, JSON REPRESENTATION",
                "EVALUATION identity changed; SRE family retained",
            ],
            "held_constant_from_parent": [
                "TASK/QOI: latent capacity-change functional",
                "Three lifts and kg",
                "Origin224; horizons14/28/56",
                "SRE ddof0 equal-lift averaging",
            ],
            "primary_design_axis": "New WORLD/system, composed population/intervention, observation, "
            "dataset and JSON representation; preserve QOI/TASK family, "
            "lifts/units/origin/horizons and SRE family.",
        },
        evidence_pointers=(
            "Source-bound historical characterization; source artifacts are not redistributed.",
        ),
        unresolved_questions=(
            "Where is expected ALI-386 readiness receipt?",
            "Do observation/data support geometry warrant future change after controlled evaluation?",
            "Can claims beyond synthetic support be separately validated?",
        ),
        attached_audit_aliases=("G0", "G1", "G2", "G3", "G4"),
    ),
}

__all__ = ["HISTORICAL_SOURCES"]
