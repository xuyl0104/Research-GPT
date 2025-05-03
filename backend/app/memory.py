import faiss
import pickle
import os

global_index = None
global_chunks = []
embedded_filenames = set()
