import type { ChatResponse } from "@/lib/api";
import { formatDomain } from "@/lib/format";

function Item({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground font-medium">
        {label}
      </div>
      <div className="text-sm font-semibold text-foreground mt-1 break-words">{value}</div>
    </div>
  );
}

export function ProcessSummary({ data }: { data: ChatResponse }) {
  const domains = data.route?.domains ?? [];
  const q = data.query_intent_adaptive_top_k ?? {};
  const rk = data.reranking_keyword?.summary ?? {};
  const errs = data.domain_errors ?? {};
  const errCount = Object.keys(errs).length;

  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-foreground">Ringkasan Proses</h3>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5">
        <Item label="Domain" value={domains.length ? domains.map(formatDomain).join(", ") : "-"} />
        <Item label="Intent Query" value={q.query_intent ?? "-"} />
        <Item label="Adaptive Top-K" value={q.adaptive_top_k ?? "-"} />
        <Item label="Konteks Digunakan" value={q.context_count_used ?? "-"} />
        <Item label="Chunk Ber-keyword" value={rk.chunks_with_keyword_count ?? "-"} />
        <Item label="Chunk Dipromosikan" value={rk.promoted_keyword_chunk_count ?? "-"} />
        <Item label="Domain Gagal" value={errCount > 0 ? errCount : "-"} />
      </div>
    </div>
  );
}
