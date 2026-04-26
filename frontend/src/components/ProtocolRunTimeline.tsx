import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react";
import type { TransparencyEvent, TransparencyEventStatus } from "../types";

const stages = [
  {
    key: "reading_selected_protocols",
    label: "Selected evidence",
    message: "Reading selected protocols.",
  },
  {
    key: "evidence_extraction",
    label: "Evidence extraction",
    message: "Extracting selected protocol evidence.",
  },
  {
    key: "corpus_example_retrieval",
    label: "Structure references",
    message: "Checking local protocol patterns.",
  },
  {
    key: "feedback_memory_retrieval",
    label: "Prior feedback",
    message: "Checking reusable feedback.",
  },
  {
    key: "safety_check",
    label: "Safety review",
    message: "Running safety checks.",
  },
  {
    key: "protocol_drafting",
    label: "Protocol composer",
    message: "Drafting protocol.",
  },
  {
    key: "protocol_validation",
    label: "Validation review",
    message: "Validating draft.",
  },
  {
    key: "ready_for_review",
    label: "Researcher review",
    message: "Ready for review.",
  },
];

type ProtocolRunTimelineProps = {
  events: TransparencyEvent[];
  isRunning: boolean;
};

function latestEventsByStage(events: TransparencyEvent[]) {
  return events.reduce<Record<string, TransparencyEvent>>((latest, event) => {
    latest[event.stage] = event;
    return latest;
  }, {});
}

function statusClass(status: TransparencyEventStatus) {
  if (status === "running") return "border-teal-200 bg-teal-50 text-teal-900";
  if (status === "completed") return "border-slate-200 bg-white text-slate-700";
  if (status === "warning") return "border-amber-200 bg-amber-50 text-amber-950";
  if (status === "failed") return "border-red-200 bg-red-50 text-red-900";
  return "border-slate-200 bg-slate-50 text-slate-500";
}

function StatusIcon({ status }: { status: TransparencyEventStatus }) {
  if (status === "running") {
    return <Loader2 className="h-4 w-4 animate-spin text-teal-700" aria-hidden="true" />;
  }
  if (status === "completed") {
    return <CheckCircle2 className="h-4 w-4 text-teal-700" aria-hidden="true" />;
  }
  if (status === "warning") {
    return <AlertTriangle className="h-4 w-4 text-amber-700" aria-hidden="true" />;
  }
  if (status === "failed") {
    return <XCircle className="h-4 w-4 text-red-700" aria-hidden="true" />;
  }
  return <Circle className="h-4 w-4 text-slate-400" aria-hidden="true" />;
}

export function ProtocolRunTimeline({ events, isRunning }: ProtocolRunTimelineProps) {
  const stageKeys = new Set(stages.map((stage) => stage.key));
  const protocolEvents = events.filter((event) => stageKeys.has(event.stage));
  const latest = latestEventsByStage(protocolEvents);
  const activeEvent = [...protocolEvents].reverse().find((event) => event.status === "running");
  const latestEvent = protocolEvents[protocolEvents.length - 1];
  const activeStage = stages.find((stage) => stage.key === activeEvent?.stage);
  const latestStage = stages.find((stage) => stage.key === latestEvent?.stage);
  const show = isRunning || protocolEvents.length > 0;

  if (!show) {
    return null;
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-1 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Protocol run</h3>
          <p className="mt-1 text-sm text-slate-600">
            {activeStage?.message ?? latestStage?.message ?? "Waiting."}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {stages.map((stage) => {
          const event = latest[stage.key];
          const status = event?.status ?? "waiting";
          return (
            <div
              key={stage.key}
              className={`rounded-md border px-3 py-2 transition ${statusClass(status)}`}
            >
              <div className="flex items-center gap-2">
                <StatusIcon status={status} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-950">{stage.label}</p>
                  <p className="text-xs font-medium text-slate-500">{status.replace(/_/g, " ")}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
