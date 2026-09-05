import { API_BASE_URL } from "@/lib/api";

export type DocItem = {
  name: string;
  url: string;
  domainKey: string;
  domainTitle: string;
};
export type DocDomain = {
  key: string;
  title: string;
  description: string;
  documents: DocItem[];
};

function pdfUrl(domainKey: string, fileName: string): string {
  return `${API_BASE_URL}/documents/${domainKey}/${encodeURIComponent(fileName)}`;
}

function doc(domainKey: string, domainTitle: string, name: string): DocItem {
  return { name, url: pdfUrl(domainKey, name), domainKey, domainTitle };
}

export const DOMAIN_OPTIONS = [
  {
    key: "general_profile",
    title: "Profil Umum",
    shortTitle: "Profil",
    description: "Profil Universitas Negeri Malang dan profil pengembang sistem.",
    prompts: ["Di kota apa Universitas Negeri Malang berlokasi?", "Siapa pengembang sistem ini?"],
  },
  {
    key: "academic_administration",
    title: "Administrasi Akademik",
    shortTitle: "Akademik",
    description: "Cuti kuliah, KRS, kalender akademik, dan aturan akademik.",
    prompts: [
      "Bagaimana cara mengajukan cuti kuliah di Universitas Negeri Malang?",
      "Kapan registrasi akademik KRS Online semester gasal 2026/2027?",
    ],
  },
  {
    key: "finance_tuition_and_scholarship",
    title: "Keuangan & Beasiswa",
    shortTitle: "Keuangan",
    description: "UKT, registrasi pembayaran, bantuan UKT, dan beasiswa.",
    prompts: [
      "Kapan batas pembayaran UKT semester gasal 2025/2026?",
      "Apa saja syarat mendaftar Beasiswa Bank Indonesia?",
    ],
  },
  {
    key: "thesis_final_project_and_graduation",
    title: "Tugas Akhir & Kelulusan",
    shortTitle: "Tugas akhir",
    description: "Skripsi, pembimbingan, yudisium, dan wisuda.",
    prompts: ["Bagaimana prosedur pembimbingan skripsi?", "Apa ketentuan wisuda tahun 2025?"],
  },
  {
    key: "facilities_and_campus_services",
    title: "Fasilitas & Layanan Kampus",
    shortTitle: "Fasilitas",
    description: "Perpustakaan, laboratorium, studio, dan sarana kampus.",
    prompts: [
      "Apa saja sarana dan prasarana perpustakaan UM?",
      "Berapa tarif penggunaan alat laboratorium sosio?",
    ],
  },
] as const;

function domainTitle(domainKey: string): string {
  return DOMAIN_OPTIONS.find((domain) => domain.key === domainKey)?.title ?? domainKey;
}

export const DOCUMENT_DOMAINS: DocDomain[] = [
  {
    key: "general_profile",
    title: "Profil Umum",
    description: "Profil umum Universitas Negeri Malang.",
    documents: [
      doc("general_profile", "Profil Umum", "profil_umum_universitasnegerimalang.pdf"),
      doc("general_profile", "Profil Umum", "profil_umum_pengembang.pdf"),
    ],
  },
  {
    key: "academic_administration",
    title: "Administrasi Akademik",
    description:
      "Pedoman pendidikan, kalender akademik, dan peraturan akademik Universitas Negeri Malang.",
    documents: [
      doc("academic_administration", "Administrasi Akademik", "Kalender-Akademik-2026-2027.pdf"),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "KALENDER-AKADEMIK-UNIVERSITAS-NEGERI-MALANG-TAHUN-AKADEMIK-2024-2025.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "Pedoman-Pendidikan-Edisi-2020_Final.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "PER-NO-12-TAHUN-2018-PEDOMAN-PENDIDIKAN-UNIVERSITAS-NEGERI-MALANG-TAHUN-AKADEMIK-2018-2019.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "PER-NO-18-TAHUN-2018-PENYELENGGARAAN-PENDIDIKAN-UNIVERSITAS-NEGERI-MALANG.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "PER-NO-19-TAHUN-2018-TAHUN-AKADEMIK-KALENDER-AKADEMIK-DAN-SISTEM-ADMINISTRASI-AKADEMIK-UNIVERSITAS-NEGERI-MALANG.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "PER-NO-20-TAHUN-2018-KURIKULUM-UNIVERSITAS-NEGERI-MALANG.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "PER-NO-21-TAHUN-2018-PENILAIAN-DAN-PROSES-HASIL-BELAJAR-MAHASISWA-UNIVERSITAS-NEGERI-MALANG.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "PER-NO-28-TAHUN-2018-KEBEBASAN-AKADEMIK-KEBEBASAN-MIMBAR-AKADEMIK-DAN-OTONOMI-KEILMUAN-UNIVERSITAS-NEGERI-MALANG.pdf",
      ),
      doc(
        "academic_administration",
        "Administrasi Akademik",
        "Perubahan-Pedoman-Akademik-Edisi-2020-UM-.pdf",
      ),
    ],
  },
  {
    key: "facilities_and_campus_services",
    title: "Fasilitas & Layanan Kampus",
    description: "SOP laboratorium, studio, perpustakaan, serta sarana dan prasarana kampus.",
    documents: [
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "Sarana dan Prasarana perpustakaan um.pdf",
      ),
      doc("facilities_and_campus_services", "Fasilitas & Layanan Kampus", "Sarana Umum um.pdf"),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "SOP-GRAFIS-Tri-Wahyuningtyas.pdf",
      ),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "SOP-LAB-SOSIO-UM-Deny-Wahyu-Apriadi.pdf",
      ),
      doc("facilities_and_campus_services", "Fasilitas & Layanan Kampus", "SOP-LAB-TM-REF-7.pdf"),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "SOP-MEDIA-REKAM-Tri-Wahyuningtyas.pdf",
      ),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "SOP-STUDIO-LUKIS-Tri-Wahyuningtyas.pdf",
      ),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "SOP-STUDIO-MUSIK-Tri-Wahyuningtyas.pdf",
      ),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "SOP-STUDIO-TARI-Tri-Wahyuningtyas.pdf",
      ),
      doc(
        "facilities_and_campus_services",
        "Fasilitas & Layanan Kampus",
        "TARIF-PENGGUNAAN-ALAT-LAB-SOSIO-Deny-Wahyu-Apriadi.pdf",
      ),
    ],
  },
  {
    key: "finance_tuition_and_scholarship",
    title: "Keuangan & Beasiswa",
    description: "Informasi UKT, registrasi mahasiswa, dan beasiswa di Universitas Negeri Malang.",
    documents: [
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "11.-Universitas-Negeri-Malang-Rekomendasi-UKT-dan-IPI.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "Pengumuman-Bantuan-UKT-Semester-Gasal-TA-2021-2022.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "Pengumuman-Beasiswa-BI-UM-tahun-2024.pdf.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "PENGUMUMAN-PERPANJANGAN-REGISTRASI-KIP-K1.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "PENGUMUMAN-REGISTRASI-MABA-JALUR-UTBK-SNBT-2024.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "PENGUMUMAN-REGISTRASI-MAHASISWA-SEMESTER-GASAL-2024-2025.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "Registrasi-Mahasiswa-Semester-Gasal-Tahun-Akademik-2025-2026.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "Registrasi-Mahasiswa-Semester-Genap-2024-2025.pdf",
      ),
      doc(
        "finance_tuition_and_scholarship",
        "Keuangan & Beasiswa",
        "s-Panduan-Aplikasi-Pengajuan-UKT-Semester-Gasal-2020-min.pdf",
      ),
    ],
  },
  {
    key: "thesis_final_project_and_graduation",
    title: "Tugas Akhir & Kelulusan",
    description: "Pedoman skripsi, pembimbingan, yudisium, dan wisuda.",
    documents: [
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "KARTU-BIMBINGAN-SKRIPSI.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "LEMBAR-PERSETUJUAN-TEMA.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "PEDOMAN-PENULISAN-SKRIPSI-FPSI-2022.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "PER-NO-22-TAHUN-2018-YUDISIUM-DAN-WISUDA-UNIVERSITAS-NEGERI-MALANG.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "PERTOR-NO-44-TAHUN-2022-PERUBAHAN-KEDUA-ATAS-PERATURAN-REKTOR-UNIVERSITAS-NEGERI-MALANG-NOMOR-24-TAHUN-2020-TENTANG-PEDOMAN-PENDIDIKAN-EDISI-2020-1.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "SOP-Pembimbingan-Skripsi-Sah.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "SURAT-EDARAN-WISUDA-2025.pdf",
      ),
      doc(
        "thesis_final_project_and_graduation",
        "Tugas Akhir & Kelulusan",
        "Surat_Dinas-wisuda-132-Tahun-2025.pdf",
      ),
    ],
  },
];

export const ALL_DOCUMENTS = DOCUMENT_DOMAINS.flatMap((domain) =>
  domain.documents.map((document) => ({
    ...document,
    domainTitle: document.domainTitle || domainTitle(document.domainKey),
  })),
);
