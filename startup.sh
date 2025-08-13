#!/bin/bash
set -e  # stop on first error

# Pgsql
echo "Starting PostgreSQL in Docker..."
cd /home/ubuntu/Projects/Research-GPT/backend/app/pgsql
docker compose up -d


# Frontend
echo "Building frontend container..."

cd /home/ubuntu/Projects/Research-GPT/ir_gpt
docker build -f Dockerfile.dev -t react-dev .

echo "Stopping any existing frontend container..."
docker rm -f react-ui 2>/dev/null || true

echo "Starting frontend container..."
docker run -d \
  --name react-ui \
  --restart unless-stopped \
  -p 3334:3334 \
  react-dev
echo "Frontend started on port 3334."

# Embedding server
echo "Starting embed server container..."
cd /home/ubuntu/Projects/Research-GPT/local_embed_server
docker compose up -d

# Backend
echo "Starting backend..."
source /root/miniconda3/etc/profile.d/conda.sh
cd /home/ubuntu/Projects/Research-GPT/backend
conda activate research_gpt2
nohup conda run -n research_gpt2 uvicorn main:app --reload --host 0.0.0.0 --port 8888 > backend.log 2>&1 &

echo "All services started."
