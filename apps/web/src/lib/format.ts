const DOMAIN_LABELS: Record<string, string> = {
  academic_administration: "Administrasi Akademik",
  finance_tuition_and_scholarship: "Keuangan & Beasiswa",
  thesis_final_project_and_graduation: "Tugas Akhir & Kelulusan",
  facilities_and_campus_services: "Fasilitas & Layanan",
  general_profile: "Profil Umum",
};

export function formatDomain(d: string): string {
  if (DOMAIN_LABELS[d]) return DOMAIN_LABELS[d];
  return d.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function fmtNum(n: number | undefined | null, digits = 3): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-";
  return Number(n).toFixed(digits);
}

export function fallback<T>(v: T | undefined | null, dflt = "-"): T | string {
  if (v === undefined || v === null || v === "") return dflt;
  return v;
}
