import type {
  LabContext,
  LiteratureQCResponse,
  OperationalPlanRequest,
  OperationalPlanResponse,
  Paper,
  Protocol,
  ProtocolAcceptResponse,
  ProtocolFeedback,
  ProtocolFeedbackType,
  ProtocolGenerationResponse,
  ProtocolSessionDetail,
  TransparencyEventsResponse,
  StructuredHypothesis,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function runLiteratureQC(query: string): Promise<LiteratureQCResponse> {
  const response = await fetch(`${API_BASE}/api/literature-qc`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<LiteratureQCResponse>;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createProtocolSession(payload: {
  original_query: string;
  structured_hypothesis: StructuredHypothesis;
  selected_papers: Paper[];
  selected_protocols: Protocol[];
  lab_context?: LabContext | null;
}): Promise<{ session_id: string }> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<{ session_id: string }>(response);
}

export async function generateProtocolDraft(
  sessionId: string,
): Promise<ProtocolGenerationResponse> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/generate`, {
    method: "POST",
  });

  return parseJsonResponse<ProtocolGenerationResponse>(response);
}

export async function fetchProtocolEvents(
  sessionId: string,
): Promise<TransparencyEventsResponse> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/events`);

  return parseJsonResponse<TransparencyEventsResponse>(response);
}

export async function submitProtocolFeedback(payload: {
  session_id: string;
  version_id: string;
  section: string;
  feedback_type: ProtocolFeedbackType;
  original_text?: string | null;
  feedback_text?: string | null;
  reason?: string | null;
  severity?: "low" | "medium" | "high";
  reusable?: boolean;
}): Promise<ProtocolFeedback> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${payload.session_id}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      version_id: payload.version_id,
      section: payload.section,
      feedback_type: payload.feedback_type,
      original_text: payload.original_text,
      feedback_text: payload.feedback_text,
      reason: payload.reason,
      severity: payload.severity ?? "medium",
      reusable: payload.reusable ?? false,
    }),
  });

  return parseJsonResponse<ProtocolFeedback>(response);
}

export async function reviseProtocolDraft(
  sessionId: string,
  versionId: string,
): Promise<ProtocolGenerationResponse> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/revise`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ version_id: versionId }),
  });

  return parseJsonResponse<ProtocolGenerationResponse>(response);
}

export async function acceptProtocol(
  sessionId: string,
  versionId: string,
): Promise<ProtocolAcceptResponse> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/accept`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ version_id: versionId }),
  });

  return parseJsonResponse<ProtocolAcceptResponse>(response);
}

export async function stopProtocolSession(sessionId: string): Promise<{ session: ProtocolSessionDetail | null }> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/stop`, {
    method: "POST",
  });

  return parseJsonResponse<{ session: ProtocolSessionDetail | null }>(response);
}

export async function createOperationalPlan(
  sessionId: string,
  payload: OperationalPlanRequest = {},
): Promise<OperationalPlanResponse> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/operational-plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<OperationalPlanResponse>(response);
}

export async function fetchOperationalPlan(sessionId: string): Promise<OperationalPlanResponse> {
  const response = await fetch(`${API_BASE}/api/protocol-sessions/${sessionId}/operational-plan`);

  return parseJsonResponse<OperationalPlanResponse>(response);
}
