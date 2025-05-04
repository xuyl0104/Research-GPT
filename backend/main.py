import os
import shutil
import json
import pickle
import numpy as np
import faiss
from datetime import datetime, timezone
from fastapi import FastAPI, Request, UploadFile, File, Form, Response, HTTPException, Depends, APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from typing import List

from app.auth import router as auth_router

import uuid
from sqlalchemy.orm import Session
from app.pgsql.database import get_db
from app.auth_utils import get_current_user
from app.pgsql.models import Base, User, Embedding, Message
from app.pgsql.models import User

from app.chatbot import extract_text_from_file, split_text, load_document_chunks, load_chunks_from_file, get_text_embedding_async, answer_question, run_mistral_async
import app.memory as memory

from app.aws_s3_utils import upload_pickle_to_s3, download_pickle_from_s3, upload_faiss_to_s3, download_faiss_from_s3, delete_from_s3, s3_key_for

from dotenv import load_dotenv

load_dotenv()

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
EMBEDDING_DIR = os.getenv("EMBEDDING_DIR")

app = FastAPI()
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/test-auth")
def test_auth(current_user: User = Depends(get_current_user)):
    print("✔️ Auth route hit")
    return {"user_name": str(current_user.username)}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()
@router.post("/register")
def register_user(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed = pwd_context.hash(password)
    user = User(id=uuid.uuid4(), username=username, password_hash=hashed)
    db.add(user)
    db.commit()
    return {"status": "success", "message": "User registered"}


@app.post("/embed-files")
async def embed_files(
    name: str = Form(...),
    append: bool = Form(True),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id

    # Get or create embedding entry in the DB
    embedding = db.query(Embedding).filter_by(user_id=user_id, name=name).first()
    if not embedding:
        embedding = Embedding(id=uuid.uuid4(), user_id=user_id, name=name)
        db.add(embedding)
        db.commit()
        db.refresh(embedding)

    emb_dir = os.path.join(EMBEDDING_DIR, str(user_id), name)
    docs_dir = os.path.join(emb_dir, "documents")
    os.makedirs(docs_dir, exist_ok=True)

    existing_files = set()
    if append and os.path.exists(docs_dir):
        existing_files = set(os.listdir(docs_dir))

    new_files = []
    for file in files:
        if append and file.filename in existing_files:
            continue
        save_path = os.path.join(docs_dir, file.filename)
        with open(save_path, "wb") as f:
            f.write(await file.read())
        new_files.append(save_path)

    if not new_files:
        return Response("No new files to embed", media_type="text/plain")

    async def streamer():
        all_chunks = []
        for path in new_files:
            chunks = extract_text_from_file(path)
            split_chunks = split_text(chunks, chunk_size=8000)
            for idx, chunk in enumerate(split_chunks):
                all_chunks.append({
                    "text": chunk,
                    "filename": os.path.basename(path),
                    "chunk_index": idx
                })
            yield f"PROGRESS: {len(all_chunks)}/{len(all_chunks)}\n"

        if not all_chunks:
            yield "PROGRESS: 0/0\n"
            yield json.dumps({"status": "error", "message": "No valid files found"})
            return
        
        faiss_index_key = s3_key_for(user_id, name, "faiss.index")
        chunks_pkl_key = s3_key_for(user_id, name, "chunks.pkl")

        faiss_path = os.path.join(emb_dir, "faiss.index")
        chunks_path = os.path.join(emb_dir, "chunks.pkl")

        if append and os.path.exists(faiss_path) and os.path.exists(chunks_path):
            index = faiss.read_index(faiss_path)
            with open(chunks_path, "rb") as f:
                old_chunks = pickle.load(f)
        else:
            index = None
            old_chunks = []

        new_embeddings = []
        for idx, chunk in enumerate(all_chunks):
            emb = await get_text_embedding_async(chunk["text"])
            new_embeddings.append(emb)
            yield f"PROGRESS: {idx + 1}/{len(all_chunks)}\n"

        emb_array = np.array(new_embeddings, dtype=np.float32)
        faiss.normalize_L2(emb_array)

        if index:
            start_id = len(old_chunks)
            ids = np.arange(start_id, start_id + len(all_chunks)).astype(np.int64)
            index.add_with_ids(emb_array, ids)
            all_chunks = old_chunks + all_chunks
        else:
            dim = emb_array.shape[1]
            index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))
            ids = np.arange(len(all_chunks)).astype(np.int64)
            index.add_with_ids(emb_array, ids)

        faiss.write_index(index, faiss_path)
        with open(chunks_path, "wb") as f:
            pickle.dump(all_chunks, f)

        # Persist embedding file paths
        # Persist S3 keys to DB
        embedding.faiss_path = faiss_index_key  # (S3 key in db)
        embedding.chunks_path = chunks_pkl_key  # (S3 key in db)

        db.add(embedding)
        db.commit()

        # Upload to S3
        upload_faiss_to_s3(index, faiss_index_key)
        upload_pickle_to_s3(all_chunks, chunks_pkl_key)

        memory.global_index = index
        memory.global_chunks = all_chunks

        yield json.dumps({"status": "success", "message": "Embedding complete"})

    return StreamingResponse(streamer(), media_type="text/plain")


@app.post("/ask")
async def ask_question(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    body = await request.json()
    question = body.get("question")
    embedding_name = body.get("embedding")
    open_mode = body.get("open_mode", False)
    if not question or not embedding_name:
        raise HTTPException(status_code=400, detail="Missing question or embedding name")

    # Get embedding session
    embedding = db.query(Embedding).filter_by(user_id=current_user.id, name=embedding_name).first()
    if not embedding:
        raise HTTPException(status_code=404, detail="Embedding not found")

    # Save user's question
    user_msg = Message(
        id=uuid.uuid4(),
        user_id=current_user.id,
        embedding_id=embedding.id,
        role="user",
        content=question,
        created_at=datetime.now(timezone.utc)
    )
    db.add(user_msg)
    db.commit()

        # Generate response based on mode
    if open_mode:
        prompt = f"Answer the following question as best you can using your general knowledge:\n\n{question}\n\nAnswer:"
        answer = await run_mistral_async(prompt)
        evidence = []
    else:
        answer, evidence = await answer_question(question)

    if not answer:
        return JSONResponse({"error": "No answer generated"}, status_code=400)

    bot_msg = Message(
        id=uuid.uuid4(),
        user_id=current_user.id,
        embedding_id=embedding.id,
        role="bot",
        content=answer,
        evidence=evidence,
        created_at=datetime.now(timezone.utc)
    )
    db.add(bot_msg)
    db.commit()

    return {
        "answer": answer,
        "evidence": evidence
    }


@app.get("/list-embeddings")
async def list_embeddings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    embeddings = (
        db.query(Embedding)
        .filter_by(user_id=current_user.id)
        .order_by(Embedding.created_at.desc())
        .all()
    )
    return {"embeddings": [e.name for e in embeddings]}

@app.get("/load-embedding")
async def load_embedding(
    name: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    embedding = db.query(Embedding).filter_by(user_id=current_user.id, name=name).first()
    if not embedding:
        raise HTTPException(status_code=404, detail="Embedding not found")

    local_dir = os.path.join(EMBEDDING_DIR, str(current_user.id), name)
    chunks_path = os.path.join(local_dir, "chunks.pkl")
    index_path = os.path.join(local_dir, "faiss.index")

    # Prefer local load, fallback to S3
    if os.path.exists(chunks_path) and os.path.exists(index_path):
        with open(chunks_path, "rb") as f:
            chunks = pickle.load(f)
        index = faiss.read_index(index_path)
    else:
        chunks = download_pickle_from_s3(embedding.chunks_path)
        index = download_faiss_from_s3(embedding.faiss_path)
        os.makedirs(local_dir, exist_ok=True)
        with open(chunks_path, "wb") as f:
            pickle.dump(chunks, f)
        faiss.write_index(index, index_path)

    memory.global_chunks = chunks
    memory.global_index = index

    file_names = list({chunk["filename"] for chunk in chunks})
    return {"status": "success", "files": file_names}


@app.post("/delete-embedding")
async def delete_embedding(
    name: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    embedding = db.query(Embedding).filter_by(user_id=current_user.id, name=name).first()
    if not embedding:
        raise HTTPException(status_code=404, detail="Embedding not found")

    # Remove from database (cascade deletes messages)
    db.delete(embedding)
    db.commit()

    # Remove local embedding folder
    emb_dir = os.path.join(EMBEDDING_DIR, str(current_user.id), name)
    if os.path.exists(emb_dir):
        shutil.rmtree(emb_dir)

    # Remove from S3
    if embedding.chunks_path:
        delete_from_s3(embedding.chunks_path)
    if embedding.faiss_path:
        delete_from_s3(embedding.faiss_path)

    return {"status": "success", "message": f"Embedding '{name}' deleted"}


@app.get("/load-chat")
async def load_chat(
    name: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    embedding = db.query(Embedding).filter_by(user_id=current_user.id, name=name).first()
    if not embedding:
        raise HTTPException(status_code=404, detail="Embedding not found")

    messages = (
        db.query(Message)
        .filter_by(embedding_id=embedding.id)
        .order_by(Message.created_at)
        .all()
    )

    return {
        "messages": [
            {
                "from": m.role,
                "content": m.content,
                "evidence": m.evidence
            }
            for m in messages
        ]
    }

@app.get("/preview-file")
async def preview_file(filename: str, embeddingName: str, current_user: User = Depends(get_current_user)):
    file_dir = os.path.join(EMBEDDING_DIR, str(current_user.id), embeddingName, "documents")
    if not os.path.exists(os.path.join(file_dir, filename)):
        raise HTTPException(status_code=404, detail="File not found")
    return Response(open(os.path.join(file_dir, filename), "rb").read(), media_type="application/octet-stream")

@app.get("/preview-chunks")
async def preview_chunks(filename: str):
    filepath = os.path.join(UPLOAD_DIR, filename)
    text = extract_text_from_file(filepath)
    chunks = split_text(text, 4096)
    return {"chunks": chunks}
