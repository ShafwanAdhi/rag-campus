from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"


@dataclass(frozen=True)
class DomainConfig:
    key: str
    directory: str
    collection: str
    metadata_by_file: Dict[str, Dict[str, str]]

    @property
    def required_metadata_keys(self) -> tuple[str, ...]:
        if self.key == "academic_administration":
            return ("document_type", "academic_year", "topic")

        return ("document_type", "academic_year", "document_year", "topic")


DOMAIN_CONFIGS: Dict[str, DomainConfig] = {
    "academic_administration": DomainConfig(
        key="academic_administration",
        directory="domain1_academic_administration",
        collection="academic_administration",
        metadata_by_file={
            "Kalender-Akademik-2026-2027.pdf": {
                "document_type": "academic_calendar",
                "academic_year": "2026/2027",
                "topic": "academic_calendar",
            },
            "KALENDER-AKADEMIK-UNIVERSITAS-NEGERI-MALANG-TAHUN-AKADEMIK-2024-2025.pdf": {
                "document_type": "academic_calendar",
                "academic_year": "2024/2025",
                "topic": "academic_calendar",
            },
            "Pedoman-Pendidikan-Edisi-2020_Final.pdf": {
                "document_type": "academic_guide",
                "academic_year": "general",
                "topic": "pedoman_pendidikan",
            },
            "PER-NO-12-TAHUN-2018-PEDOMAN-PENDIDIKAN-UNIVERSITAS-NEGERI-MALANG-TAHUN-AKADEMIK-2018-2019.pdf": {
                "document_type": "academic_guide",
                "academic_year": "general",
                "topic": "pedoman_pendidikan",
            },
            "PER-NO-18-TAHUN-2018-PENYELENGGARAAN-PENDIDIKAN-UNIVERSITAS-NEGERI-MALANG.pdf": {
                "document_type": "academic_regulation",
                "academic_year": "general",
                "topic": "general",
            },
            "PER-NO-19-TAHUN-2018-TAHUN-AKADEMIK-KALENDER-AKADEMIK-DAN-SISTEM-ADMINISTRASI-AKADEMIK-UNIVERSITAS-NEGERI-MALANG.pdf": {
                "document_type": "academic_regulation",
                "academic_year": "general",
                "topic": "administrasi_akademik",
            },
            "PER-NO-20-TAHUN-2018-KURIKULUM-UNIVERSITAS-NEGERI-MALANG.pdf": {
                "document_type": "academic_regulation",
                "academic_year": "general",
                "topic": "kurikulum",
            },
            "PER-NO-21-TAHUN-2018-PENILAIAN-DAN-PROSES-HASIL-BELAJAR-MAHASISWA-UNIVERSITAS-NEGERI-MALANG.pdf": {
                "document_type": "academic_regulation",
                "academic_year": "general",
                "topic": "penilaian_hasil_belajar",
            },
            "PER-NO-28-TAHUN-2018-KEBEBASAN-AKADEMIK-KEBEBASAN-MIMBAR-AKADEMIK-DANOTONOMI-KEILMUAN-UNIVERSITAS-NEGERI-MALANG.pdf": {
                "document_type": "academic_regulation",
                "academic_year": "general",
                "topic": "general",
            },
            "Perubahan-Pedoman-Akademik-Edisi-2020-UM-.pdf": {
                "document_type": "academic_regulation",
                "academic_year": "general",
                "topic": "pedoman_pendidikan",
            },
        },
    ),
    "facilities_and_campus_services": DomainConfig(
        key="facilities_and_campus_services",
        directory="domain2_facilities_and_campus_services",
        collection="facilities_and_campus_services",
        metadata_by_file={
            "Sarana dan Prasarana perpustakaan um.pdf": {
                "document_type": "facility_info",
                "academic_year": "general",
                "document_year": "general",
                "topic": "library_facilities",
            },
            "Sarana Umum um.pdf": {
                "document_type": "facility_info",
                "academic_year": "general",
                "document_year": "general",
                "topic": "general_facilities",
            },
            "SOP-GRAFIS-Tri-Wahyuningtyas.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "graphic_studio",
            },
            "SOP-LAB-SOSIO-UM-Deny-Wahyu-Apriadi.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "sociology_laboratory",
            },
            "SOP-LAB-TM-REF-7.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "laboratory",
            },
            "SOP-MEDIA-REKAM-Tri-Wahyuningtyas.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "recording_media",
            },
            "SOP-STUDIO-LUKIS-Tri-Wahyuningtyas.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "painting_studio",
            },
            "SOP-STUDIO-MUSIK-Tri-Wahyuningtyas.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "music_studio",
            },
            "SOP-STUDIO-TARI-Tri-Wahyuningtyas.pdf": {
                "document_type": "facility_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "dance_studio",
            },
            "TARIF-PENGGUNAAN-ALAT-LAB-SOSIO-Deny-Wahyu-Apriadi.pdf": {
                "document_type": "facility_fee_info",
                "academic_year": "general",
                "document_year": "general",
                "topic": "sociology_laboratory_fee",
            },
        },
    ),
    "finance_tuition_and_scholarship": DomainConfig(
        key="finance_tuition_and_scholarship",
        directory="domain3_finance_tuition_and_scholarship",
        collection="finance_tuition_and_scholarship",
        metadata_by_file={
            "11.-Universitas-Negeri-Malang-Rekomendasi-UKT-dan-IPI.pdf": {
                "document_type": "finance_policy",
                "academic_year": "general",
                "document_year": "general",
                "topic": "ukt_and_ipi_recommendation",
            },
            "Pengumuman-Bantuan-UKT-Semester-Gasal-TA-2021-2022.pdf": {
                "document_type": "finance_announcement",
                "academic_year": "2021/2022",
                "document_year": "2021",
                "topic": "ukt_assistance",
            },
            "Pengumuman-Beasiswa-BI-UM-tahun-2024.pdf.pdf": {
                "document_type": "scholarship_announcement",
                "academic_year": "general",
                "document_year": "2024",
                "topic": "bank_indonesia_scholarship",
            },
            "PENGUMUMAN-PERPANJANGAN-REGISTRASI-KIP-K1.pdf": {
                "document_type": "scholarship_announcement",
                "academic_year": "general",
                "document_year": "general",
                "topic": "kip_registration",
            },
            "PENGUMUMAN-REGISTRASI-MABA-JALUR-UTBK-SNBT-2024.pdf": {
                "document_type": "registration_announcement",
                "academic_year": "2024/2025",
                "document_year": "2024",
                "topic": "new_student_registration",
            },
            "PENGUMUMAN-REGISTRASI-MAHASISWA-SEMESTER-GASAL-2024-2025.pdf": {
                "document_type": "registration_announcement",
                "academic_year": "2024/2025",
                "document_year": "2024",
                "topic": "semester_registration",
            },
            "Registrasi-Mahasiswa-Semester-Gasal-Tahun-Akademik-2025-2026.pdf": {
                "document_type": "registration_announcement",
                "academic_year": "2025/2026",
                "document_year": "2025",
                "topic": "semester_registration",
            },
            "Registrasi-Mahasiswa-Semester-Genap-2024-2025.pdf": {
                "document_type": "registration_announcement",
                "academic_year": "2024/2025",
                "document_year": "2024",
                "topic": "semester_registration",
            },
            "s-Panduan-Aplikasi-Pengajuan-UKT-Semester-Gasal-2020-min.pdf": {
                "document_type": "finance_guide",
                "academic_year": "2020/2021",
                "document_year": "2020",
                "topic": "ukt_application_guide",
            },
        },
    ),
    "thesis_final_project_and_graduation": DomainConfig(
        key="thesis_final_project_and_graduation",
        directory="domain4_thesis_final_project_and_graduation",
        collection="thesis_final_project_and_graduation",
        metadata_by_file={
            "KARTU-BIMBINGAN-SKRIPSI.pdf": {
                "document_type": "thesis_form",
                "academic_year": "general",
                "document_year": "general",
                "topic": "thesis_guidance_card",
            },
            "LEMBAR-PERSETUJUAN-TEMA.pdf": {
                "document_type": "thesis_form",
                "academic_year": "general",
                "document_year": "general",
                "topic": "thesis_topic_approval",
            },
            "PEDOMAN-PENULISAN-SKRIPSI-FPSI-2022.pdf": {
                "document_type": "thesis_guide",
                "academic_year": "general",
                "document_year": "2022",
                "topic": "thesis_writing_guideline",
            },
            "PER-NO-22-TAHUN-2018-YUDISIUM-DAN-WISUDA-UNIVERSITAS-NEGERI-MALANG.pdf": {
                "document_type": "graduation_regulation",
                "academic_year": "general",
                "document_year": "2018",
                "topic": "yudisium_and_graduation",
            },
            "PERTOR-NO-44-TAHUN-2022-PERUBAHAN-KEDUA-ATAS-PERATURAN-REKTOR-UNIVERSITAS-NEGERI-MALANG-NOMOR-24-TAHUN-2020-TENTANG-PEDOMAN-PENDIDIKAN-EDISI-2020-1.pdf": {
                "document_type": "academic_guide_revision",
                "academic_year": "general",
                "document_year": "2022",
                "topic": "graduation_requirement",
            },
            "SOP-Pembimbingan-Skripsi-Sah.pdf": {
                "document_type": "thesis_sop",
                "academic_year": "general",
                "document_year": "general",
                "topic": "thesis_supervision",
            },
            "SURAT-EDARAN-WISUDA-2025.pdf": {
                "document_type": "graduation_announcement",
                "academic_year": "general",
                "document_year": "2025",
                "topic": "graduation_ceremony",
            },
            "Surat_Dinas-wisuda-132-Tahun-2025.pdf": {
                "document_type": "graduation_letter",
                "academic_year": "general",
                "document_year": "2025",
                "topic": "graduation_ceremony",
            },
        },
    ),
    "general_profile": DomainConfig(
        key="general_profile",
        directory=".",
        collection="general_profile",
        metadata_by_file={
            "profil_umum_universitasnegerimalang.pdf": {
                "document_type": "institution_profile",
                "academic_year": "general",
                "document_year": "general",
                "topic": "institution_profile",
            },
            "profil_umum_pengembang.pdf": {
                "document_type": "developer_profile",
                "academic_year": "general",
                "document_year": "general",
                "topic": "developer_profile",
            },
        },
    ),
}


def iter_domain_configs(selected_domains: Iterable[str] | None = None) -> Iterable[DomainConfig]:
    if not selected_domains:
        return DOMAIN_CONFIGS.values()

    return [DOMAIN_CONFIGS[domain] for domain in selected_domains]
