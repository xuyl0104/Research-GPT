import faiss
import pickle
import os

global_index = None
global_chunks = []
embedded_filenames = set()


if os.path.exists("faiss.index") and os.path.exists("chunks.pkl"):
    try:
        global_index = faiss.read_index("faiss.index")
        with open("chunks.pkl", "rb") as f:
            global_chunks = pickle.load(f)
            embedded_filenames = {chunk["filename"] for chunk in global_chunks}
        print("FAISS index and chunks loaded from disk.")
    except Exception as e:
        print(f"Failed to load saved index: {e}")
