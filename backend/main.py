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
from embedding import router as embedding_router

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

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
EMBEDDING_DIR = os.getenv("EMBEDDING_DIR")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3334",              # Local development
        "http://137.220.61.33:3334",          # Vultr
        # "http://128.226.119.122:3334",        # Server IP
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(embedding_router, prefix="/api")
