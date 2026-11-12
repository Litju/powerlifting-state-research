/** Public-safe research material listed on the Publication page. Every path must exist in the public repository (tested). */
export interface Material {
  path: string;
  title: string;
  kind: "overview" | "study" | "evidence" | "rights";
}

export const MATERIAL: Material[] = [
  { path: "README.md", title: "Repository README and research map", kind: "overview" },
  { path: "docs/current-research-state.md", title: "Current research state and artifact access", kind: "overview" },
  { path: "docs/studies/index.md", title: "Study index: findings and limits for G1 to G4 and the representation study", kind: "study" },
  { path: "docs/studies/g2-identifiability-decision.md", title: "G2 identifiability decision (RES-617)", kind: "study" },
  { path: "docs/studies/g4-reader-corrections-v1.md", title: "G4 reader corrections (RES-510, RES-511)", kind: "study" },
  { path: "docs/studies/observable-strength-forecasting.md", title: "Observable strength-assessment forecasting (RES-616)", kind: "study" },
  { path: "docs/studies/history-conditional-uncertainty.md", title: "History-conditioned predictive uncertainty (RES-639)", kind: "study" },
  { path: "docs/studies/probabilistic-capacity-forecasting.md", title: "Probabilistic capacity forecasting: public methods and aggregates (restricted raw evidence)", kind: "study" },
  { path: "results/studies/res294-definition-b-final-synthesis.md", title: "RES-294 bounded program synthesis", kind: "study" },
  { path: "docs/science/system-model.md", title: "Scientific system model and public capacity/expression law", kind: "study" },
  { path: "results/studies/observable_strength_forecasting/full/summary.json", title: "RES-616 summary (evidence)", kind: "evidence" },
  { path: "results/studies/observable_strength_forecasting/full/manifest.json", title: "RES-616 manifest with output hashes (evidence)", kind: "evidence" },
  { path: "results/studies/history_conditional_uncertainty/full/summary.json", title: "RES-639 summary (evidence)", kind: "evidence" },
  { path: "results/studies/history_conditional_uncertainty/full/independent-audit/evidence-audit.json", title: "RES-639 independent evidence audit (evidence)", kind: "evidence" },
  { path: "results/tables/public-native-comparator-frontier.csv", title: "Public-native comparator frontier (evidence)", kind: "evidence" },
  { path: "docs/reproducibility.md", title: "Reproducibility: Level A inspection and Level B numerical reproduction", kind: "rights" },
  { path: "provenance/normalization-and-rights-clarification.md", title: "Normalization and rights clarification", kind: "rights" },
  { path: "LICENSE", title: "MIT License (code and data)", kind: "rights" },
  { path: "LICENSE-DOCS", title: "CC BY 4.0 (documentation)", kind: "rights" },
  { path: "CITATION.cff", title: "Software citation file", kind: "rights" },
];
