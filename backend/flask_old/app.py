from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import faiss
import os
import json
import numpy as np
import pickle
import asyncio
from chatbot import extract_text_from_file, split_text, load_document_chunks, get_text_embedding_async, answer_question
import backend.app.memory as memory

UPLOAD_DIR = "documents"
EMBEDDING_DIR = "embeddings"

app = Flask(__name__)
CORS(app)

@app.route("/embed-files", methods=["POST"])
def embed_files():
    name = request.args.get("name")
    append = request.args.get("append", "false").lower() == "true"
    if not name:
        return jsonify({"error": "Missing embedding name"}), 400

    emb_dir = os.path.join(EMBEDDING_DIR, name)
    docs_dir = os.path.join(emb_dir, "documents")
    os.makedirs(docs_dir, exist_ok=True)

    uploaded_files = request.files.getlist("files")
    for file in uploaded_files:
        save_path = os.path.join(docs_dir, file.filename)
        file.save(save_path)

    def stream_embedding():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Step 1: Load all chunks from uploaded documents
        all_chunks = loop.run_until_complete(load_document_chunks(docs_dir, chunk_size=8000))

        if not all_chunks:
            yield "PROGRESS: 0/0\n"
            yield '{"status": "error", "message": "No valid files found"}'
            return

        # Step 2: If appending, load existing index/chunks
        faiss_path = os.path.join(emb_dir, "faiss.index")
        chunks_path = os.path.join(emb_dir, "chunks.pkl")

        if append and os.path.exists(faiss_path) and os.path.exists(chunks_path):
            index = faiss.read_index(faiss_path)
            with open(chunks_path, "rb") as f:
                old_chunks = pickle.load(f)
        else:
            index = None
            old_chunks = []

        # Step 3: Embed each chunk and stream progress
        new_embeddings = []
        for idx, chunk in enumerate(all_chunks):
            emb = loop.run_until_complete(get_text_embedding_async(chunk["text"]))
            new_embeddings.append(emb)

            yield f"PROGRESS: {idx + 1}/{len(all_chunks)}\n"

        # Step 4: Build or update FAISS index
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

        # Step 5: Save index and chunks
        faiss.write_index(index, faiss_path)
        with open(chunks_path, "wb") as f:
            pickle.dump(all_chunks, f)

        memory.global_index = index
        memory.global_chunks = all_chunks

        yield '{"status": "success", "message": "Embedding complete"}'

    return Response(stream_embedding(), mimetype="text/plain")


@app.route("/list-embeddings")
def list_embeddings():
    emb_root = "embeddings"
    if not os.path.exists(emb_root):
        return jsonify({"embeddings": []})
    names = sorted([d for d in os.listdir(emb_root) if os.path.isdir(os.path.join(emb_root, d))])
    return jsonify({"embeddings": names})


@app.route("/load-embedding")
def load_embedding():
    import backend.app.memory as memory
    import faiss
    import pickle

    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Missing embedding name"}), 400

    emb_dir = os.path.join("embeddings", name)
    index_path = os.path.join(emb_dir, "faiss.index")
    chunks_path = os.path.join(emb_dir, "chunks.pkl")

    if not os.path.exists(index_path) or not os.path.exists(chunks_path):
        return jsonify({"error": "Embedding not found"}), 404

    try:
        memory.global_index = faiss.read_index(index_path)
        with open(chunks_path, "rb") as f:
            memory.global_chunks = pickle.load(f)
        filenames = sorted(list(set(chunk["filename"] for chunk in memory.global_chunks)))
        return jsonify({"status": "loaded", "files": filenames})
    except Exception as e:
        return jsonify({"error": f"Failed to load embedding: {str(e)}"}), 500


@app.route("/delete-embedding", methods=["POST"])
def delete_embedding():
    import shutil
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Missing embedding name"}), 400

    emb_dir = os.path.join("embeddings", name)
    if os.path.exists(emb_dir):
        shutil.rmtree(emb_dir)
        return jsonify({"status": "deleted", "message": f"Embedding '{name}' deleted"})
    else:
        return jsonify({"error": "Embedding not found"}), 404

@app.route("/ask", methods=["POST"])
def ask_question():
    user_question = request.json.get("question", "")
    if not user_question:
        return jsonify({"error": "No question provided."}), 400
    if memory.global_index is None:
        return jsonify({"error": "No documents embedded. Please upload and embed files first."}), 400

    # Call async function properly
    result = asyncio.run(answer_question(user_question))
    return jsonify({"answer": result[0], "evidence": result[1]})


@app.route("/save-chat", methods=["POST"])
def save_chat():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Missing embedding name"}), 400
    messages = request.json.get("messages", [])
    emb_dir = os.path.join("embeddings", name)
    os.makedirs(emb_dir, exist_ok=True)
    try:
        with open(os.path.join(emb_dir, "chat.json"), "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/load-chat")
def load_chat():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Missing embedding name"}), 400
    emb_dir = os.path.join("embeddings", name)
    chat_path = os.path.join(emb_dir, "chat.json")
    if not os.path.exists(chat_path):
        return jsonify({"messages": []})
    try:
        with open(chat_path, "r", encoding="utf-8") as f:
            messages = json.load(f)
        return jsonify({"messages": messages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/preview-file")
def preview_file():
    filename = request.args.get("filename")
    embedding_name = request.args.get("embeddingName")

    if not filename or not embedding_name:
        return jsonify({"error": "Missing filename or embeddingName"}), 400

    file_dir = os.path.join("embeddings", embedding_name, "documents")
    if not os.path.exists(os.path.join(file_dir, filename)):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(file_dir, filename, as_attachment=False)


def get_content_type(filename):
    if filename.endswith(".pdf"):
        return "application/pdf"
    elif filename.endswith(".png"):
        return "image/png"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    elif filename.endswith(".gif"):
        return "image/gif"
    elif filename.endswith(".csv"):
        return "text/csv"
    elif filename.endswith(".txt"):
        return "text/plain"
    elif filename.endswith(".md"):
        return "text/markdown"
    else:
        return "application/octet-stream"


@app.route("/preview-chunks")
def preview_chunks():
    filename = request.args.get("filename")
    if not filename:
        return jsonify({"error": "Missing filename"}), 400

    filepath = os.path.join("documents", filename)
    text = extract_text_from_file(filepath)
    chunks = split_text(text, 4096)
    return jsonify({"chunks": chunks})

if __name__ == "__main__":
    app.run(port=5000, debug=True, threaded=False)