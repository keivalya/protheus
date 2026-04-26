from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class LabContext(BaseModel):
    cell_line_or_organism: str | None = None
    biosafety_level: str | None = None
    available_equipment: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    things_to_avoid: list[str] = Field(default_factory=list)
    detail_level: str = "researcher_review_draft"


RiskLevel = Literal["low_risk", "needs_expert_review", "blocked_or_redacted"]


class WorkflowParameters(BaseModel):
    time: str | None = None
    temperature: str | None = None
    volume: str | None = None
    concentration: str | None = None


class WorkflowStep(BaseModel):
    step_number: int
    action: str
    parameters: WorkflowParameters = Field(default_factory=WorkflowParameters)
    source_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class WorkflowPhase(BaseModel):
    phase_name: str
    purpose: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class MaterialItem(BaseModel):
    name: str
    source_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class ProtocolSection(BaseModel):
    title: str
    content: str
    source_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    items: list[MaterialItem] = Field(default_factory=list)
    phases: list[WorkflowPhase] = Field(default_factory=list)

    @field_validator("phases", mode="before")
    @classmethod
    def normalize_phases(cls, value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, Any]] = []
        for phase_index, phase in enumerate(value, start=1):
            if not isinstance(phase, dict):
                continue
            phase_name = phase.get("phase_name") or phase.get("title") or phase.get("name")
            raw_steps = phase.get("steps") or []
            if isinstance(raw_steps, str):
                raw_steps = [raw_steps]

            steps: list[dict[str, Any]] = []
            for step_index, step in enumerate(raw_steps, start=1):
                if isinstance(step, str):
                    step = {"action": step}
                if not isinstance(step, dict):
                    continue
                action = (
                    step.get("action")
                    or step.get("step_description")
                    or step.get("description")
                    or step.get("text")
                )
                if not action:
                    continue
                parameters = step.get("parameters") if isinstance(step.get("parameters"), dict) else {}
                steps.append(
                    {
                        "step_number": step.get("step_number") or step.get("number") or step_index,
                        "action": str(action),
                        "parameters": parameters,
                        "source_ids": step.get("source_ids") if isinstance(step.get("source_ids"), list) else [],
                        "assumptions": step.get("assumptions") if isinstance(step.get("assumptions"), list) else [],
                        "missing_information": (
                            step.get("missing_information")
                            if isinstance(step.get("missing_information"), list)
                            else []
                        ),
                    }
                )

            if phase_name and steps:
                normalized.append(
                    {
                        "phase_name": str(phase_name),
                        "purpose": str(phase.get("purpose") or phase.get("description") or "Researcher review phase"),
                        "steps": steps,
                        "source_ids": phase.get("source_ids") if isinstance(phase.get("source_ids"), list) else [],
                    }
                )
        return normalized


class SafetyReview(BaseModel):
    risk_level: RiskLevel = "low_risk"
    flags: list[str] = Field(default_factory=list)
    requires_expert_review: bool = False
    notes: list[str] = Field(default_factory=list)


class EntityValidation(BaseModel):
    entity: str
    type: str
    normalized_name: str
    status: str
    source: str = "internal_normalization"


class ExtractedProtocolEvidence(BaseModel):
    source_id: str
    title: str
    steps: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_methods: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ProtocolVerifierReport(BaseModel):
    passed: bool
    warnings: list[str] = Field(default_factory=list)
    unsupported_sections: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)


ValidationStatus = Literal["pass", "needs_revision", "blocked"]


class ProtocolValidationIssue(BaseModel):
    section: str
    severity: Literal["low", "medium", "high"]
    issue: str
    suggestion: str
    requires_researcher_review: bool = True


class ProtocolValidationReport(BaseModel):
    overall_status: ValidationStatus
    grounding_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    safety_status: RiskLevel
    issues: list[ProtocolValidationIssue] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    can_show_to_researcher: bool = True


class FeedbackMemoryReference(BaseModel):
    id: str
    memory_text: str
    domain: str | None = None
    experiment_type: str | None = None
    model_system: str | None = None
    intervention: str | None = None
    outcome: str | None = None
    section: str | None = None
    distance: float | None = None
    search_backend: str = "sqlite"


class CorpusExampleReference(BaseModel):
    id: str
    source: str
    domain: str | None = None
    experiment_type: str | None = None
    summary: str
    structure_notes: list[str] = Field(default_factory=list)
    score: float = 0.0
    search_backend: str = "bm25_metadata_rapidfuzz"


class CustomProtocolDraft(BaseModel):
    title: str
    goal: str
    experiment_type: str | None = None
    source_evidence_used: list[str] = Field(default_factory=list)
    scientific_rationale: ProtocolSection
    materials_and_reagents: ProtocolSection
    adapted_workflow: ProtocolSection
    controls: ProtocolSection
    validation_readout: ProtocolSection
    safety_review: SafetyReview = Field(default_factory=SafetyReview)
    risks_and_limitations: ProtocolSection
    open_questions: list[str] = Field(default_factory=list)
    disclaimer: str = "Researcher-review draft. Must be reviewed by qualified personnel before execution."
    prior_feedback_used: list[FeedbackMemoryReference] = Field(default_factory=list)
    reference_examples_used: list[CorpusExampleReference] = Field(default_factory=list)
    validated_entities: list[EntityValidation] = Field(default_factory=list)
    extracted_protocol_evidence: list[ExtractedProtocolEvidence] = Field(default_factory=list)
    generation_backend: str | None = None
    generation_model: str | None = None
    reasoning_effort: str | None = None
    generation_error: str | None = None


FeedbackType = Literal["accept", "correction", "comment", "rejection"]
Severity = Literal["low", "medium", "high"]


class ProtocolSessionCreate(BaseModel):
    original_query: str = Field(..., min_length=3)
    structured_hypothesis: dict[str, Any]
    selected_papers: list[dict[str, Any]] = Field(default_factory=list)
    selected_protocols: list[dict[str, Any]] = Field(default_factory=list)
    lab_context: LabContext | None = None


class ProtocolFeedbackCreate(BaseModel):
    version_id: str
    section: str
    feedback_type: FeedbackType
    original_text: str | None = None
    feedback_text: str | None = None
    reason: str | None = None
    severity: Severity = "medium"
    reusable: bool = False


class ProtocolReviseRequest(BaseModel):
    version_id: str | None = None


class ProtocolAcceptRequest(BaseModel):
    version_id: str | None = None


class OperationalPlanRequest(BaseModel):
    version_id: str | None = None
    team_size: int = Field(default=2, ge=1, le=20)
    start_date: date | None = None
    workday_start: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    workday_end: str = Field(default="17:00", pattern=r"^\d{2}:\d{2}$")
    hours_per_day: float = Field(default=8, gt=0, le=16)
    workdays: list[str] = Field(
        default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    )
    skip_weekends: bool = True
    include_us_holidays: bool = False
    procurement_lead_days: int | None = Field(default=None, ge=0, le=90)

    @field_validator("workdays", mode="before")
    @classmethod
    def normalize_workdays(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or not value:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        return [str(item) for item in value if str(item).strip()]


class ProtocolVersionResponse(BaseModel):
    id: str
    session_id: str
    version_number: int
    parent_version_id: str | None = None
    protocol: CustomProtocolDraft
    verifier_report: ProtocolVerifierReport | None = None
    validation_report: ProtocolValidationReport | None = None
    change_summary: str | None = None
    status: str
    created_at: str


class ProtocolFeedbackResponse(BaseModel):
    id: str
    session_id: str
    version_id: str
    section: str
    feedback_type: str
    original_text: str | None = None
    feedback_text: str | None = None
    reason: str | None = None
    severity: str | None = None
    reusable: bool = False
    created_at: str


TransparencyStatus = Literal["waiting", "running", "completed", "warning", "failed"]


class TransparencyEventResponse(BaseModel):
    id: str
    session_id: str
    version_id: str | None = None
    stage: str
    status: TransparencyStatus
    user_message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ProtocolSessionDetail(BaseModel):
    id: str
    original_query: str
    structured_hypothesis: dict[str, Any]
    selected_papers: list[dict[str, Any]]
    selected_protocols: list[dict[str, Any]]
    lab_context: dict[str, Any] | None = None
    status: str
    accepted_version_id: str | None = None
    created_at: str
    versions: list[ProtocolVersionResponse] = Field(default_factory=list)
    feedback: list[ProtocolFeedbackResponse] = Field(default_factory=list)
