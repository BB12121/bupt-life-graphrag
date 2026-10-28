// Minimal typed integration example; complete schemas are in docs/openapi.json.
export type Campus = "shahe" | "haidian";
export interface QARequest {
  question: string;
  campus?: Campus | null;
  mode?: "hybrid" | "vector";
  entity_bindings?: Record<string, string>;
}
export interface Entity {
  id: string;
  type: "Campus" | "Place" | "Service" | "Platform" | "Condition";
  name: string;
  aliases: string[];
  campus: Campus | "shared" | "unknown";
  url: string | null;
}
export interface Evidence {
  id: string;
  doc_id: string;
  source_commit: string;
  source_path: string;
  heading: string;
  line_start: number;
  line_end: number;
  quote: string;
  source_url: string;
}
export interface QAResponse {
  status: "answered" | "partial" | "abstained" | "needs_clarification";
  reason: string | null;
  knowledge_revision: number;
  source_commit: string;
  answers: { text: string; entity_ids: string[]; path_ids: string[]; evidence_ids: string[] }[];
  paths: {
    id: string;
    branch_id: number;
    nodes: Entity[];
    edges: {
      subject_id: string;
      relation: "LOCATED_IN" | "PROVIDES" | "USES_PLATFORM" | "REQUIRES";
      object_id: string;
      evidence_ids: string[];
    }[];
  }[];
  evidence: Evidence[];
  warnings: string[];
  clarifications: {
    field: "campus" | "entity_bindings";
    mention: string;
    options: { value: string; label: string }[];
  }[];
}

export async function ask(request: QARequest, signal?: AbortSignal): Promise<QAResponse> {
  const response = await fetch("http://127.0.0.1:8000/api/v1/qa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message ?? `HTTP ${response.status}`);
  return body as QAResponse;
}

// On clarification: retain the original question, update campus/entity_bindings,
// and resend the entire request. Render answer.text and evidence.quote as text,
// never v-html. Reverse traversal does not reverse subject_id/object_id.
