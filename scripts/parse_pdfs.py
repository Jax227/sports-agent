from pathlib import Path
import fitz

RAW_DIR = Path("data/raw")
PARSED_DIR = Path("data/parsed")
PARSED_DIR.mkdir(parents=True, exist_ok=True)

def extract_text_from_pdf(pdf_path: Path) -> str:
    text_parts = []
    doc = fitz.open(pdf_path)
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)

def main():
    pdf_files = list(RAW_DIR.glob("*.pdf"))
    if not pdf_files:
        print("data/raw/ 里没有 PDF 文件")
        return

    for pdf_file in pdf_files:
        print(f"正在解析: {pdf_file.name}")
        text = extract_text_from_pdf(pdf_file)
        out_file = PARSED_DIR / f"{pdf_file.stem}.txt"
        out_file.write_text(text, encoding="utf-8")
        print(f"已保存: {out_file}")

if __name__ == "__main__":
    main()
