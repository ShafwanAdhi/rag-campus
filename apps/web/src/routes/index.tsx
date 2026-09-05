import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { chat, chatStream, type ChatResponse } from "@/lib/api";
import { ChatInput } from "@/components/ChatInput";
import { ProgressCard } from "@/components/ProgressCard";
import { AnswerCard } from "@/components/AnswerCard";
import { ProcessSummary } from "@/components/ProcessSummary";
import { SourceCard } from "@/components/SourceCard";
import { ParticleBackdrop } from "@/components/ParticleBackdrop";
import { cn } from "@/lib/utils";
import { AlertCircle } from "lucide-react";

const HIDDEN_CONTEXT_DOCUMENTS = new Set(["profil_umum_pengembang.pdf"]);

type ChatViewState = {
  query: string;
  loading: boolean;
  progress: number;
  progressMsg: string;
  error: string | null;
  result: ChatResponse | null;
};

let persistedChatState: ChatViewState = {
  query: "",
  loading: false,
  progress: 0,
  progressMsg: "",
  error: null,
  result: null,
};

function persistChatState(patch: Partial<ChatViewState>) {
  persistedChatState = {
    ...persistedChatState,
    ...patch,
  };
}

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Chat - SISDAS RAG Assistant" },
      {
        name: "description",
        content: "Tanyakan informasi akademik, beasiswa, tugas akhir, dan layanan kampus.",
      },
    ],
  }),
  component: ChatPage,
});

function ChatPage() {
  const [query, setQueryState] = useState(persistedChatState.query);
  const [loading, setLoadingState] = useState(persistedChatState.loading);
  const [progress, setProgressState] = useState(persistedChatState.progress);
  const [progressMsg, setProgressMsgState] = useState(persistedChatState.progressMsg);
  const [error, setErrorState] = useState<string | null>(persistedChatState.error);
  const [result, setResultState] = useState<ChatResponse | null>(persistedChatState.result);
  const cancelRef = useRef<(() => void) | null>(null);
  const resultTopRef = useRef<HTMLDivElement | null>(null);
  const scrollTimerRef = useRef<number | null>(null);
  const pendingResultScrollRef = useRef(false);

  useEffect(() => {
    persistChatState({ query, loading, progress, progressMsg, error, result });
  }, [query, loading, progress, progressMsg, error, result]);

  useEffect(() => {
    return () => {
      if (scrollTimerRef.current !== null) {
        window.clearTimeout(scrollTimerRef.current);
      }
    };
  }, []);

  const setQuery = (value: string) => {
    persistChatState({ query: value });
    setQueryState(value);
  };

  const setLoading = (value: boolean) => {
    persistChatState({ loading: value });
    setLoadingState(value);
  };

  const setProgress = (value: number) => {
    persistChatState({ progress: value });
    setProgressState(value);
  };

  const setProgressMsg = (value: string) => {
    persistChatState({ progressMsg: value });
    setProgressMsgState(value);
  };

  const setError = (value: string | null) => {
    persistChatState({ error: value });
    setErrorState(value);
  };

  const setResult = (value: ChatResponse | null) => {
    persistChatState({ result: value });
    setResultState(value);
  };

  const scrollToElementTop = (getElement: () => HTMLElement | null, offset = 16, delay = 0) => {
    if (scrollTimerRef.current !== null) {
      window.clearTimeout(scrollTimerRef.current);
    }

    scrollTimerRef.current = window.setTimeout(() => {
      scrollTimerRef.current = null;
      const element = getElement();
      if (!element) return;

      const main = document.querySelector("main");
      const scrollParent = main && main.scrollHeight > main.clientHeight ? main : null;

      const targetRect = element.getBoundingClientRect();
      if (!scrollParent) {
        const top = window.scrollY + targetRect.top - offset;
        window.scrollTo({ top: Math.max(top, 0), behavior: "smooth" });
        return;
      }

      const parentRect = scrollParent.getBoundingClientRect();
      const top = scrollParent.scrollTop + targetRect.top - parentRect.top - offset;
      scrollParent.scrollTo({ top: Math.max(top, 0), behavior: "smooth" });
    }, delay);
  };

  useEffect(() => {
    if (!pendingResultScrollRef.current || !result || loading) return;

    pendingResultScrollRef.current = false;
    scrollToElementTop(() => resultTopRef.current, 16, 620);
  }, [loading, result]);

  const submit = () => {
    const q = query.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(5);
    setProgressMsg("Menghubungi server...");

    cancelRef.current?.();
    cancelRef.current = chatStream(q, {
      onStatus: (s) => {
        if (typeof s.progress === "number") setProgress(s.progress);
        if (s.message) setProgressMsg(s.message);
      },
      onDone: (r) => {
        setResult(r);
        setProgress(100);
        pendingResultScrollRef.current = true;
        setLoading(false);
      },
      onError: async (msg) => {
        // fallback to standard /chat
        try {
          setProgressMsg("Streaming gagal, mencoba mode standar...");
          const r = await chat(q);
          setResult(r);
          pendingResultScrollRef.current = true;
          setLoading(false);
        } catch {
          setError(msg);
          setLoading(false);
        }
      },
    });
  };

  const cancel = () => {
    cancelRef.current?.();
    cancelRef.current = null;
    setLoading(false);
    setProgress(0);
    setProgressMsg("");
  };

  const hasOutput = loading || result || error;
  const visibleContexts = result?.contexts?.filter((context) => !isHiddenContext(context)) ?? [];

  return (
    <div className="motion-page-enter relative isolate min-h-full overflow-hidden">
      <ParticleBackdrop />
      <div
        className={cn(
          "relative z-10 mx-auto w-full max-w-5xl px-5 transition-[padding-top,padding-bottom] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] sm:px-6 md:px-8",
          hasOutput
            ? "pt-8 pb-[45vh] md:pt-10 md:pb-[42vh]"
            : "flex min-h-full flex-col justify-center py-8 md:min-h-screen md:pt-[clamp(5rem,20dvh,12rem)] md:pb-10",
        )}
      >
        {/* Hero */}
        <div className={hasOutput ? "mb-5 text-center md:mb-6" : "mb-8 text-center md:mb-10"}>
          <h1
            className={
              hasOutput
                ? "text-2xl md:text-3xl font-semibold tracking-tight text-foreground"
                : "text-3xl md:text-4xl font-semibold tracking-tight text-foreground"
            }
          >
            Cari Jawaban dari <br className="md:hidden" />
            Dokumen UM
          </h1>
        </div>

        <ChatInput value={query} onChange={setQuery} onSubmit={submit} loading={loading} />

        {hasOutput && (
          <div className="mt-6 space-y-5 md:mt-8">
            {loading && (
              <div className="motion-panel-enter">
                <ProgressCard progress={progress} message={progressMsg} onCancel={cancel} />
              </div>
            )}

            {error && !loading && (
              <div className="motion-panel-enter rounded-xl border border-destructive/30 bg-destructive/5 p-4 flex gap-3">
                <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                <div>
                  <div className="text-sm font-semibold text-destructive">
                    Gagal memproses permintaan
                  </div>
                  <p className="text-xs text-destructive/80 mt-1">{error}</p>
                </div>
              </div>
            )}

            {result && !loading && (
              <div ref={resultTopRef} className="motion-panel-enter space-y-5">
                <AnswerCard userQuery={result.user_query ?? query} answer={result.answer} />
                {!shouldHideEvidenceCards(result) && (
                  <>
                    <ProcessSummary data={result} />

                    {visibleContexts.length > 0 && (
                      <div>
                        <div className="mb-3 flex items-center gap-2">
                          <h3 className="text-sm font-semibold">Konteks Dokumen</h3>
                          <span className="text-xs text-muted-foreground">
                            ({visibleContexts.length})
                          </span>
                        </div>
                        <div className="grid md:grid-cols-2 gap-3">
                          {visibleContexts.map((c, i) => (
                            <SourceCard key={i} ctx={c} index={i} />
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function isHiddenContext(context: NonNullable<ChatResponse["contexts"]>[number]): boolean {
  const metadata = context.metadata ?? {};
  const fileName = getFileName(metadata.file_name ?? metadata.source);
  return fileName ? HIDDEN_CONTEXT_DOCUMENTS.has(fileName.toLowerCase()) : false;
}

function getFileName(value?: string): string | undefined {
  if (!value) return undefined;

  const parts = value.split(/[\\/]/);
  return decodeURIComponent(parts.at(-1) || value).trim();
}

function isFallbackUnknownAnswer(answer?: string): boolean {
  if (!answer) return false;

  const normalizedAnswer = answer.toLowerCase().replace(/\s+/g, " ").trim();

  return [
    "informasi tersebut tidak ditemukan secara jelas dalam dokumen yang tersedia",
    "informasi yang relevan tidak ditemukan dalam dokumen yang tersedia",
  ].some((message) => normalizedAnswer.includes(message));
}

function shouldHideEvidenceCards(result: ChatResponse): boolean {
  if (result.answer_status) {
    return result.answer_status !== "answered";
  }

  return isFallbackUnknownAnswer(result.answer);
}
