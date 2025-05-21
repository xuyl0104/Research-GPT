import os
import io
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

from app.aws_s3_utils import s3, AWS_S3_BUCKET, upload_pickle_to_s3, download_pickle_from_s3, upload_faiss_to_s3, download_faiss_from_s3, delete_from_s3, s3_key_for

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

@router.get("/test-auth")
def test_auth(current_user: User = Depends(get_current_user)):
    print("✔️ Auth route hit")
    return {"user_name": str(current_user.username)}


@router.post("/embed-files")
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

    faiss_index_key = s3_key_for(user_id, name, "faiss.index")
    chunks_pkl_key = s3_key_for(user_id, name, "chunks.pkl")

    # Load previous chunks/index if appending
    if append:
        try:
            old_chunks = download_pickle_from_s3(chunks_pkl_key)
            old_filenames = {c["filename"] for c in old_chunks}
            index = download_faiss_from_s3(faiss_index_key)
        except:
            old_chunks = []
            old_filenames = set()
            index = None
    else:
        old_chunks = []
        old_filenames = set()
        index = None

    # Read new file contents early to avoid UploadFile closure
    new_files = []
    for file in files:
        if file.filename in old_filenames:
            continue
        contents = await file.read()
        new_files.append((file.filename, contents))

    if not new_files:
        return Response("No new files to embed", media_type="text/plain")

    async def streamer(index, old_chunks):
        all_chunks = []

        # Step 1: Read text and split
        for filename, contents in new_files:
            text = extract_text_from_file(contents, filename)
            if not text:
                continue

            split_chunks = split_text(text, chunk_size=8000)
            for idx, chunk in enumerate(split_chunks):
                all_chunks.append({
                    "text": chunk,
                    "filename": filename,
                    "chunk_index": idx
                })
            yield f"PROGRESS: {len(all_chunks)}/{len(all_chunks)}\n"

        if not all_chunks:
            yield "PROGRESS: 0/0\n"
            yield json.dumps({"status": "error", "message": "No valid files found"})
            return

        # Step 2: Embed
        new_embeddings = []
        for idx, chunk in enumerate(all_chunks):
            emb = await get_text_embedding_async(chunk["text"])
            new_embeddings.append(emb)
            yield f"PROGRESS: {idx + 1}/{len(all_chunks)}\n"

        # embedded files uploaded to S3
        for filename, contents in new_files:
            s3_key = f"{user_id}/{name}/documents/{filename}"
            s3.upload_fileobj(io.BytesIO(contents), AWS_S3_BUCKET, s3_key)

        # Step 3: FAISS
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

        # Step 4: Save to S3
        embedding.faiss_path = faiss_index_key
        embedding.chunks_path = chunks_pkl_key
        db.add(embedding)
        db.commit()

        upload_faiss_to_s3(index, faiss_index_key)
        upload_pickle_to_s3(all_chunks, chunks_pkl_key)

        memory.user_sessions[user_id] = {
            "chunks": all_chunks,
            "index": index
        }

        yield json.dumps({"status": "success", "message": "Embedding complete"})

    return StreamingResponse(streamer(index, old_chunks), media_type="text/plain")




@router.post("/ask")
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
        session = memory.user_sessions.get(current_user.id)
        if not session:
            raise HTTPException(status_code=400, detail="No embedding loaded")

        answer, evidence = await answer_question(question, session["index"], session["chunks"])

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


@router.get("/list-embeddings")
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

@router.get("/load-embedding")
async def load_embedding(
    name: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id
    print(f"🟢 Start loading embedding '{name}' for user {user_id}")

    embedding = db.query(Embedding).filter_by(user_id=user_id, name=name).first()
    if not embedding:
        raise HTTPException(status_code=404, detail="Embedding not found")

    print("🧩 Found embedding in DB:")
    print("  chunks_path:", embedding.chunks_path)
    print("  faiss_path:", embedding.faiss_path)

    if not embedding.chunks_path or not embedding.faiss_path:
        raise HTTPException(status_code=400, detail="Embedding paths missing in DB")

    try:
        print("📥 Downloading chunks from S3...")
        chunks = download_pickle_from_s3(embedding.chunks_path)

        print("📥 Downloading FAISS index from S3...")
        index = download_faiss_from_s3(embedding.faiss_path)

        print("🧠 Type of FAISS index:", type(index))
        if not hasattr(index, "ntotal"):
            raise ValueError("❌ FAISS index object is invalid (not really an index)")

        print("✅ S3 downloads succeeded")
    except Exception as e:
        print(f"❌ S3 download error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load embedding from S3: {e}")

    memory.user_sessions[user_id] = {
        "chunks": chunks,
        "index": index
    }

    file_names = list({chunk["filename"] for chunk in chunks})
    return {"status": "success", "files": file_names}



@router.post("/delete-embedding")
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

    # Remove from memory
    memory.user_sessions.pop(current_user.id, None)

    # Remove from S3
    if embedding.chunks_path:
        delete_from_s3(embedding.chunks_path)
    if embedding.faiss_path:
        delete_from_s3(embedding.faiss_path)

    return {"status": "success", "message": f"Embedding '{name}' deleted"}


@router.get("/load-chat")
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

@router.get("/preview-file")
async def preview_file(filename: str, embeddingName: str, current_user: User = Depends(get_current_user)):
    from app.aws_s3_utils import download_file_bytes_from_s3

    s3_key = f"{current_user.id}/{embeddingName}/documents/{filename}"
    try:
        file_bytes = download_file_bytes_from_s3(s3_key)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

    return Response(file_bytes, media_type="application/octet-stream")


@router.get("/preview-chunks")
async def preview_chunks(filename: str, embeddingName: str, current_user: User = Depends(get_current_user)):
    from app.aws_s3_utils import download_file_bytes_from_s3

    s3_key = f"{current_user.id}/{embeddingName}/documents/{filename}"
    try:
        file_bytes = download_file_bytes_from_s3(s3_key)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

    text = extract_text_from_file(file_bytes, filename)
    chunks = split_text(text, 4096)
    return {"chunks": chunks}

