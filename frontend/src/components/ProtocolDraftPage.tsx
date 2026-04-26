import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  RefreshCw,
  Save,
  StopCircle,
} from "lucide-react";
import {
  acceptProtocol,
  createProtocolSession,
  fetchProtocolEvents,
  generateProtocolDraft,
  reviseProtocolDraft,
  stopProtocolSession,
  submitProtocolFeedback,
} from "../api";
import { ProtocolRunTimeline } from "./ProtocolRunTimeline";
import type {
  CustomProtocolDraft,
  Protocol,
  ProtocolFeedbackType,
  ProtocolSection,
  ProtocolVersion,
  StructuredHypothesis,
  TransparencyEvent,
} from "../types";

type ProtocolSectionKey =
  | "scientific_rationale"
  | "materials_and_reagents"
  | "adapted_workflow"
  | "controls"
  | "validation_readout"
  | "risks_and_limitations";

const sectionKeys: ProtocolSectionKey[] = [
  "scientific_rationale",
  "materials_and_reagents",
  "adapted_workflow",
  "controls",
  "validation_readout",
  "risks_and_limitations",
];

const maxProtocolVersions = 3;

type FeedbackDraft = {
  feedbackText: string;
  savedLabel?: string;
};

type ProtocolDraftPageProps = {
  originalQuery: string;
  structuredHypothesis: StructuredHypothesis;
  selectedProtocols: Protocol[];
};

function riskLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function riskClass(value: string): string {
  if (value === "blocked_or_redacted") {
    return "border-red-200 bg-red-50 text-red-900";
  }
  if (value === "needs_expert_review") {
    return "border-amber-200 bg-amber-50 text-amber-950";
  }
  return "border-teal-200 bg-teal-50 text-teal-900";
}

function validationStatusClass(value?: string): string {
  if (value === "blocked") {
    return "border-red-200 bg-red-50 text-red-900";
  }
  if (value === "needs_revision") {
    return "border-amber-200 bg-amber-50 text-amber-950";
  }
  return "border-teal-200 bg-teal-50 text-teal-900";
}

function scientificLoopSummary(version: ProtocolVersion | null): string | null {
  if (!version?.validation_report) {
    return null;
  }
  const report = version.validation_report;
  const safety = report.safety_status.replace(/_/g, " ");
  const status = report.overall_status.replace(/_/g, " ");
  const issueSections = Array.from(new Set(report.issues.map((issue) => issue.section))).slice(0, 3);
  const issueText = issueSections.length ? ` Review: ${issueSections.join(", ")}.` : "";
  return `v${version.version_number}: ${status}. Safety ${safety}.${issueText}`;
}

function getSection(protocol: CustomProtocolDraft, key: ProtocolSectionKey): ProtocolSection {
  return protocol[key];
}

function emptyFeedback(): FeedbackDraft {
  return {
    feedbackText: "",
  };
}

function buttonClass(kind: "primary" | "secondary" | "danger" = "secondary") {
  if (kind === "primary") {
    return "inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-teal-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300";
  }
  if (kind === "danger") {
    return "inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800 transition hover:border-red-400 disabled:cursor-not-allowed disabled:opacity-60";
  }
  return "inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 transition hover:border-teal-600 disabled:cursor-not-allowed disabled:opacity-60";
}

function listPreview(items: string[], limit = 3): string {
  if (!items.length) {
    return "none";
  }
  const visible = items.slice(0, limit);
  const remainder = items.length - visible.length;
  return remainder > 0 ? `${visible.join("; ")}; more` : visible.join("; ");
}

function sectionEvidenceLabel(section: ProtocolSection): string {
  return section.source_ids.length ? "Selected protocol evidence" : "missing information";
}

function sectionReviewNotes(section: ProtocolSection): string[] {
  return [...section.missing_information, ...section.assumptions].slice(0, 3);
}

export function ProtocolDraftPage({
  originalQuery,
  structuredHypothesis,
  selectedProtocols,
}: ProtocolDraftPageProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [versions, setVersions] = useState<ProtocolVersion[]>([]);
  const [activeVersionId, setActiveVersionId] = useState<string | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TransparencyEvent[]>([]);
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<ProtocolSectionKey, FeedbackDraft>>(
    () =>
      sectionKeys.reduce(
        (drafts, key) => ({ ...drafts, [key]: emptyFeedback() }),
        {} as Record<ProtocolSectionKey, FeedbackDraft>,
      ),
  );
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const selectedEvidenceKey = useMemo(
    () =>
      [
        originalQuery,
        selectedProtocols.map((protocol) => protocol.id).join("|"),
      ].join("::"),
    [originalQuery, selectedProtocols],
  );

  useEffect(() => {
    setSessionId(null);
    setVersions([]);
    setActiveVersionId(null);
    setTimelineEvents([]);
    setError(null);
    setStatus(null);
    setFeedbackDrafts(
      sectionKeys.reduce(
        (drafts, key) => ({ ...drafts, [key]: emptyFeedback() }),
        {} as Record<ProtocolSectionKey, FeedbackDraft>,
      ),
    );
  }, [selectedEvidenceKey]);

  const loadTimelineEvents = useCallback(async (targetSessionId: string) => {
    try {
      const response = await fetchProtocolEvents(targetSessionId);
      setTimelineEvents(response.events);
    } catch {
      // Timeline polling should not interrupt protocol generation.
    }
  }, []);

  useEffect(() => {
    if (!sessionId || !isBusy) {
      return undefined;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetchProtocolEvents(sessionId);
        if (!cancelled) {
          setTimelineEvents(response.events);
        }
      } catch {
        return;
      }
    };
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 1200);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isBusy, sessionId]);

  const activeVersion = useMemo(
    () =>
      versions.find((version) => version.id === activeVersionId) ??
      versions[versions.length - 1] ??
      null,
    [activeVersionId, versions],
  );

  const canGenerate = selectedProtocols.length > 0;
  const validationReport = activeVersion?.validation_report ?? null;
  const isBlocked = validationReport?.overall_status === "blocked";
  const revisionLimitReached = Boolean(
    activeVersion && activeVersion.version_number >= maxProtocolVersions,
  );
  const loopSummary = useMemo(
    () => scientificLoopSummary(activeVersion),
    [activeVersion],
  );

  const handleGenerate = useCallback(async () => {
    if (!canGenerate || isBusy) {
      return;
    }

    setIsBusy(true);
    setError(null);
    setStatus("Generating protocol draft");

    try {
      const session =
        sessionId ??
        (
          await createProtocolSession({
            original_query: originalQuery,
            structured_hypothesis: structuredHypothesis,
            selected_papers: [],
            selected_protocols: selectedProtocols,
          })
        ).session_id;
      setSessionId(session);
      const response = await generateProtocolDraft(session);
      await loadTimelineEvents(session);
      setVersions((current) => [...current, response.version]);
      setActiveVersionId(response.version.id);
      setStatus(`Generated protocol v${response.version.version_number}`);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Protocol generation failed.",
      );
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }, [
    isBusy,
    loadTimelineEvents,
    originalQuery,
    canGenerate,
    selectedProtocols,
    sessionId,
    structuredHypothesis,
  ]);

  const updateFeedbackDraft = useCallback(
    (sectionKey: ProtocolSectionKey, patch: Partial<FeedbackDraft>) => {
      setFeedbackDrafts((current) => ({
        ...current,
        [sectionKey]: (() => {
          const next = {
            ...current[sectionKey],
            ...patch,
          };
          if (!Object.prototype.hasOwnProperty.call(patch, "savedLabel")) {
            next.savedLabel = undefined;
          }
          return next;
        })(),
      }));
    },
    [],
  );

  const handleSaveFeedback = useCallback(
    async (sectionKey: ProtocolSectionKey, feedbackType: ProtocolFeedbackType) => {
      if (!sessionId || !activeVersion || isBusy) {
        return;
      }
      const section = getSection(activeVersion.protocol, sectionKey);
      const draft = feedbackDrafts[sectionKey] ?? emptyFeedback();
      if (feedbackType !== "accept" && !draft.feedbackText.trim()) {
        updateFeedbackDraft(sectionKey, { savedLabel: "Add feedback text first" });
        return;
      }

      setIsBusy(true);
      setError(null);

      try {
        await submitProtocolFeedback({
          session_id: sessionId,
          version_id: activeVersion.id,
          section: sectionKey,
          feedback_type: feedbackType,
          original_text: section.content,
          feedback_text: feedbackType === "accept" ? null : draft.feedbackText.trim(),
          reason: null,
          severity: "medium",
          reusable: feedbackType === "correction",
        });
        updateFeedbackDraft(sectionKey, {
          savedLabel: feedbackType === "accept" ? "Section accepted" : "Feedback saved",
        });
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Saving feedback failed.",
        );
      } finally {
        setIsBusy(false);
      }
    },
    [activeVersion, feedbackDrafts, isBusy, sessionId, updateFeedbackDraft],
  );

  const handleRevise = useCallback(async () => {
    if (!sessionId || !activeVersion || isBusy || revisionLimitReached) {
      return;
    }

    setIsBusy(true);
    setError(null);
    setStatus("Generating revised protocol");

    try {
      const response = await reviseProtocolDraft(sessionId, activeVersion.id);
      await loadTimelineEvents(sessionId);
      setVersions((current) => [...current, response.version]);
      setActiveVersionId(response.version.id);
      setStatus(`Generated protocol v${response.version.version_number}`);
      setFeedbackDrafts(
        sectionKeys.reduce(
          (drafts, key) => ({ ...drafts, [key]: emptyFeedback() }),
          {} as Record<ProtocolSectionKey, FeedbackDraft>,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Protocol revision failed.",
      );
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }, [activeVersion, isBusy, loadTimelineEvents, revisionLimitReached, sessionId]);

  const handleAccept = useCallback(async () => {
    if (!sessionId || !activeVersion || isBusy) {
      return;
    }

    setIsBusy(true);
    setError(null);
    setStatus("Accepting protocol");

    try {
      const response = await acceptProtocol(sessionId, activeVersion.id);
      await loadTimelineEvents(sessionId);
      setVersions(response.session?.versions ?? versions);
      setStatus(
        `Accepted v${activeVersion.version_number}; saved ${response.memories_saved.length} reusable memory item${response.memories_saved.length === 1 ? "" : "s"}.`,
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Accepting protocol failed.",
      );
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }, [activeVersion, isBusy, loadTimelineEvents, sessionId, versions]);

  const handleStop = useCallback(async () => {
    if (!sessionId || isBusy) {
      return;
    }

    setIsBusy(true);
    setError(null);
    setStatus("Stopping session");

    try {
      await stopProtocolSession(sessionId);
      await loadTimelineEvents(sessionId);
      setStatus("Session stopped");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Stopping session failed.",
      );
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }, [isBusy, loadTimelineEvents, sessionId]);

  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Custom protocol generation</h2>
            <p className="mt-1 text-sm text-slate-600">
              {selectedProtocols.length} selected protocol
              {selectedProtocols.length === 1 ? "" : "s"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!activeVersion ? (
              <button
                type="button"
                className={buttonClass("primary")}
                onClick={handleGenerate}
                disabled={!canGenerate || isBusy}
              >
                <FlaskConical className="h-4 w-4" aria-hidden="true" />
                Generate Custom Protocol
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className={buttonClass()}
                  onClick={handleRevise}
                  disabled={!sessionId || isBusy || revisionLimitReached}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Revise
                </button>
                <button
                  type="button"
                  className={buttonClass("primary")}
                  onClick={handleAccept}
                  disabled={!sessionId || isBusy || isBlocked}
                >
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Accept
                </button>
                <button
                  type="button"
                  className={buttonClass("danger")}
                  onClick={handleStop}
                  disabled={!sessionId || isBusy}
                >
                  <StopCircle className="h-4 w-4" aria-hidden="true" />
                  Stop
                </button>
              </>
            )}
          </div>
        </div>

        {status ? (
          <p className="mt-4 text-sm font-medium text-teal-800">{status}</p>
        ) : null}
        {error ? (
          <p className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">
            {error}
          </p>
        ) : null}
        {revisionLimitReached ? (
          <p className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
            {loopSummary ??
              "Revision limit reached."}
          </p>
        ) : null}
      </div>

      <ProtocolRunTimeline events={timelineEvents} isRunning={isBusy && Boolean(sessionId)} />

      {versions.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {versions.map((version) => (
            <button
              key={version.id}
              type="button"
              onClick={() => setActiveVersionId(version.id)}
              className={`inline-flex min-h-9 items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold transition ${
                version.id === activeVersion?.id
                  ? "border-teal-700 bg-teal-50 text-teal-900"
                  : "border-slate-300 bg-white text-slate-700 hover:border-teal-500"
              }`}
            >
              v{version.version_number}
              {version.status === "accepted" ? (
                <CheckCircle2 className="h-4 w-4 text-teal-700" aria-hidden="true" />
              ) : null}
            </button>
          ))}
        </div>
      ) : null}

      {activeVersion ? (
        <div className="grid gap-4">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-wide text-teal-800">
                  Protocol v{activeVersion.version_number}
                </p>
                <h3 className="mt-1 text-xl font-semibold text-slate-950">
                  {activeVersion.protocol.title}
                </h3>
                {activeVersion.protocol.experiment_type ? (
                  <p className="mt-1 text-sm font-medium text-slate-600">
                    {activeVersion.protocol.experiment_type}
                  </p>
                ) : null}
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {activeVersion.protocol.goal}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 md:justify-end">
                <span
                  className={`inline-flex w-fit items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold ${riskClass(activeVersion.protocol.safety_review.risk_level)}`}
                >
                  <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                  {riskLabel(activeVersion.protocol.safety_review.risk_level)}
                </span>
                {activeVersion.protocol.prior_feedback_used.length ? (
                  <span className="w-fit rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                    prior feedback applied
                  </span>
                ) : null}
                {validationReport ? (
                  <span
                    className={`w-fit rounded-md border px-2.5 py-1 text-xs font-semibold ${validationStatusClass(validationReport.overall_status)}`}
                  >
                    {validationReport.overall_status.replace(/_/g, " ")}
                  </span>
                ) : null}
              </div>
            </div>

            {activeVersion.change_summary ? (
              <p className="mt-3 text-sm text-slate-600">{activeVersion.change_summary}</p>
            ) : null}

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-950">Evidence</p>
                <p className="mt-1 text-sm text-slate-700">
                  {listPreview(selectedProtocols.map((protocol) => protocol.title))}
                </p>
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-950">Safety</p>
                <p className="mt-1 text-sm text-slate-700">
                  {activeVersion.protocol.safety_review.requires_expert_review
                    ? "Expert review required"
                    : "Standard review"}
                </p>
                {activeVersion.protocol.safety_review.flags.length ? (
                  <p className="mt-1 text-sm text-slate-700">
                    {activeVersion.protocol.safety_review.flags.join(", ")}
                  </p>
                ) : null}
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-950">Validation</p>
                <p className="mt-1 text-sm text-slate-700">
                  {validationReport
                    ? validationReport.overall_status.replace(/_/g, " ")
                    : activeVersion.verifier_report?.passed
                      ? "pass"
                      : "needs review"}
                </p>
                {validationReport?.issues.length ? (
                  <p className="mt-1 text-sm text-slate-700">
                    {listPreview(validationReport.issues.map((issue) => issue.section))}
                  </p>
                ) : null}
              </div>
            </div>

            {validationReport ? (
              <div className={`mt-4 rounded-md border p-3 ${validationStatusClass(validationReport.overall_status)}`}>
                <p className="text-sm font-semibold">Review summary</p>
                {validationReport.issues.length ? (
                  <div className="mt-3 grid gap-2">
                    {validationReport.issues.slice(0, 3).map((issue, index) => (
                      <div
                        key={`${issue.section}-${issue.issue}-${index}`}
                        className="rounded-md border border-current/20 bg-white/60 p-2 text-sm"
                      >
                        <p className="font-semibold">
                          {issue.section.replace(/_/g, " ")} · {issue.severity}
                        </p>
                        <p className="mt-1">{issue.issue}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm">No validation issues reported.</p>
                )}

                {validationReport.missing_information.length ? (
                  <div className="mt-3 text-sm">
                    <p className="font-semibold">Missing information</p>
                    <p className="mt-1">{listPreview(validationReport.missing_information, 4)}</p>
                  </div>
                ) : null}

                {validationReport.safety_flags.length ? (
                  <div className="mt-3 text-sm">
                    <p className="font-semibold">Safety flags</p>
                    <p className="mt-1">{validationReport.safety_flags.join(", ")}</p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          {isBlocked ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-900 shadow-soft">
              Blocked. Expert review required.
            </div>
          ) : null}

          {!isBlocked ? sectionKeys.map((sectionKey) => {
            const section = getSection(activeVersion.protocol, sectionKey);
            const draft = feedbackDrafts[sectionKey] ?? emptyFeedback();
            const reviewNotes = sectionReviewNotes(section);
            return (
              <article
                key={`${activeVersion.id}-${sectionKey}`}
                className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft"
              >
                <div>
                  <h4 className="text-base font-semibold text-slate-950">{section.title}</h4>
                  <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">
                    {section.content}
                  </p>
                </div>

                <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  <p>
                    <span className="font-semibold text-slate-900">Evidence: </span>
                    {sectionEvidenceLabel(section)}
                  </p>
                  {reviewNotes.length ? (
                    <p className="mt-1">
                      <span className="font-semibold text-slate-900">Needs review: </span>
                      {listPreview(reviewNotes)}
                    </p>
                  ) : null}
                </div>

                {section.items.length ? (
                  <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                    <p className="text-sm font-semibold text-slate-950">Materials</p>
                    <div className="mt-2 grid gap-1 text-sm text-slate-700">
                      {section.items.map((item) => (
                        <p key={`${sectionKey}-${item.name}`}>{item.name}</p>
                      ))}
                    </div>
                  </div>
                ) : null}

                {section.phases.length ? (
                  <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                    <p className="text-sm font-semibold text-slate-950">Workflow outline</p>
                    <div className="mt-2 grid gap-3 text-sm text-slate-700">
                      {section.phases.map((phase) => (
                        <div key={`${sectionKey}-${phase.phase_name}`}>
                          <p className="font-semibold text-slate-900">{phase.phase_name}</p>
                          <p>{phase.purpose}</p>
                          <div className="mt-1 grid gap-1">
                            {phase.steps.map((step) => (
                              <p key={`${phase.phase_name}-${step.step_number}`}>
                                {step.step_number}. {step.action}
                              </p>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="mt-4 flex flex-col gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className={buttonClass()}
                      onClick={() => handleSaveFeedback(sectionKey, "accept")}
                      disabled={isBusy}
                    >
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Accept section
                    </button>
                    {draft.savedLabel ? (
                      <span className="text-sm font-medium text-teal-800">{draft.savedLabel}</span>
                    ) : null}
                  </div>
                  <details className="rounded-md border border-slate-200 bg-slate-50 p-3">
                    <summary className="cursor-pointer text-sm font-semibold text-slate-800">
                      Request change
                    </summary>
                    <div className="mt-3 grid gap-3">
                      <textarea
                        value={draft.feedbackText}
                        onChange={(event) =>
                          updateFeedbackDraft(sectionKey, { feedbackText: event.target.value })
                        }
                        rows={3}
                        className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm leading-6 text-slate-900 outline-none focus:border-teal-700"
                        placeholder="Feedback"
                      />
                      <button
                        type="button"
                        className={buttonClass("primary")}
                        onClick={() => handleSaveFeedback(sectionKey, "correction")}
                        disabled={isBusy}
                      >
                        <RefreshCw className="h-4 w-4" aria-hidden="true" />
                        Save feedback
                      </button>
                    </div>
                  </details>
                </div>
              </article>
            );
          }) : null}

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
            <h4 className="text-base font-semibold text-slate-950">Open questions</h4>
            <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-700">
              {activeVersion.protocol.open_questions.length ? (
                activeVersion.protocol.open_questions.map((question) => (
                  <p key={question}>{question}</p>
                ))
              ) : (
                <p>missing information</p>
              )}
            </div>
            <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-950">
              {activeVersion.protocol.disclaimer}
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
