import type { ChatContext } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { fmtNum } from "@/lib/format";
import { ALL_DOCUMENTS } from "@/lib/documents";
import { ExternalLink } from "lucide-react";

export function SourceCard({ ctx, index }: { ctx: ChatContext; index: number }) {
  const m = ctx.metadata ?? {};
  const rank = ctx.rerank_rank ?? index + 1;
  const kws = ctx.matched_rerank_keywords ?? [];
  const documentUrl = findDocumentUrl(m.file_name ?? m.source);
  const title = m.file_name ?? getFileName(m.source) ?? "Dokumen";

  const content = (
    <>
      <div className="mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-foreground truncate">{title}</span>
            <Badge variant="outline" className="text-[10px] font-medium">
              #{rank}
            </Badge>
            {documentUrl && (
              <ExternalLink className="ml-auto h-3.5 w-3.5 text-muted-foreground opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100" />
            )}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-muted-foreground">
            {m.page !== undefined && <span>Halaman {m.page}</span>}
            {m.topic && <span>Topik: {m.topic}</span>}
            {ctx.final_score !== undefined && <span>Skor: {fmtNum(ctx.final_score)}</span>}
          </div>
        </div>
      </div>

      {kws.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {kws.map((k) => (
            <Badge key={k} variant="secondary" className="text-[10px] font-normal">
              {k}
            </Badge>
          ))}
        </div>
      )}

      {ctx.page_content && (
        <p className="text-xs text-foreground/70 leading-relaxed line-clamp-4 whitespace-pre-wrap">
          {ctx.page_content}
        </p>
      )}
    </>
  );

  if (documentUrl) {
    return (
      <a
        href={documentUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="group block rounded-xl border bg-card p-4 transition hover:border-primary/40 hover:bg-accent/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        {content}
      </a>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-4 transition hover:border-primary/40">
      {content}
    </div>
  );
}

function findDocumentUrl(value?: string): string | undefined {
  const fileName = getFileName(value);
  if (!fileName) return undefined;

  const normalizedFileName = normalizeFileName(fileName);
  return ALL_DOCUMENTS.find((document) => normalizeFileName(document.name) === normalizedFileName)
    ?.url;
}

function getFileName(value?: string): string | undefined {
  if (!value) return undefined;

  const parts = value.split(/[\\/]/);
  return parts.at(-1) || value;
}

function normalizeFileName(value: string): string {
  return decodeURIComponent(value).trim().toLowerCase();
}
