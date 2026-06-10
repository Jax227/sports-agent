from pathlib import Path
import json
import pickle
from sentence_transformers import SentenceTransformer

CHUNKS_FILE = Path("data/chunks/chunks.json")
DB_DIR = Path("db")
DB_DIR.mkdir(exist_ok=True)

MODEL_NAME = "BAAI/bge-small-zh-v1.5"

def main():
    if not CHUNKS_FILE.exists():
        print("找不到 chunks.json，请先运行 chunk_texts.py")
        return

    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    texts = [item["text"] for item in chunks]

    print("加载 embedding 模型中...")
    model = SentenceTransformer(MODEL_NAME)

    print("生成向量中...")
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    with open(DB_DIR / "chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

    with open(DB_DIR / "embeddings.pkl", "wb") as f:
        pickle.dump(embeddings, f)

    print("索引构建完成")
    print(f"共处理 {len(chunks)} 个文本块")
    print(f"输出文件: {DB_DIR / 'chunks.pkl'}")
    print(f"输出文件: {DB_DIR / 'embeddings.pkl'}")

if __name__ == "__main__":
    main()
