import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "Tentang - SISDAS RAG Assistant" },
      { name: "description", content: "Tentang sistem SISDAS RAG Assistant dan cara kerjanya." },
    ],
  }),
  component: AboutPage,
});

const capabilities = [
  {
    title: "Jawaban Berbasis Dokumen",
    desc: "Menjawab pertanyaan akademik dengan rujukan dokumen kampus.",
  },
  {
    title: "Konteks Sumber",
    desc: "Menampilkan potongan dokumen yang menjadi dasar jawaban.",
  },
  {
    title: "Ringkasan Proses",
    desc: "Menyajikan ringkasan proses retrieval dan reranking.",
  },
  {
    title: "Respons Streaming",
    desc: "Menampilkan progres pemrosesan secara real-time.",
  },
];

const steps = [
  "User mengirim pertanyaan melalui chat.",
  "Query planner mengecek apakah pertanyaan dapat dijawab dari structured facts, seperti rektor, akreditasi, lokasi, fakultas, prodi, atau sarana umum.",
  "Jika structured facts cocok, sistem menjawab langsung dari data fakta dan tetap mengirim sumber dokumen secara terpisah.",
  "Jika perlu pencarian dokumen, router memilih satu atau beberapa domain yang paling relevan.",
  "Analyzer domain menentukan intent, filter metadata, dan kata kunci reranking. Jika model terkena limit, fallback analyzer digunakan pada domain yang tersedia.",
  "Sistem mengambil chunk dari Chroma dengan embedding Voyage dan hybrid search berbasis vektor serta BM25.",
  "Konteks diperluas dengan chunk tetangga, lalu diranking ulang dengan reranker formal berbasis skor retrieval, metadata, dan kecocokan keyword.",
  "Generator Groq menyusun jawaban dari konteks terbaik. Jika generator gagal, sistem membuat fallback ekstraktif dari konteks yang sudah ditemukan.",
  "UI menampilkan jawaban, sumber terstruktur, konteks dokumen, dan timing tiap step. Jika jawaban tidak ditemukan, card proses dan konteks disembunyikan.",
];

const developerLinks = [
  {
    label: "GitHub",
    href: "https://github.com/ShafwanAdhi",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6 fill-current">
        <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.1 3.29 9.42 7.86 10.95.58.1.79-.25.79-.56v-2.02c-3.2.7-3.88-1.54-3.88-1.54-.52-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.76 2.7 1.25 3.36.95.1-.75.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .98-.31 3.17 1.18A11.1 11.1 0 0 1 12 5.48c.98 0 1.96.13 2.88.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.41-5.26 5.7.42.36.78 1.06.78 2.14v3.71c0 .31.21.67.8.56A11.52 11.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
      </svg>
    ),
  },
  {
    label: "Gmail",
    href: "mailto:shafwan.adhi.dwi@gmail.com",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6">
        <path fill="#4285F4" d="M21.5 6.92v10.16c0 .78-.64 1.42-1.42 1.42h-2.86V9.67L12 13.58 6.78 9.67V18.5H3.92c-.78 0-1.42-.64-1.42-1.42V6.92c0-.38.15-.74.42-1l9.08 6.8 9.08-6.8c.27.26.42.62.42 1Z" />
        <path fill="#34A853" d="M6.78 9.67V18.5H3.92c-.78 0-1.42-.64-1.42-1.42V6.92c0-.38.15-.74.42-1l3.86 2.89v.86Z" />
        <path fill="#FBBC04" d="M17.22 9.67V18.5h2.86c.78 0 1.42-.64 1.42-1.42V6.92c0-.38-.15-.74-.42-1l-3.86 2.89v.86Z" />
        <path fill="#EA4335" d="M12 13.58 2.92 6.78A1.42 1.42 0 0 1 4.42 4.5l7.58 5.69 7.58-5.69a1.42 1.42 0 0 1 1.5 2.28L12 13.58Z" />
      </svg>
    ),
  },
  {
    label: "LinkedIn",
    href: "https://www.linkedin.com/in/shafwan-adhi-dwi-nugraha-b90943321",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6 fill-current">
        <path d="M20.45 20.45h-3.56v-5.58c0-1.33-.03-3.04-1.86-3.04-1.86 0-2.14 1.45-2.14 2.95v5.67H9.33V9h3.42v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.31 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12Zm1.78 13.02H3.52V9h3.57v11.45ZM22.23 0H1.76C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.76 24h20.47c.98 0 1.77-.77 1.77-1.72V1.72C24 .77 23.21 0 22.23 0Z" />
      </svg>
    ),
  },
];

function AboutPage() {
  return (
    <div className="motion-page-enter mx-auto w-full max-w-5xl px-5 py-8 sm:px-6 md:px-8 md:py-10">
      <div className="mb-8 text-center">
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">
          Tentang Sistem ini
        </h1>
      </div>

      <div className="rounded-xl border bg-card p-5 md:p-6 mb-6">
        <p className="text-sm leading-relaxed text-foreground/80">
          Sistem ini adalah antarmuka chatbot berbasis Retrieval-Augmented Generation. Sistem ini
          menggabungkan structured facts, routing domain, hybrid retrieval, reranking formal, dan
          jawaban berbasis konteks dokumen resmi{" "}
          <a
            href="https://um.ac.id"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
          >
            Universitas Negeri Malang
          </a>
          .
        </p>
      </div>

      <h2 className="text-lg font-semibold text-foreground mb-3">Kemampuan Utama</h2>
      <div className="motion-stack-enter grid sm:grid-cols-2 gap-3 mb-8">
        {capabilities.map((c) => (
          <div key={c.title} className="rounded-xl border bg-card p-4">
            <h3 className="mb-2 text-sm font-semibold">{c.title}</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">{c.desc}</p>
          </div>
        ))}
      </div>

      <h2 className="text-lg font-semibold text-foreground mb-3">Cara Kerja Sistem</h2>
      <ol className="motion-stack-enter space-y-2">
        {steps.map((s, i) => (
          <li key={i} className="rounded-xl border bg-card p-4">
            <span className="text-sm text-foreground/80">
              {i + 1}. {s}
            </span>
          </li>
        ))}
      </ol>

      <h2 className="text-lg font-semibold text-foreground mt-10 mb-3">Pengembang</h2>
      <div className="rounded-xl border bg-card p-5 md:p-6">
        <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
          <div className="relative h-28 w-28 shrink-0 overflow-hidden rounded-full bg-accent text-accent-foreground">
            <div className="flex h-full w-full items-center justify-center text-2xl font-semibold">
              SA
            </div>
            <img
              src="/developer-shafwan.jpg"
              alt="Shafwan Adhi Dwi Nugraha"
              className="absolute inset-0 h-full w-full object-cover"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-foreground">Shafwan Adhi Dwi Nugraha</h3>
            <p className="mt-1 text-sm leading-relaxed text-foreground/80">
              Mahasiswa Teknik Informatika <br className="md:hidden" /> Universitas Negeri Malang.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2 sm:justify-start">
              {developerLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  target={link.href.startsWith("mailto:") ? undefined : "_blank"}
                  rel={link.href.startsWith("mailto:") ? undefined : "noreferrer"}
                  aria-label={link.label}
                  title={link.label}
                  className="flex h-11 w-11 items-center justify-center text-foreground/75 transition-transform duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] hover:-translate-y-0.5 hover:scale-110 hover:text-foreground"
                >
                  {link.icon}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
