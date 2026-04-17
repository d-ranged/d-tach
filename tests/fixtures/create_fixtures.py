"""
Generate binary test fixture files (DOCX and PDF) for manual testing.

Run once from the project root:
    python tests/fixtures/create_fixtures.py

Creates:
    tests/fixtures/sample_with_pii.docx  — DOCX with names, email, phone, student number
    tests/fixtures/sample_with_pii.pdf   — matching PDF
    tests/fixtures/sample_clean.docx     — DOCX with no personal data
    tests/fixtures/sample_clean.pdf      — matching PDF
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

OUTPUT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# DOCX fixtures
# ---------------------------------------------------------------------------

from docx import Document


def create_pii_docx() -> None:
    doc = Document()
    doc.add_heading("Internship Report — Period 2", level=1)

    info = [
        ("Student", "Sarah Mitchell"),
        ("Student Number", "542348"),
        ("Email", "sarah.mitchell@example.com"),
        ("Phone", "+44 7911 123456"),
        ("Supervisor", "Jan van der Berg"),
        ("Supervisor Email", "j.vandenberg@example.nl"),
        ("Location", "Amsterdam, Netherlands"),
        ("Date", "September 2025"),
    ]
    table = doc.add_table(rows=len(info), cols=2)
    for i, (label, value) in enumerate(info):
        table.rows[i].cells[0].text = label
        table.rows[i].cells[1].text = value

    doc.add_paragraph()
    doc.add_heading("Introduction", level=2)
    doc.add_paragraph(
        "This report was prepared by Sarah Mitchell as part of the internship programme. "
        "Student number 542348 is registered at the faculty administration."
    )
    doc.add_paragraph(
        "For questions, contact sarah.mitchell@example.com or call +44 7911 123456. "
        "The supervisor Jan van der Berg can be reached at j.vandenberg@example.nl."
    )
    doc.add_heading("Learning Objectives", level=2)
    doc.add_paragraph(
        "Sarah Mitchell identified the following learning objectives for this period. "
        "Goals were discussed with Jan van der Berg during the intake meeting in Amsterdam."
    )
    doc.add_paragraph(
        "Note: invoices totalling \u20ac12345 were processed and are not personal data. "
        "A currency-prefixed number \u20ac542348 should NOT be flagged by student number detection."
    )

    doc.save(str(OUTPUT_DIR / "sample_with_pii.docx"))
    print("Created sample_with_pii.docx")


def create_clean_docx() -> None:
    doc = Document()
    doc.add_heading("Project Notes", level=1)
    doc.add_heading("Overview", level=2)
    doc.add_paragraph(
        "This document contains general project notes with no personal information. "
        "All references are to roles, not individuals."
    )
    doc.add_heading("Timeline", level=2)
    for item in ["Q1 2025: Initial research phase", "Q2 2025: Development sprint",
                 "Q3 2025: Testing and review", "Q4 2025: Release"]:
        doc.add_paragraph(item, style="List Bullet")
    doc.add_heading("Budget", level=2)
    doc.add_paragraph("Total approved budget: \u20ac45000\nSpent to date: \u20ac12340\nRemaining: \u20ac32660")
    doc.add_heading("Notes", level=2)
    doc.add_paragraph(
        "The methodology follows standard practice. No personal data is processed or stored "
        "in this document. It should be marked as CHECKED when processed by d-tach."
    )
    doc.save(str(OUTPUT_DIR / "sample_clean.docx"))
    print("Created sample_clean.docx")


# ---------------------------------------------------------------------------
# PDF fixtures
# ---------------------------------------------------------------------------

import fitz


def create_pii_pdf() -> None:
    doc = fitz.open()
    page = doc.new_page()

    content = """\
Internship Report — Period 2

Student:          Sarah Mitchell
Student Number:   542348
Email:            sarah.mitchell@example.com
Phone:            +44 7911 123456
Supervisor:       Jan van der Berg  (j.vandenberg@example.nl)
Location:         Amsterdam, Netherlands
Date:             September 2025

Introduction

This report was prepared by Sarah Mitchell as part of the internship
programme. Student number 542348 is registered at the faculty administration.

For questions, contact sarah.mitchell@example.com or call +44 7911 123456.
The supervisor Jan van der Berg can be reached at j.vandenberg@example.nl.

Learning Objectives

Sarah Mitchell identified the following learning objectives for this period.
Goals were discussed with Jan van der Berg during the intake in Amsterdam.

Note: invoices totalling \u20ac12345 are not personal data.
A currency-prefixed number \u20ac542348 should NOT be flagged.
"""
    page.insert_text((72, 72), content, fontsize=11)
    doc.save(str(OUTPUT_DIR / "sample_with_pii.pdf"))
    doc.close()
    print("Created sample_with_pii.pdf")


def create_clean_pdf() -> None:
    doc = fitz.open()
    page = doc.new_page()
    content = """\
Project Notes

Overview

This document contains general project notes with no personal information.
All references are to roles, not individuals.

Timeline

  - Q1 2025: Initial research phase
  - Q2 2025: Development sprint
  - Q3 2025: Testing and review
  - Q4 2025: Release

Budget

  Total approved budget: \u20ac45000
  Spent to date:         \u20ac12340
  Remaining:             \u20ac32660

Notes

The methodology follows standard practice. No personal data is processed
or stored in this document. It should be marked as CHECKED by d-tach.
"""
    page.insert_text((72, 72), content, fontsize=11)
    doc.save(str(OUTPUT_DIR / "sample_clean.pdf"))
    doc.close()
    print("Created sample_clean.pdf")


if __name__ == "__main__":
    create_pii_docx()
    create_clean_docx()
    create_pii_pdf()
    create_clean_pdf()
    print("Done. All fixture files created in tests/fixtures/")