#!/usr/bin/env python3
"""Generate LBRO_Interview_Architecture_Master_Booklet.pdf from Markdown source."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "LBRO_Interview_Architecture_Master_Booklet.md"
PDF_PATH = ROOT / "LBRO_Interview_Architecture_Master_Booklet.pdf"

UNICODE_REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2192": "->",
    "\u2190": "<-",
    "\u2514": "+",
    "\u251c": "+",
    "\u2502": "|",
    "\u2500": "-",
    "\u250c": "+",
    "\u2510": "+",
    "\u2518": "+",
    "\u2713": "[x]",
    "\u2705": "[OK]",
    "\u274c": "[X]",
    "\u2022": "-",
    "\u2193": "v",
    "\u2191": "^",
    "\u25ba": ">",
}


def sanitize(text: str) -> str:
    if not text:
        return ""
    for src, dst in UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    # Break long unbreakable tokens for PDF wrapping
    text = re.sub(r"(\S{80,})", lambda m: " ".join(m.group(1)[i : i + 40] for i in range(0, len(m.group(1)), 40)), text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class BookletPDF(FPDF):
    MARGIN = 15

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        self.set_auto_page_break(auto=True, margin=20)
        self._section_title = ""
        self._skip_header_footer = False

    @property
    def content_width(self) -> float:
        return self.w - 2 * self.MARGIN

    def header(self) -> None:
        if self._skip_header_footer or self.page_no() <= 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        title = sanitize(self._section_title)[:70]
        self.cell(self.content_width / 2, 5, "LBRO Interview & Architecture Master Booklet")
        self.cell(self.content_width / 2, 5, title, align="R", new_x="LMARGIN", new_y="NEXT")

    def footer(self) -> None:
        if self._skip_header_footer or self.page_no() <= 1:
            return
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def add_title_page(self) -> None:
        self.add_page()
        self._skip_header_footer = True
        self.ln(45)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(20, 40, 80)
        self.cell(0, 12, "LBRO", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 15)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 9, sanitize("Interview & Architecture\nMaster Booklet"), align="C")
        self.ln(18)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, sanitize("Engineering / Interview Preparation Document\nRepository-First Analysis"), align="C")
        self.ln(24)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 5, sanitize("Source: Actual LBRO codebase implementation\nNot a marketing document"), align="C")
        self._skip_header_footer = False

    def add_toc(self, entries: list[tuple[str, int]]) -> None:
        self.add_page()
        self._section_title = "Table of Contents"
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 40, 80)
        self.cell(0, 10, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        for title, page in entries:
            t = sanitize(title)
            self.cell(0, 5, f"{t} .............. {page}", new_x="LMARGIN", new_y="NEXT")

    def write_heading(self, level: int, text: str) -> None:
        text = sanitize(text)
        if level == 1:
            self.ln(3)
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(20, 40, 80)
            self._section_title = text
        elif level == 2:
            self.ln(2)
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(30, 60, 100)
        elif level == 3:
            self.ln(1)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(40, 40, 40)
        else:
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(50, 50, 50)
        self.multi_cell(self.content_width, 6, text)
        self.ln(1)

    def write_body(self, text: str) -> None:
        text = sanitize(text.strip())
        if not text:
            return
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.content_width, 4.5, text)
        self.ln(1)

    def write_bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.content_width, 4.5, sanitize("- " + text))

    def write_code(self, text: str) -> None:
        self.set_fill_color(245, 245, 245)
        self.set_font("Courier", "", 7)
        self.set_text_color(20, 20, 20)
        for line in text.split("\n"):
            line = sanitize(line)
            if len(line) > 110:
                while line:
                    chunk, line = line[:110], line[110:]
                    self.multi_cell(self.content_width, 3.8, "  " + chunk, fill=True)
            else:
                self.multi_cell(self.content_width, 3.8, "  " + line, fill=True)
        self.ln(2)

    def write_callout(self, label: str, text: str) -> None:
        self.set_fill_color(255, 248, 220)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 80, 0)
        self.multi_cell(self.content_width, 5, sanitize(label + ": " + text), fill=True)
        self.ln(2)

    def write_table(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        ncols = len(rows[0])
        width = self.content_width / ncols
        for ri, row in enumerate(rows):
            self.set_font("Helvetica", "B" if ri == 0 else "", 7)
            self.set_fill_color(230, 235, 245 if ri == 0 else 255)
            for cell in row:
                txt = sanitize(cell)[: int(width / 1.8)]
                self.cell(width, 5, txt, border=1, fill=(ri == 0))
            self.ln()


def parse_markdown(md: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(("code", "\n".join(code_lines)))
            i += 1
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            blocks.append((f"h{min(level, 4)}", line.lstrip("#").strip()))
        elif line.startswith("> **"):
            m = re.match(r">\s*\*\*(.+?)\*\*:\s*(.*)", line)
            if m:
                blocks.append(("callout", f"{m.group(1)}|{m.group(2)}"))
        elif line.startswith("|") and "|" in line[1:]:
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[-:\s|]+\|$", lines[i]):
                    cells = [c.strip() for c in lines[i].strip("|").split("|")]
                    rows.append(cells)
                i += 1
            blocks.append(("table", repr(rows)))
            continue
        elif line.startswith("- "):
            blocks.append(("bullet", line[2:].strip()))
        elif line.strip() == "---":
            blocks.append(("hr", ""))
        elif line.strip():
            para = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "-", "|", ">", "```", "---")):
                para.append(lines[i].strip())
                i += 1
            blocks.append(("text", " ".join(para)))
            continue
        i += 1
    return blocks


def render_blocks(pdf: BookletPDF, blocks: list[tuple[str, str]], h1_pages: list[tuple[str, int]] | None = None) -> None:
    for btype, content in blocks:
        if btype == "h1":
            if h1_pages is not None:
                h1_pages.append((content, pdf.page_no()))
            pdf.write_heading(1, content)
        elif btype == "h2":
            pdf.write_heading(2, content)
        elif btype == "h3":
            pdf.write_heading(3, content)
        elif btype == "h4":
            pdf.write_heading(4, content)
        elif btype == "text":
            pdf.write_body(content)
        elif btype == "bullet":
            pdf.write_bullet(content)
        elif btype == "code":
            pdf.write_code(content)
        elif btype == "callout":
            label, text = content.split("|", 1)
            pdf.write_callout(label, text)
        elif btype == "table":
            pdf.write_table(ast.literal_eval(content))
        elif btype == "hr":
            pdf.ln(2)


def build_pdf(blocks: list[tuple[str, str]]) -> BookletPDF:
    # Pass 1: collect h1 page numbers
    tmp = BookletPDF()
    tmp.add_page()
    h1_pages: list[tuple[str, int]] = []
    render_blocks(tmp, blocks, h1_pages)

    # Pass 2: title + TOC + content
    pdf = BookletPDF()
    pdf.add_title_page()
    toc = [(t, p + 1) for t, p in h1_pages]  # offset for TOC page
    pdf.add_toc(toc)
    render_blocks(pdf, blocks)
    return pdf


def main() -> int:
    if not MD_PATH.exists():
        print(f"Missing markdown: {MD_PATH}", file=sys.stderr)
        return 1
    md = MD_PATH.read_text(encoding="utf-8")
    blocks = parse_markdown(md)
    pdf = build_pdf(blocks)
    pdf.output(str(PDF_PATH))
    pages = pdf.page_no()
    print(f"Generated: {PDF_PATH}")
    print(f"Pages: {pages}")
    if pages < 20:
        print(f"WARNING: Page count {pages} is below 20-page target", file=sys.stderr)
    elif pages > 35:
        print(f"NOTE: Page count {pages} exceeds 30-page target slightly", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
