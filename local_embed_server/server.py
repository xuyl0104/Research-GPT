from fastapi import FastAPI, Request
from transformers import AutoTokenizer, AutoModel
import torch

app = FastAPI()

print("Loading model...")
model = AutoModel.from_pretrained("jinaai/jina-embeddings-v2-base-en", trust_remote_code=True)
tokenizer = AutoTokenizer.from_pretrained("jinaai/jina-embeddings-v2-base-en", trust_remote_code=True)
model.eval()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
print("Model loaded.")

@app.post("/v1/embeddings")
async def get_embedding(request: Request):
    body = await request.json()
    input_texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
    encoded = tokenizer(input_texts, padding=True, truncation=True, max_length=8192, return_tensors="pt").to(device)
    with torch.no_grad():
        output = model(**encoded)
        embeddings = output.last_hidden_state.mean(dim=1).cpu().tolist()
    return {
        "object": "list",
        "data": [{"embedding": e, "index": i} for i, e in enumerate(embeddings)],
        "model": "jinaai/jina-embeddings-v2-base-en",
        "usage": {"total_tokens": sum(len(t) for t in input_texts)}
    }
