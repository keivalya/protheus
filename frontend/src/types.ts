export type NoveltySignal = "exact match found" | "similar work exists" | "not found";

export type StructuredHypothesis = {
  domain: string | null;
  model_system: string | null;
  intervention: string | null;
  control: string | null;
  outcome: string | null;
  effect_size: string | null;
  assay: string | null;
  mechanism: string | null;
  keywords: string[];
};

export type QCResult = {
  novelty_signal: NoveltySignal;
  confidence: number;
  explanation: string;
};

export type RankedResult = {
  id: string;
  title: string;
  year?: number | null;
  url?: string | null;
  source: string;
  match_score: number;
  match_tier?: "strong_match" | "related_protocol" | "weak_match";
  match_reason: string;
  matched_fields?: string[];
  missing_matches?: string[];
};

export type Paper = RankedResult & {
  doi?: string | null;
  authors?: string[];
  abstract?: string | null;
  citation_count?: number;
};

export type Protocol = RankedResult & {
  description?: string;
  steps_preview?: string[];
  materials_preview?: string[];
};

export type LiteratureQCResponse = {
  query: string;
  structured_hypothesis: StructuredHypothesis;
  qc: QCResult;
  papers: Paper[];
  protocols: Protocol[];
  warnings?: string[];
  debug?: {
    normalized_query: string;
    scientific_entities: string[];
    protocol_search_queries: string[];
    paper_search_queries: string[];
    scispacy_model: string;
    scispacy_available: boolean;
    rapidfuzz_available: boolean;
  };
};

export type LabContext = {
  cell_line_or_organism?: string | null;
  biosafety_level?: string | null;
  available_equipment: string[];
  constraints: string[];
  things_to_avoid: string[];
  detail_level: string;
};

export type ProtocolSection = {
  title: string;
  content: string;
  source_ids: string[];
  assumptions: string[];
  missing_information: string[];
  confidence: number;
  items: MaterialItem[];
  phases: WorkflowPhase[];
};

export type MaterialItem = {
  name: string;
  source_ids: string[];
  missing_information: string[];
};

export type WorkflowParameters = {
  time?: string | null;
  temperature?: string | null;
  volume?: string | null;
  concentration?: string | null;
};

export type WorkflowStep = {
  step_number: number;
  action: string;
  parameters: WorkflowParameters;
  source_ids: string[];
  assumptions: string[];
  missing_information: string[];
};

export type WorkflowPhase = {
  phase_name: string;
  purpose: string;
  steps: WorkflowStep[];
  source_ids: string[];
};

export type SafetyReview = {
  risk_level: "low_risk" | "needs_expert_review" | "blocked_or_redacted";
  flags: string[];
  requires_expert_review: boolean;
  notes: string[];
};

export type EntityValidation = {
  entity: string;
  type: string;
  normalized_name: string;
  status: string;
  source: string;
};

export type ExtractedProtocolEvidence = {
  source_id: string;
  title: string;
  steps: string[];
  materials: string[];
  equipment: string[];
  conditions: string[];
  warnings: string[];
  validation_methods: string[];
  missing_fields: string[];
};

export type ProtocolVerifierReport = {
  passed: boolean;
  warnings: string[];
  unsupported_sections: string[];
  safety_flags: string[];
};

export type ProtocolValidationIssue = {
  section: string;
  severity: "low" | "medium" | "high";
  issue: string;
  suggestion: string;
  requires_researcher_review: boolean;
};

export type ProtocolValidationReport = {
  overall_status: "pass" | "needs_revision" | "blocked";
  grounding_score: number;
  completeness_score: number;
  safety_status: "low_risk" | "needs_expert_review" | "blocked_or_redacted";
  issues: ProtocolValidationIssue[];
  missing_information: string[];
  safety_flags: string[];
  can_show_to_researcher: boolean;
};

export type FeedbackMemoryReference = {
  id: string;
  memory_text: string;
  domain?: string | null;
  experiment_type?: string | null;
  model_system?: string | null;
  intervention?: string | null;
  outcome?: string | null;
  section?: string | null;
  distance?: number | null;
  search_backend: string;
};

export type CorpusExampleReference = {
  id: string;
  source: string;
  domain?: string | null;
  experiment_type?: string | null;
  summary: string;
  structure_notes: string[];
  score: number;
  search_backend: string;
};

export type CustomProtocolDraft = {
  title: string;
  goal: string;
  experiment_type?: string | null;
  source_evidence_used: string[];
  scientific_rationale: ProtocolSection;
  materials_and_reagents: ProtocolSection;
  adapted_workflow: ProtocolSection;
  controls: ProtocolSection;
  validation_readout: ProtocolSection;
  safety_review: SafetyReview;
  risks_and_limitations: ProtocolSection;
  open_questions: string[];
  disclaimer: string;
  prior_feedback_used: FeedbackMemoryReference[];
  reference_examples_used: CorpusExampleReference[];
  validated_entities: EntityValidation[];
  extracted_protocol_evidence: ExtractedProtocolEvidence[];
};

export type ProtocolVersion = {
  id: string;
  session_id: string;
  version_number: number;
  parent_version_id?: string | null;
  protocol: CustomProtocolDraft;
  verifier_report?: ProtocolVerifierReport | null;
  validation_report?: ProtocolValidationReport | null;
  change_summary?: string | null;
  status: string;
  created_at: string;
};

export type ProtocolFeedbackType = "accept" | "correction" | "comment" | "rejection";

export type ProtocolFeedback = {
  id: string;
  session_id: string;
  version_id: string;
  section: string;
  feedback_type: ProtocolFeedbackType;
  original_text?: string | null;
  feedback_text?: string | null;
  reason?: string | null;
  severity?: "low" | "medium" | "high";
  reusable: boolean;
  created_at: string;
};

export type ProtocolSessionDetail = {
  id: string;
  original_query: string;
  structured_hypothesis: StructuredHypothesis;
  selected_papers: Paper[];
  selected_protocols: Protocol[];
  lab_context?: LabContext | null;
  status: string;
  accepted_version_id?: string | null;
  created_at: string;
  versions: ProtocolVersion[];
  feedback: ProtocolFeedback[];
};

export type ProtocolGenerationResponse = {
  session_id: string;
  version: ProtocolVersion;
  prior_feedback_used: FeedbackMemoryReference[];
  reference_examples_used: CorpusExampleReference[];
  verifier_report: ProtocolVerifierReport;
  validation_report: ProtocolValidationReport;
};

export type ProtocolAcceptResponse = {
  session: ProtocolSessionDetail | null;
  accepted_version_id: string;
  memories_saved: FeedbackMemoryReference[];
  memories_indexed: number;
};

export type TransparencyEventStatus = "waiting" | "running" | "completed" | "warning" | "failed";

export type TransparencyEvent = {
  id: string;
  session_id: string;
  version_id?: string | null;
  stage: string;
  status: TransparencyEventStatus;
  user_message: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type TransparencyEventsResponse = {
  session_id: string;
  events: TransparencyEvent[];
};
