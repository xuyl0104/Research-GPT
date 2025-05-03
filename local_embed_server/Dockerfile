FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY server.py .

ENV TRANSFORMERS_CACHE=/root/.cache/huggingface
ENV HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
