export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ChatContext = {
  page_content?: string;
  final_score?: number;
  heuristic_score?: number;
  semantic_score?: number;
  lexical_score?: number;
  keyword_score?: number;
  keyword_match_count?: number;
  metadata_score?: number;
  vector_rank?: number;
  lexical_rank?: number;
  retrieval_channels?: string[];
  rerank_rank?: number;
  matched_rerank_keywords?: string[];
  metadata?: {
    file_name?: string;
    source?: string;
    page?: number;
    topic?: string;
  };
};

export type ChatSource = {
  file_name: string;
  url?: string;
  pages?: Array<string | number>;
  chunks?: Array<string | number>;
  domain?: string;
  topic?: string;
};

export type ChatResponse = {
  request_id?: string;
  user_query?: string;
  answer?: string;
  answer_status?: "answered" | "not_found" | "domain_error" | "no_domain";
  route?: { domains?: string[] };
  query_intent_adaptive_top_k?: {
    query_intent?: string;
    adaptive_top_k?: number;
    context_count_used?: number;
  };
  reranking_keyword?: {
    summary?: {
      chunks_with_keyword_count?: number;
      promoted_keyword_chunk_count?: number;
    };
  };
  domain_errors?: Record<string, unknown>;
  sources?: ChatSource[];
  contexts?: ChatContext[];
  retrieval_confidence?: {
    sufficient?: boolean;
    reason?: string;
    top_final_score?: number;
    top_keyword_bonus?: number;
    top_keyword_match_count?: number;
    top_distance?: number;
  };
  timings?: {
    routing_ms?: number;
    global_reranking_ms?: number;
    answer_generation_ms?: number;
    total_ms?: number;
    domains?: Record<
      string,
      {
        analysis_ms?: number;
        retrieval_ms?: number;
        reranking_ms?: number;
        total_ms?: number;
      }
    >;
  };
};

export type StreamStatus = {
  progress?: number;
  message?: string;
  elapsed_ms?: number;
};

export type StreamHandlers = {
  onStatus?: (s: StreamStatus) => void;
  onDone?: (r: ChatResponse) => void;
  onError?: (msg: string) => void;
};

export async function checkHealth(): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(`${API_BASE_URL}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    return res.ok;
  } catch {
    return false;
  }
}

export async function chat(query: string): Promise<ChatResponse> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 5 * 60 * 1000);
  try {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

export function chatStream(query: string, handlers: StreamHandlers): () => void {
  const url = `${API_BASE_URL}/chat/stream?query=${encodeURIComponent(query)}`;
  const es = new EventSource(url);
  let inactivityTimer: ReturnType<typeof setTimeout>;
  let closed = false;

  function cleanup() {
    if (closed) return;
    closed = true;
    clearTimeout(inactivityTimer);
    clearTimeout(overallTimer);
    es.close();
  }

  function resetInactivity() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => {
      handlers.onError?.("Koneksi tidak responsif (timeout 150 detik).");
      cleanup();
    }, 150_000);
  }

  const overallTimer = setTimeout(
    () => {
      handlers.onError?.("Permintaan melebihi batas waktu (5 menit).");
      cleanup();
    },
    5 * 60 * 1000,
  );

  resetInactivity();

  const parse = (raw: string) => {
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  };

  es.addEventListener("status", (ev: MessageEvent) => {
    resetInactivity();
    const data = parse(ev.data);
    if (data) handlers.onStatus?.(data);
  });

  es.addEventListener("done", (ev: MessageEvent) => {
    resetInactivity();
    const data = parse(ev.data);
    if (data) handlers.onDone?.(data);
    else handlers.onError?.("Respons tidak valid dari server.");
    cleanup();
  });

  es.addEventListener("error", (ev: MessageEvent) => {
    const data = ev.data ? parse(ev.data) : null;
    const msg = (data && (data.message as string)) || "Terjadi kesalahan pada koneksi streaming.";
    handlers.onError?.(msg);
    cleanup();
  });

  return cleanup;
}
