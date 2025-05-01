# chatbot.py — with location metadata and answer/evidence matching
import os
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

from memory import global_index, global_chunks, embedded_filenames

# Load API key
with open("config.json", "r") as file:
    print("API key loaded")
    config = json.load(file)
mistralai_api_key = config.get("api-key")
client = mistralai.Mistral(api_key=mistralai_api_key)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
    return text

def extract_text_from_docx(docx_path):
    try:
        doc = docx.Document(docx_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Error processing {docx_path}: {e}")
        return ""

def extract_text_from_csv(csv_path):
    try:
        df = pd.read_csv(csv_path)
        return df.to_csv(index=False)
    except Exception as e:
        print(f"Error processing {csv_path}: {e}")
        return ""

def extract_text_from_txt(txt_path):
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error processing {txt_path}: {e}")
        return ""

def extract_text_from_image(image_path):
    try:
        image = Image.open(image_path)
        return pytesseract.image_to_string(image)
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return ""

def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    elif ext == ".csv":
        return extract_text_from_csv(file_path)
    elif ext == ".txt":
        return extract_text_from_txt(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff"]:
        return extract_text_from_image(file_path)
    else:
        print(f"Unsupported file format: {file_path}")
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
    url = "http://128.226.119.122:8000/v1/embeddings"
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
    import memory
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



async def answer_question(question):
    from memory import global_index, global_chunks
    if not global_index or not global_chunks:
        return None, []
    q_embed = await get_text_embedding_async(question)
    query_vec = np.array([np.array(q_embed, dtype=np.float32)])
    faiss.normalize_L2(query_vec)
    distances, indices = global_index.search(query_vec, k=6)
    evidence = []
    for idx in indices[0]:
        if 0 <= idx < len(global_chunks):
            evidence.append(global_chunks[idx])
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
        for idx, chunk in enumerate(global_chunks):
            if quote in chunk["text"]:
                filtered.append({
                    "text": quote,
                    "filename": chunk["filename"],
                    "chunk_index": chunk["chunk_index"]
                })
                break

    return answer, filtered
