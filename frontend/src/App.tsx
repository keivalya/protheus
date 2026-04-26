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

function shortText(value = "", max = 140) {
  const clean = value.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max - 1).trim()}…` : clean;
}

function scoreLabel(score?: number) {
  if (typeof score !== "number") return "match";
  return `${Math.round(score)}%`;
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

function ProtocolCard({
  protocol,
  selected,
  onSelect,
}: {
  protocol: Protocol;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <article className={`candidate ${selected ? "is-selected" : ""}`}>
      <div>
        <div className="cand-head">
          <span className="source-badge">{protocol.source}</span>
          <span className="cand-meta">{scoreLabel(protocol.match_score)}</span>
        </div>
        <h4 className="cand-title">{protocol.title}</h4>
        <p className="cand-summary">
          {shortText(protocol.description || protocol.match_reason || "Source-linked protocol.")}
        </p>
      </div>
      <div className="cand-actions">
        {protocol.url ? (
          <a className="cand-link" href={protocol.url} target="_blank" rel="noreferrer">
            ↗
          </a>
        ) : null}
        <button className="cand-btn" type="button" onClick={onSelect}>
          {selected ? "Selected" : "Use this"}
        </button>
      </div>
    </article>
  );
}

function PaperList({ result }: { result: LiteratureQCResponse }) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3 className="card-title">Source papers</h3>
          <div className="card-sub">{result.papers.length} source records found.</div>
        </div>
      </div>
      <div className="card-body refs">
        {result.papers.slice(0, 5).map((paper, index) => (
          <a className="ref" href={paper.url || "#"} target="_blank" rel="noreferrer" key={paper.id}>
            <div className="ref-num">[{String(index + 1).padStart(2, "0")}]</div>
            <div>
              <div className="ref-title">{paper.title}</div>
              <div className="ref-meta">
                <b>{paper.authors?.slice(0, 3).join(", ") || paper.source}</b>
                {paper.year ? ` · ${paper.year}` : ""}
                {paper.doi ? ` · DOI ${paper.doi}` : ""}
              </div>
            </div>
          </a>
        ))}
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
        <h2>{protocol.title}</h2>
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
  const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeVersion, setActiveVersion] = useState<ProtocolVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const isWorking = Boolean(result || isBusy || error);
  const noveltyText = useMemo(() => {
    if (!result) return "";
    return `${result.qc.novelty_signal}. ${result.qc.explanation}`;
  }, [result]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isBusy) return;

    setIsBusy(true);
    setResult(null);
    setSelectedProtocol(null);
    setActiveVersion(null);
    setSessionId(null);
    setError(null);
    setStatus("Searching sources");

    try {
      const response = await runLiteratureQC(trimmed);
      setResult(response);
      setStatus(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Search failed.");
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleGenerate(protocol: Protocol) {
    if (!result || isBusy) return;
    setIsBusy(true);
    setError(null);
    setSelectedProtocol(protocol);
    setStatus("Drafting protocol");

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
      setStatus(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Protocol generation failed.");
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleAccept() {
    if (!sessionId || !activeVersion || isBusy) return;
    setIsBusy(true);
    setError(null);
    setStatus("Approving protocol");
    try {
      await acceptProtocol(sessionId, activeVersion.id);
      setStatus("Protocol approved");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Approval failed.");
      setStatus(null);
    } finally {
      setIsBusy(false);
    }
  }

  function reset() {
    setResult(null);
    setSelectedProtocol(null);
    setActiveVersion(null);
    setSessionId(null);
    setError(null);
    setStatus(null);
  }

  return (
    <div className={isWorking ? "app is-working" : "app"}>
      <header className="topbar">
        <div className="brand">
          <img className="mark" src="/logo.png" alt="" />
          <span className="name">Protheus</span>
        </div>
        <button className="gear-btn" type="button" aria-label="Settings">⚙</button>
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

            {status ? <div className="card status-card">{status}</div> : null}
            {error ? <div className="card error-card">{error}</div> : null}

            {result ? (
              <>
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h3 className="card-title">Literature QC</h3>
                      <div className="card-sub">{noveltyText}</div>
                    </div>
                  </div>
                </section>

                <div className="result-grid">
                  <PaperList result={result} />
                  <section className="card">
                    <div className="card-head">
                      <div>
                        <h3 className="card-title">Pick a base protocol</h3>
                        <div className="card-sub">Pick the closest source. The draft stays linked to it.</div>
                      </div>
                    </div>
                    <div className="card-body candidates">
                      {result.protocols.length ? (
                        result.protocols.slice(0, 6).map((protocol) => (
                          <ProtocolCard
                            key={protocol.id}
                            protocol={protocol}
                            selected={selectedProtocol?.id === protocol.id}
                            onSelect={() => void handleGenerate(protocol)}
                          />
                        ))
                      ) : (
                        <p className="empty">No protocol records found.</p>
                      )}
                    </div>
                  </section>
                </div>

                {activeVersion ? (
                  <ProtocolDraft version={activeVersion} onAccept={handleAccept} isBusy={isBusy} />
                ) : null}
              </>
            ) : null}
          </section>
        )}
      </main>
    </div>
  );
}
