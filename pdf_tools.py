import argparse
import sys
from pathlib import Path

import fitz


def open_pdf(path: str) -> fitz.Document:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return fitz.open(pdf_path)


def page_text(pdf: fitz.Document, page_number: int) -> str:
    if page_number < 1 or page_number > len(pdf):
        raise ValueError(f"Page must be between 1 and {len(pdf)}")
    return pdf[page_number - 1].get_text()


def search_text(pdf: fitz.Document, needle: str) -> list[int]:
    matches = []
    for i, page in enumerate(pdf, start=1):
        if needle in page.get_text():
            matches.append(i)
    return matches


def render_page(pdf: fitz.Document, page_number: int, output: str, zoom: float) -> None:
    if page_number < 1 or page_number > len(pdf):
        raise ValueError(f"Page must be between 1 and {len(pdf)}")
    pix = pdf[page_number - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(output)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Simple PDF reading helper.")
    parser.add_argument("pdf", help="Path to the PDF file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search for text in the PDF")
    search_parser.add_argument("needle", help="Exact text to search for")

    text_parser = subparsers.add_parser("page-text", help="Extract text from a page")
    text_parser.add_argument("page", type=int, help="1-based PDF page number")

    render_parser = subparsers.add_parser("render", help="Render a page to an image")
    render_parser.add_argument("page", type=int, help="1-based PDF page number")
    render_parser.add_argument("output", help="Output image path")
    render_parser.add_argument("--zoom", type=float, default=2.0, help="Render zoom factor")

    args = parser.parse_args()
    pdf = open_pdf(args.pdf)

    if args.command == "search":
        matches = search_text(pdf, args.needle)
        if not matches:
            print("No matches found.")
            return 1
        print("Matches on pages:", ", ".join(str(page) for page in matches))
        return 0

    if args.command == "page-text":
        print(page_text(pdf, args.page))
        return 0

    if args.command == "render":
        render_page(pdf, args.page, args.output, args.zoom)
        print(Path(args.output).resolve())
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
