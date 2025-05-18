# chatbot.py — with location metadata and answer/evidence matching
import os
import io
import glob
import json
import asyncio
import numpy as np
import faiss
import PyPDF2
import docx
import pandas as pd
from PIL import Image
import pytesseract
import mistralai
import re
import pickle
import aiohttp

from dotenv import load_dotenv

load_dotenv()
mistralai_api_key = os.getenv("MISTRAL_KEY")
EMBED_SERVER_URL = os.getenv("EMBED_SERVER_URL")
EMBED_SERVER_PORT = os.getenv("EMBED_SERVER_PORT")

client = mistralai.Mistral(api_key=mistralai_api_key)

def extract_text_from_pdf_bytes(file_bytes):
    from PyPDF2 import PdfReader
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
    except Exception as e:
        print("PDF read error:", e)
        return ""

def extract_text_from_docx_bytes(file_bytes):
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print("DOCX read error:", e)
        return ""

def extract_text_from_csv_bytes(file_bytes):
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
        return df.to_csv(index=False)
    except Exception as e:
        print("CSV read error:", e)
        return ""

def extract_text_from_image_bytes(file_bytes):
    try:
        image = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(image)
    except Exception as e:
        print("Image OCR error:", e)
        return ""


def extract_text_from_file(file_bytes: bytes, filename: str):
    ext = os.path.splitext(filename)[-1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf_bytes(file_bytes)
    elif ext == ".docx":
        return extract_text_from_docx_bytes(file_bytes)
    elif ext == ".csv":
        return extract_text_from_csv_bytes(file_bytes)
    elif ext == ".txt":
        return file_bytes.decode("utf-8", errors="ignore")
    elif ext in [".png", ".jpg", ".jpeg", ".tiff"]:
        return extract_text_from_image_bytes(file_bytes)
    else:
        print(f"Unsupported file format: {filename}")
        return ""


def split_text(text, chunk_size=10240):
    if chunk_size <= 0:
        chunk_size = 500  # fallback chunk size
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

async def load_document_chunks(directory, chunk_size=10240):
    chunks = []
    patterns = ["*.pdf", "*.docx", "*.csv", "*.txt", "*.png", "*.jpg", "*.jpeg", "*.tiff"]
    for pattern in patterns:
        for file_path in glob.glob(os.path.join(directory, pattern)):
            print(f"Processing: {file_path}")
            text = extract_text_from_file(file_path)
            if text:
                split_chunks = split_text(text, chunk_size)
                for idx, chunk in enumerate(split_chunks):
                    chunks.append({
                        "text": chunk,
                        "filename": os.path.basename(file_path),
                        "chunk_index": idx
                    })
    return chunks


def load_chunks_from_file(file_path, chunk_size=10240):
    chunks = []
    text = extract_text_from_file(file_path)
    if text:
        split_chunks = split_text(text, chunk_size)
        for idx, chunk in enumerate(split_chunks):
            chunks.append({
                "text": chunk,
                "filename": os.path.basename(file_path),
                "chunk_index": idx
            })
    return chunks


async def get_text_embedding_async(input_text):
    # url = "http://host.docker.internal:8000/v1/embeddings"
    url = f"http://{EMBED_SERVER_URL}:{EMBED_SERVER_PORT}/v1/embeddings"
    headers = {"Content-Type": "application/json"}
    payload = {"input": input_text}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
            data = await response.json()
            embedding = data["data"][0]["embedding"]
            return embedding

# TODO: embedding using mistral, may need to delete
async def get_text_embedding_async_bk(input_text):
    await asyncio.sleep(2)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: client.embeddings.create(
            model="mistral-embed",
            inputs=input_text
        )
    )
    return result.data[0].embedding

async def run_mistral_async(user_message, model="mistral-large-latest"):
    await asyncio.sleep(1)
    loop = asyncio.get_running_loop()
    chat_response = await loop.run_in_executor(
        None,
        lambda: client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": user_message}]
        )
    )
    return chat_response.choices[0].message.content


async def update_index(documents_dir, chunk_size, save_dir, append=False):
    import app.memory as memory
    print("Updating index from:", documents_dir)

    # Load existing if appending
    faiss_path = os.path.join(save_dir, "faiss.index")
    chunks_path = os.path.join(save_dir, "chunks.pkl")

    if append and os.path.exists(faiss_path) and os.path.exists(chunks_path):
        index = faiss.read_index(faiss_path)
        with open(chunks_path, "rb") as f:
            old_chunks = pickle.load(f)
    else:
        index = None
        old_chunks = []

    # Load and filter new files
    all_chunks = await load_document_chunks(documents_dir, chunk_size)
    old_filenames = {c["filename"] for c in old_chunks}
    new_chunks = [c for c in all_chunks if c["filename"] not in old_filenames]

    if not new_chunks:
        print("No new chunks to embed.")
        memory.global_index = index
        memory.global_chunks = old_chunks
        return

    # Embed new chunks
    emb_list = [await get_text_embedding_async(chunk["text"]) for chunk in new_chunks]
    emb_array = np.stack(emb_list).astype(np.float32)
    faiss.normalize_L2(emb_array)

    if index:
        print("Appending to index...")
        start_id = len(old_chunks)
        ids = np.arange(start_id, start_id + len(new_chunks)).astype(np.int64)
        index.add_with_ids(emb_array, ids)
        all_chunks = old_chunks + new_chunks
    else:
        print("Creating new index...")
        dim = emb_array.shape[1]
        index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))
        ids = np.arange(len(new_chunks)).astype(np.int64)
        index.add_with_ids(emb_array, ids)
        all_chunks = new_chunks

    memory.global_index = index
    memory.global_chunks = all_chunks

    # Save to disk
    faiss.write_index(index, faiss_path)
    with open(chunks_path, "wb") as f:
        pickle.dump(all_chunks, f)



async def answer_question(question, index, chunks):
    if not index or not chunks:
        print("No index loaded.")
        return None, []

    q_embed = await get_text_embedding_async(question)
    query_vec = np.array([np.array(q_embed, dtype=np.float32)])
    faiss.normalize_L2(query_vec)
    distances, indices = index.search(query_vec, k=6)
    evidence = []
    for idx in indices[0]:
        if 0 <= idx < len(chunks):
            evidence.append(chunks[idx])
    prompt = f"""
Below are excerpts extracted from original documents:
---------------------
{chr(10).join([e['text'] for e in evidence])}
---------------------
Based solely on the above content, answer the following question.
After your answer, include an \"Evidence\" section in which you quote the exact excerpts you used.
If the relevant evidence is not available, state so.
Query: {question}
Answer:
"""
    answer = await run_mistral_async(prompt)

    # Extract quoted evidence for matching
    quoted = re.findall(r'\"(.+?)\"', answer, re.DOTALL)
    quoted = [q.strip() for q in quoted if len(q.strip()) > 20]
    filtered = []
    for quote in quoted:
        for idx, chunk in enumerate(chunks):
            if quote in chunk["text"]:
                filtered.append({
                    "text": quote,
                    "filename": chunk["filename"],
                    "chunk_index": chunk["chunk_index"]
                })
                break

    return answer, filtered
