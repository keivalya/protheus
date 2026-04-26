import { ExternalLink } from "lucide-react";
import type { Protocol } from "../types";

type ProtocolResultsProps = {
  protocols: Protocol[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
};

function scoreLabel(score: number) {
  return `${Math.round(score * 100)}% match`;
}

function tierLabel(tier: Protocol["match_tier"]) {
  if (tier === "strong_match") return "Strong";
  if (tier === "related_protocol") return "Related";
  if (tier === "weak_match") return "Weak";
  return null;
}

export function ProtocolResults({ protocols, selectedIds, onToggle }: ProtocolResultsProps) {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Protocols to review</h2>
          <p className="text-sm text-slate-600">{protocols.length} protocols.io results</p>
        </div>
      </div>

      {protocols.length ? (
        <div className="grid gap-3">
          {protocols.map((protocol) => (
            <article
              key={protocol.id}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-soft"
            >
              <div className="flex gap-3">
                <input
                  type="checkbox"
                  checked={selectedIds.has(protocol.id)}
                  onChange={() => onToggle(protocol.id)}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-700"
                  aria-label={`Select protocol ${protocol.title}`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="break-words text-base font-semibold leading-6 text-slate-950">
                        {protocol.title}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {protocol.source}
                        {protocol.year ? ` · ${protocol.year}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-end">
                      <span className="w-fit rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                        {tierLabel(protocol.match_tier) ? `${tierLabel(protocol.match_tier)} · ` : ""}
                        {scoreLabel(protocol.match_score)}
                      </span>
                      {protocol.url ? (
                        <a
                          href={protocol.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1 text-xs font-semibold text-teal-700 transition hover:border-teal-700 hover:text-teal-900"
                        >
                          Protocol
                          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                        </a>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
          No protocols returned.
        </div>
      )}
    </section>
  );
}
