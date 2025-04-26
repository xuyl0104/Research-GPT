# Flask backend: simplified /ask route using chatbot.answer_question with 15s timeout handling

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import asyncio
from chatbot import update_index, extract_text_from_file, split_text, answer_question
import memory

UPLOAD_DIR = "documents"

app = Flask(__name__)
CORS(app)

@app.route("/embed-files", methods=["POST"])
def embed_files():
    import memory
    import shutil

    name = request.args.get("name")
    append = request.args.get("append", "false").lower() == "true"
    if not name:
        return jsonify({"error": "Missing embedding name"}), 400

    emb_dir = os.path.join("embeddings", name)
    docs_dir = os.path.join(emb_dir, "documents")
    os.makedirs(docs_dir, exist_ok=True)

    # Save uploaded files
    uploaded_files = request.files.getlist("files")
    max_size = 0
    for file in uploaded_files:
        save_path = os.path.join(docs_dir, file.filename)
        file.save(save_path)
        max_size = max(max_size, os.path.getsize(save_path))

    chunk_size = min(max_size, 8000)
    asyncio.run(update_index(docs_dir, chunk_size, emb_dir, append))
    return jsonify({"status": "success", "message": f"Embedded in '{name}'"})

@app.route("/list-embeddings")
def list_embeddings():
    emb_root = "embeddings"
    if not os.path.exists(emb_root):
        return jsonify({"embeddings": []})
    names = sorted([d for d in os.listdir(emb_root) if os.path.isdir(os.path.join(emb_root, d))])
    return jsonify({"embeddings": names})


@app.route("/load-embedding")
def load_embedding():
    import memory
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