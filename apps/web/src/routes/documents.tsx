import { createFileRoute } from "@tanstack/react-router";
import { DOCUMENT_DOMAINS } from "@/lib/documents";
import { ChevronDown, ExternalLink } from "lucide-react";
import { useEffect, useState, type MouseEvent } from "react";

const HIDDEN_DOCUMENTS = new Set(["profil_umum_pengembang.pdf"]);

export const Route = createFileRoute("/documents")({
  head: () => ({
    meta: [
      { title: "Dokumen - SISDAS RAG Assistant" },
      { name: "description", content: "Daftar dokumen kampus yang digunakan oleh sistem RAG." },
    ],
  }),
  component: DocumentsPage,
});

function DocumentsPage() {
  const visibleDomains = DOCUMENT_DOMAINS.map((domain) => ({
    ...domain,
    documents: domain.documents.filter((document) => !HIDDEN_DOCUMENTS.has(document.name)),
  })).filter((domain) => domain.documents.length > 0);
  const orderedDomains = [
    ...visibleDomains.filter((domain) => domain.key !== "general_profile").slice(0, 2),
    ...visibleDomains.filter((domain) => domain.key === "general_profile"),
    ...visibleDomains.filter((domain) => domain.key !== "general_profile").slice(2),
  ];

  return (
    <div className="motion-page-enter mx-auto w-full max-w-5xl select-none px-5 py-8 sm:px-6 md:px-8 md:py-10">
      <div className="mb-8 text-center">
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">
          Dokumen yang Digunakan
        </h1>
      </div>

      <div className="motion-stack-enter grid min-w-0 gap-4">
        {orderedDomains.map((d, domainIndex) => {
          return <DocumentDomain key={d.key} domain={d} initiallyOpen={domainIndex === 0} />;
        })}
      </div>
    </div>
  );
}

type DocumentDomainProps = {
  domain: (typeof DOCUMENT_DOMAINS)[number];
  initiallyOpen: boolean;
};

function DocumentDomain({ domain, initiallyOpen }: DocumentDomainProps) {
  const [open, setOpen] = useState(initiallyOpen);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (!closing) return;

    const timeout = window.setTimeout(() => {
      setOpen(false);
      setClosing(false);
    }, 300);

    return () => window.clearTimeout(timeout);
  }, [closing]);

  const toggle = (event: MouseEvent<HTMLElement>) => {
    event.preventDefault();

    if (closing) {
      setClosing(false);
      return;
    }

    if (open) {
      setClosing(true);
      return;
    }

    setOpen(true);
  };

  return (
    <section
      className="document-domain-card group min-w-0 rounded-xl border bg-card p-4 md:p-5"
      data-open={open && !closing ? "true" : undefined}
      data-closing={closing ? "true" : undefined}
    >
      <button
        type="button"
        aria-expanded={open && !closing}
        onClick={toggle}
        className="flex w-full min-w-0 cursor-pointer flex-wrap items-start gap-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        <div className="min-w-0 flex-1 basis-56">
          <h3 className="font-semibold text-foreground">{domain.title}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">{domain.description}</p>
        </div>
        <ChevronDown className="document-domain-chevron h-4 w-4 shrink-0 text-muted-foreground" />
      </button>
      {open && (
        <ul className="motion-documents-list mt-4 min-w-0 divide-y divide-border/60 rounded-lg border bg-background/40 overflow-hidden">
          {domain.documents.map((doc) => (
            <li key={doc.name} className="motion-document-item min-w-0">
              <a
                href={doc.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex min-h-11 min-w-0 items-center gap-3 px-3 py-2.5 text-sm hover:bg-accent/50 transition"
              >
                <span className="min-w-0 flex-1 truncate text-foreground/80 group-hover:text-foreground">
                  {doc.name}
                </span>
                <ExternalLink
                  aria-hidden="true"
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition group-hover:text-primary"
                />
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
