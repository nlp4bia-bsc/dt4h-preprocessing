"""Convert milestones_data/ .txt files to pdf/xml/docx and write API pointer JSONs."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from docx import Document
from fpdf import FPDF

from encoding import detect_and_read

FORMATS = ["txt", "pdf", "xml", "docx"]

FONT_CANDIDATES = [
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",           # Arch/Fedora
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Ubuntu/Debian
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",                  # Ubuntu/Debian
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",                # Fedora
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise FileNotFoundError(
        "No Unicode TTF font found. Install liberation-fonts or dejavu-fonts, "
        "or pass --font /path/to/font.ttf"
    )


def write_txt(text: str, dest: Path, **_) -> None:
    dest.write_text(text, encoding="utf-8")


def write_pdf(text: str, dest: Path, font: str, **_) -> None:
    pdf = FPDF()
    pdf.add_font("Unicode", fname=font)
    pdf.set_font("Unicode", size=11)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.multi_cell(pdf.epw, 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(dest))


def write_xml(text: str, dest: Path, **_) -> None:
    root = ET.Element("document")
    text_el = ET.SubElement(root, "text")
    text_el.text = text
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(str(dest), encoding="unicode", xml_declaration=True)


def write_docx(text: str, dest: Path, **_) -> None:
    doc = Document()
    for line in text.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    doc.save(str(dest))


def write_pointer(lang: str, stem: str, ext: str, abs_path: Path, ptrs_root: Path) -> None:
    payload = {
        "patient_id": stem,
        "admission_id": f"{lang}_{stem}",
        "text_path": str(abs_path),
    }
    ptr_dir = ptrs_root / lang
    ptr_dir.mkdir(parents=True, exist_ok=True)
    (ptr_dir / f"{stem}_{ext}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def process_file(txt_path: Path, lang: str, records_root: Path, ptrs_root: Path, font: str) -> None:
    stem = txt_path.stem
    text = detect_and_read(txt_path)

    writers = {
        "txt": write_txt,
        "pdf": write_pdf,
        "xml": write_xml,
        "docx": write_docx,
    }

    for ext, writer in writers.items():
        dest_dir = records_root / lang / ext
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{stem}.{ext}"
        writer(text, dest, font=font)
        write_pointer(lang, stem, ext, dest.resolve(), ptrs_root)

    print(f"  {lang}/{stem}: {', '.join(FORMATS)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert milestone .txt records to all formats.")
    parser.add_argument("--source", default="milestones_data", help="Source dir with lang subdirs of .txt files")
    parser.add_argument("--records", default="test_records", help="Output dir for converted files")
    parser.add_argument("--ptrs", default="test_record_ptrs", help="Output dir for pointer JSONs")
    parser.add_argument("--font", default=None, help="Path to Unicode TTF font (auto-detected if omitted)")
    args = parser.parse_args()

    source = Path(args.source)
    records_root = Path(args.records)
    ptrs_root = Path(args.ptrs)

    try:
        font = args.font or find_font()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Font: {font}")

    for lang_dir in sorted(source.iterdir()):
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        txt_files = sorted(lang_dir.glob("*.txt"))
        print(f"[{lang}] {len(txt_files)} files")
        for txt_path in txt_files:
            process_file(txt_path, lang, records_root, ptrs_root, font)

    print("Done.")


if __name__ == "__main__":
    main()
