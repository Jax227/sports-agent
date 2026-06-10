from pathlib import Path
import json

PARSED_DIR = Path("data/parsed")
CHUNKS_DIR = Path("data/chunks")
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 1200

def chunk_text(text, chunk_size=CHUNK_SIZE):
    text = text.replace("\x00", " ").strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end
    return chunks

def main():
    txt_files = list(PARSED_DIR.glob("*.txt"))
    if not txt_files:
        print("没有可切片的 txt 文件")
        return

    all_chunks = []

    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "doc_id": txt_file.stem,
                "chunk_id": f"{txt_file.stem}_{i}",
                "text": chunk
            })

    out_path = CHUNKS_DIR / "chunks.json"
    out_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已输出 {len(all_chunks)} 个 chunks 到 {out_path}")

if __name__ == "__main__":
    main()
