import { useEffect, useMemo, useState } from "react";
import {
  acceptProtocol,
  createProtocolSession,
  generateProtocolDraft,
  runLiteratureQC,
} from "./api";
import type {
  CustomProtocolDraft,
  LiteratureQCResponse,
  NoveltySignal,
  Paper,
  Protocol,
  ProtocolSection,
  ProtocolVersion,
} from "./types";

const heroLines = [
  { a: "From question to", b: "experiment in one step.", mark: "experiment" },
  { a: "From curiosity to", b: "experiment instantly.", mark: "experiment" },
  { a: "From idea to", b: "experiment you can run.", mark: "experiment" },
  { a: "From thought to trial", b: "without friction.", mark: "friction" },
  { a: "From wondering to", b: "working science.", mark: "science" },
  { a: "From question to", b: "protocol — beautifully simple.", mark: "protocol" },
  { a: "From idea to bench", b: "no steps wasted.", mark: "bench" },
  { a: "From hypothesis", b: "to hands-on.", mark: "hands-on" },
  { a: "From question", b: "to execution.", mark: "execution" },
  { a: "From curiosity", b: "to results.", mark: "results" },
  { a: "From idea to reality", b: "in one move.", mark: "reality" },
  { a: "From question", b: "to breakthrough.", mark: "breakthrough" },
  { a: "From thinking", b: "to doing.", mark: "doing" },
  { a: "From concept to", b: "controlled experiment.", mark: "experiment" },
  { a: "From question to clarity", b: "fast.", mark: "clarity" },
  { a: "From idea", b: "to evidence.", mark: "evidence" },
  { a: "From curiosity", b: "to confirmation.", mark: "confirmation" },
  { a: "From question", b: "to discovery.", mark: "discovery" },
  { a: "From hypothesis", b: "to proof.", mark: "proof" },
  { a: "From idea to insight", b: "instantly.", mark: "insight" },
];

const sectionKeys: Array<keyof CustomProtocolDraft> = [
  "scientific_rationale",
  "materials_and_reagents",
  "adapted_workflow",
  "controls",
  "validation_readout",
  "risks_and_limitations",
];

const STEP_LABELS = [
  "Question",
  "Literature QC",
  "Pick protocol",
  "Review & iterate",
  "Full plan",
];

type PickStage = "novelty" | "protocols";

function renderMarked(text: string, mark?: string) {
  if (!mark) return text;
  const idx = text.toLowerCase().lastIndexOf(mark.toLowerCase());
  if (idx < 0) return text;
  return (
    <>
      {text.slice(0, idx)}
      <em>{text.slice(idx, idx + mark.length)}</em>
      {text.slice(idx + mark.length)}
    </>
  );
}

function SciTitle({ html }: { html: string }) {
  const safe = html.replace(/<(?!\/?(?:sub|sup)\b)[^>]*>/gi, "");
  return <span dangerouslySetInnerHTML={{ __html: safe }} />;
}

function shortText(value = "", max = 140) {
  const clean = value.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max - 1).trim()}…` : clean;
}

function shortDoi(doi?: string | null) {
  if (!doi) return null;
  return doi.replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, "");
}

function noveltyPillText(signal: NoveltySignal) {
  switch (signal) {
    case "exact match found":
    case "similar work exists":
      return "Similar work exists";
    case "not found":
      return "Novel direction";
    default:
      return signal;
  }
}

function noveltyPillTone(signal: NoveltySignal) {
  switch (signal) {
    case "exact match found":
      return "warn";
    case "similar work exists":
      return "warn";
    case "not found":
      return "ok";
    default:
      return "info";
  }
}

function noveltyHeadline(signal: NoveltySignal) {
  switch (signal) {
    case "exact match found":
    case "similar work exists":
      return "Has this been done before?";
    case "not found":
      return "No close prior work found.";
    default:
      return "Prior work check";
  }
}

function noveltyCaption(signal: NoveltySignal) {
  switch (signal) {
    case "exact match found":
    case "similar work exists":
      return "Review the closest sources before claiming novelty.";
    case "not found":
      return "Proceed to draft a protocol from the closest available sources.";
    default:
      return "";
  }
}

function sectionBody(section: ProtocolSection) {
  if (section.phases?.length) {
    return section.phases
      .flatMap((phase) =>
        phase.steps.map((step) => `${step.step_number}. ${step.action}`),
      )
      .join("\n");
  }
  if (section.items?.length) {
    return section.items.map((item) => item.name).join("\n");
  }
  return section.content;
}

function HeroHeadline() {
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(
    heroLines[0].a.length + heroLines[0].b.length,
  );
  const [deleting, setDeleting] = useState(true);
  const [paused, setPaused] = useState(true);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const line = heroLines[lineIndex];
    const length = line.a.length + line.b.length;

    const timer = window.setTimeout(
      () => {
        if (paused) {
          setPaused(false);
          return;
        }
        if (deleting) {
          if (charIndex <= 0) {
            setDeleting(false);
            setLineIndex((current) => (current + 1) % heroLines.length);
            return;
          }
          setCharIndex((current) => current - 1);
          return;
        }
        if (charIndex >= length) {
          setDeleting(true);
          setPaused(true);
          return;
        }
        setCharIndex((current) => current + 1);
      },
      paused ? 3000 : deleting ? 22 : 42,
    );
    return () => window.clearTimeout(timer);
  }, [charIndex, deleting, lineIndex, paused]);

  useEffect(() => {
    setCharIndex(0);
  }, [lineIndex]);

  const line = heroLines[lineIndex];
  const complete = charIndex >= line.a.length + line.b.length;
  const first = line.a.slice(0, Math.min(charIndex, line.a.length));
  const second = charIndex > line.a.length ? line.b.slice(0, charIndex - line.a.length) : "";
  const cursorLine = charIndex <= line.a.length ? 1 : 2;

  return (
    <h1 className="hero-title" aria-live="polite">
      <span className="hero-line">
        {renderMarked(first, complete ? line.mark : undefined)}
        {cursorLine === 1 ? <span className="type-cursor" aria-hidden="true" /> : null}
      </span>
      <span className="hero-line">
        {renderMarked(second, complete ? line.mark : undefined)}
        {cursorLine === 2 ? <span className="type-cursor" aria-hidden="true" /> : null}
      </span>
    </h1>
  );
}

function LoadingBlock({
  title,
  subs,
  intervalMs = 700,
}: {
  title: string;
  subs: string[];
  intervalMs?: number;
}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
    if (subs.length <= 1) return;
    const id = window.setInterval(() => {
      setIndex((current) => (current + 1) % subs.length);
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [subs, intervalMs]);

  return (
    <section className="card loading-card">
      <div className="loading-block">
        <div className="spin" aria-hidden="true" />
        <div className="loading-text">
          {title}
          <small aria-live="polite">{subs[index] ?? ""}</small>
        </div>
      </div>
    </section>
  );
}

function StepNav({ step }: { step: number }) {
  return (
    <nav className="step-nav" aria-label="Progress">
      {STEP_LABELS.map((label, idx) => {
        const num = idx + 1;
        const state = num < step ? "done" : num === step ? "active" : "todo";
        return (
          <div key={label} className={`step is-${state}`}>
            <span className="step-bullet" aria-hidden="true">
              {state === "done" ? "✓" : num}
            </span>
            <span className="step-label">{label}</span>
          </div>
        );
      })}
    </nav>
  );
}

function PaperRef({ paper, index }: { paper: Paper; index: number }) {
  const num = String(index + 1).padStart(2, "0");
  const authors = paper.authors?.slice(0, 3).join(", ") || "";
  const doi = shortDoi(paper.doi);
  const meta: Array<{ key: string; node: React.ReactNode; tone?: "accent" }> = [];
  if (authors) meta.push({ key: "authors", node: <b>{authors}</b> });
  if (paper.year) meta.push({ key: "year", node: <span>{paper.year}</span> });
  if (doi) meta.push({ key: "doi", node: <span className="ref-doi">DOI {doi}</span>, tone: "accent" });
  if (paper.source && paper.source !== "Unknown") {
    meta.push({ key: "source", node: <span>{paper.source}</span> });
  }

  return (
    <a
      className="ref"
      href={paper.url || (doi ? `https://doi.org/${doi}` : "#")}
      target="_blank"
      rel="noreferrer"
    >
      <div className="ref-num">[{num}]</div>
      <div className="ref-body">
        <div className="ref-title">
          <SciTitle html={paper.title} />
          <span className="ref-link-icon" aria-hidden="true">↗</span>
        </div>
        {meta.length ? (
          <div className="ref-meta">
            {meta.map((item, i) => (
              <span key={item.key}>
                {item.node}
                {i < meta.length - 1 ? <span className="ref-sep"> · </span> : null}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </a>
  );
}

function NoveltyReview({
  result,
  onContinue,
  isBusy,
}: {
  result: LiteratureQCResponse;
  onContinue: () => void;
  isBusy: boolean;
}) {
  const signal = result.qc.novelty_signal;
  const tone = noveltyPillTone(signal);
  return (
    <section className="card novelty-card">
      <div className="card-head">
        <div>
          <h3 className="card-title">{noveltyHeadline(signal)}</h3>
          <div className="card-sub">{result.papers.length} source records found.</div>
        </div>
      </div>
      <div className="card-body">
        <div className={`novelty-row tone-${tone}`}>
          <span className={`novelty-pill tone-${tone}`}>
            <span className="pill-dot" aria-hidden="true" /> {noveltyPillText(signal)}
          </span>
          <p className="novelty-caption">{noveltyCaption(signal) || result.qc.explanation}</p>
        </div>
        <div className="refs">
          {result.papers.slice(0, 5).map((paper, index) => (
            <PaperRef key={paper.id} paper={paper} index={index} />
          ))}
          {!result.papers.length ? (
            <p className="empty">No source papers were returned.</p>
          ) : null}
        </div>
        <div className="novelty-actions">
          <button
            className="btn primary"
            type="button"
            onClick={onContinue}
            disabled={isBusy}
          >
            Find matching protocols <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>
    </section>
  );
}

function ProtocolCard({
  protocol,
  selected,
  onSelect,
  isBusy,
}: {
  protocol: Protocol;
  selected: boolean;
  onSelect: () => void;
  isBusy: boolean;
}) {
  return (
    <article className={`candidate ${selected ? "is-selected" : ""}`}>
      <div className="cand-main">
        <div className="cand-head">
          <span className="source-badge">{protocol.source}</span>
        </div>
        <h4 className="cand-title">
          <SciTitle html={protocol.title} />
        </h4>
        <p className="cand-summary">
          {shortText(protocol.description || protocol.match_reason || "Source-linked protocol.")}
        </p>
      </div>
      <div className="cand-actions">
        {protocol.url ? (
          <a className="cand-link" href={protocol.url} target="_blank" rel="noreferrer" aria-label="Open source">
            ↗
          </a>
        ) : null}
        <button className="cand-btn" type="button" onClick={onSelect} disabled={isBusy}>
          {selected ? "Selected" : "Use this"}
        </button>
      </div>
    </article>
  );
}

function ProtocolPicker({
  result,
  selectedProtocol,
  onSelect,
  onBack,
  isBusy,
}: {
  result: LiteratureQCResponse;
  selectedProtocol: Protocol | null;
  onSelect: (p: Protocol) => void;
  onBack: () => void;
  isBusy: boolean;
}) {
  return (
    <section className="card">
      <div className="card-head card-head-row">
        <div>
          <h3 className="card-title">Pick a base protocol</h3>
          <div className="card-sub">Pick the closest source. The draft stays linked to it.</div>
        </div>
        <button className="link-btn" type="button" onClick={onBack}>
          ← Back to sources
        </button>
      </div>
      <div className="card-body candidates">
        {result.protocols.length ? (
          result.protocols.slice(0, 6).map((protocol) => (
            <ProtocolCard
              key={protocol.id}
              protocol={protocol}
              selected={selectedProtocol?.id === protocol.id}
              onSelect={() => onSelect(protocol)}
              isBusy={isBusy}
            />
          ))
        ) : (
          <div className="empty-state">
            <p className="empty">No matching protocol records were returned.</p>
            <p className="empty-hint">
              The literature search did not find protocols.io entries that match this query.
              Try rephrasing the question with more specific assay or technique terms.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function ProtocolDraft({
  version,
  onAccept,
  isBusy,
}: {
  version: ProtocolVersion;
  onAccept: () => void;
  isBusy: boolean;
}) {
  const protocol = version.protocol;
  return (
    <section className="plan is-visible">
      <div className="plan-hero">
        <div className="eyebrow-row">
          <span className="dot" />
          <span>Protocol draft</span>
        </div>
        <h2><SciTitle html={protocol.title} /></h2>
        <p className="blurb">{protocol.goal}</p>
        <div className="plan-stats">
          <div className="stat">
            <span className="k">Grounding</span>
            <span className="v">{Math.round((version.validation_report?.grounding_score ?? 0) * 100)}%</span>
          </div>
          <div className="stat">
            <span className="k">Completeness</span>
            <span className="v">{Math.round((version.validation_report?.completeness_score ?? 0) * 100)}%</span>
          </div>
          <div className="stat">
            <span className="k">Safety</span>
            <span className="v">{protocol.safety_review.risk_level.replace(/_/g, " ")}</span>
          </div>
          <div className="stat">
            <span className="k">Version</span>
            <span className="v">v{version.version_number}</span>
          </div>
        </div>
      </div>
      <div className="protocol-sections">
        {sectionKeys.map((key) => {
          const section = protocol[key] as ProtocolSection;
          return (
            <article className="protocol-step" key={key}>
              <header>
                <div className="step-title">{section.title}</div>
                <div className="step-time">{Math.round(section.confidence * 100)}%</div>
              </header>
              <div className="step-body">
                {sectionBody(section)
                  .split("\n")
                  .filter(Boolean)
                  .map((line) => (
                    <p key={line}>{line}</p>
                  ))}
              </div>
              {section.missing_information.length || section.assumptions.length ? (
                <div className="step-meta">
                  {[...section.missing_information, ...section.assumptions].slice(0, 3).map((note) => (
                    <span key={note}>{note}</span>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
      <div className="plan-actions">
        <div className="meta">
          <span className="dot" />
          <span>{version.validation_report?.overall_status.replace(/_/g, " ") ?? "ready"}</span>
        </div>
        <span className="spacer" />
        <button className="btn primary" type="button" disabled={isBusy} onClick={onAccept}>
          Approve protocol
        </button>
      </div>
    </section>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<LiteratureQCResponse | null>(null);
  const [pickStage, setPickStage] = useState<PickStage>("novelty");
  const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeVersion, setActiveVersion] = useState<ProtocolVersion | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<{
    title: string;
    subs: string[];
    intervalMs?: number;
  } | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const isWorking = Boolean(result || isBusy || error);

  const currentStep = useMemo(() => {
    if (accepted) return 5;
    if (activeVersion) return 4;
    if (result) return 3;
    if (isBusy) return 2;
    return 1;
  }, [accepted, activeVersion, result, isBusy]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isBusy) return;

    setIsBusy(true);
    setResult(null);
    setSelectedProtocol(null);
    setActiveVersion(null);
    setSessionId(null);
    setAccepted(false);
    setPickStage("novelty");
    setError(null);
    setLoading({
      title: "Searching literature for prior art…",
      subs: [
        "PubMed · Crossref · arXiv",
        "Fetching source metadata…",
        "Normalizing DOI resolver links…",
        "Deduplicating evidence records…",
      ],
      intervalMs: 700,
    });

    try {
      const response = await runLiteratureQC(trimmed);
      setResult(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Search failed.");
    } finally {
      setLoading(null);
      setIsBusy(false);
    }
  }

  async function handleGenerate(protocol: Protocol) {
    if (!result || isBusy) return;
    setIsBusy(true);
    setError(null);
    setSelectedProtocol(protocol);
    setLoading({
      title: "Adapting the protocol to your question…",
      subs: [
        "Customizing steps with your sample & question parameters",
        "Cross-referencing materials & equipment",
        "Calibrating step-by-step instructions",
      ],
      intervalMs: 750,
    });

    try {
      const session =
        sessionId ??
        (
          await createProtocolSession({
            original_query: result.query,
            structured_hypothesis: result.structured_hypothesis,
            selected_papers: result.papers,
            selected_protocols: [protocol],
          })
        ).session_id;
      setSessionId(session);
      const draft = await generateProtocolDraft(session);
      setActiveVersion(draft.version);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Protocol generation failed.");
    } finally {
      setLoading(null);
      setIsBusy(false);
    }
  }

  async function handleAccept() {
    if (!sessionId || !activeVersion || isBusy) return;
    setIsBusy(true);
    setError(null);
    setLoading({
      title: "Approving protocol…",
      subs: [
        "Saving feedback memories for future drafts",
        "Indexing protocol provenance…",
      ],
      intervalMs: 750,
    });
    try {
      await acceptProtocol(sessionId, activeVersion.id);
      setAccepted(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Approval failed.");
    } finally {
      setLoading(null);
      setIsBusy(false);
    }
  }

  function reset() {
    setResult(null);
    setSelectedProtocol(null);
    setActiveVersion(null);
    setSessionId(null);
    setAccepted(false);
    setPickStage("novelty");
    setError(null);
    setLoading(null);
  }

  return (
    <div className={isWorking ? "app is-working" : "app"}>
      <header className="topbar">
        <div className="brand">
          <img className="mark" src="/logo.png" alt="" />
          <span className="name">Protheus</span>
        </div>
      </header>

      <main className="stage">
        {!isWorking ? (
          <section className="hero">
            <HeroHeadline />
            <p className="lede">Stop searching papers. Start running experiments.</p>
            <form className="ask-form" onSubmit={handleSubmit}>
              <div className="ask-input-wrap">
                <textarea
                  className="ask-input"
                  rows={1}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  placeholder="Ask a research question..."
                />
                <button className="ask-submit" type="submit" aria-label="Submit question">→</button>
              </div>
            </form>
          </section>
        ) : (
          <section className="work">
            <div className="question-bar">
              <div className="qtext">{query}</div>
              <button className="qedit" type="button" onClick={reset}>Edit · Restart</button>
            </div>

            <StepNav step={currentStep} />

            {loading ? (
              <LoadingBlock
                title={loading.title}
                subs={loading.subs}
                intervalMs={loading.intervalMs}
              />
            ) : null}
            {error ? <div className="card error-card">{error}</div> : null}

            {result && !activeVersion ? (
              pickStage === "novelty" ? (
                <NoveltyReview
                  result={result}
                  onContinue={() => setPickStage("protocols")}
                  isBusy={isBusy}
                />
              ) : (
                <ProtocolPicker
                  result={result}
                  selectedProtocol={selectedProtocol}
                  onSelect={handleGenerate}
                  onBack={() => setPickStage("novelty")}
                  isBusy={isBusy}
                />
              )
            ) : null}

            {activeVersion ? (
              <ProtocolDraft version={activeVersion} onAccept={handleAccept} isBusy={isBusy} />
            ) : null}
          </section>
        )}
      </main>
    </div>
  );
}
