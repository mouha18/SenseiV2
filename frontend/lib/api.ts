const API_URL = process.env.NEXT_PUBLIC_API_URL;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    detail: unknown | null;
  };
}

export class ApiError extends Error {
  code: string;
  detail: unknown | null;

  constructor(body: ApiErrorBody) {
    super(body.error.message);
    this.code = body.error.code;
    this.detail = body.error.detail;
  }
}

// GET /health
export interface HealthResponse {
  status: string;
  version: string;
}

// POST /ingest/upload (multipart: file, session_id)
export interface UploadResponse {
  status: string;
  document_id: string;
  session_id: string;
  file_name: string;
  file_size_bytes: number;
  estimated_chunks: number;
}

// POST /ingest/cancel
export interface CancelRequest {
  document_id: string;
}

export interface CancelResponse {
  document_id: string;
  status: string;
}

// POST /chat/ask
export interface ChatRequest {
  session_id: string;
  question: string;
}

export type ResponseType = "socratic" | "direct" | "redirect" | "new_session_prompt";
export type SourceType = "rag" | "general" | null;

export interface ChatResponse {
  answer: string;
  response_type: ResponseType;
  source: SourceType;
  chunks_used: number;
  out_of_scope: boolean;
  new_session_required: boolean;
}

// POST /evaluate/feynman
export interface FeynmanRequest {
  session_id: string;
  concept: string;
  explanation: string;
}

export interface FeynmanScores {
  clear: number;
  concise: number;
  concrete: number;
  correct: number;
  coherent: number;
  complete: number;
  courteous: number;
}

export interface FeynmanCriticism {
  clear: string;
  concise: string;
  concrete: string;
  correct: string;
  coherent: string;
  complete: string;
  courteous: string;
}

export interface FeynmanResponse {
  concept: string;
  overall_score: number;
  scores: FeynmanScores;
  criticism: FeynmanCriticism;
  summary: string;
  retry_suggested: boolean;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json()) as ApiErrorBody;
    throw new ApiError(body);
  }

  return response.json() as Promise<T>;
}
