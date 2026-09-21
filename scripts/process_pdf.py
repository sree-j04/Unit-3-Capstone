import os
import time
import json
import sqlite3
import boto3
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader, PdfWriter
import io

load_dotenv()

REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET = os.environ["S3_BUCKET_NAME"]

s3 = boto3.client("s3", region_name=REGION)
textract = boto3.client("textract", region_name=REGION)

DB_PATH = "capstone.db"
VECTOR_STORE_PATH = "vector_store.json"

model = SentenceTransformer("all-MiniLM-L6-v2")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            chunk_index INTEGER,
            text TEXT
        )
    """)
    conn.commit()
    return conn


def extract_text_from_pdf(local_path: str) -> str:
    reader = PdfReader(local_path)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    first_page_bytes = buf.getvalue()

    response = textract.detect_document_text(Document={"Bytes": first_page_bytes})

    lines = [block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"]
    return "\n".join(lines)


def chunk_text(text: str, words_per_chunk: int = 700) -> list:
    words = text.split()
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunk = " ".join(words[i:i + words_per_chunk])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def process_pdf(filename: str):
    print(f"Extracting text from {filename} via Textract...")
    full_text = extract_text_from_pdf(filename)
    print(f"Extracted {len(full_text)} characters")

    chunks = chunk_text(full_text)
    print(f"Split into {len(chunks)} chunk(s)")

    conn = init_db()
    vector_store = []
    if os.path.exists(VECTOR_STORE_PATH):
        with open(VECTOR_STORE_PATH, "r") as f:
            vector_store = json.load(f)

    for i, chunk in enumerate(chunks):
        conn.execute(
            "INSERT INTO raw_documents (filename, chunk_index, text) VALUES (?, ?, ?)",
            (filename, i, chunk),
        )
        embedding = model.encode(chunk).tolist()
        vector_store.append({
            "filename": filename,
            "chunk_index": i,
            "text": chunk,
            "embedding": embedding,
        })

    conn.commit()
    conn.close()

    with open(VECTOR_STORE_PATH, "w") as f:
        json.dump(vector_store, f)

    print(f"Stored {len(chunks)} chunk(s) in SQLite and vector_store.json")


if __name__ == "__main__":
    process_pdf("C:/Users/jyoth/Desktop/Deloitte/Sree Jessu Resume.pdf")