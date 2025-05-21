# backend/Dockerfile

FROM continuumio/miniconda3

# Set work directory
WORKDIR /app

# Copy environment.yml into the container
COPY environment.yml .

# Create the Conda environment and clean up
RUN conda env create -f environment.yml && \
    conda clean -afy

# Make sure the env is active by default in interactive shells
SHELL ["conda", "run", "-n", "research_gpt2", "/bin/bash", "-c"]

# Copy the backend source code
COPY . .

# Expose FastAPI port
EXPOSE 8888

# Run the app using uvicorn in the conda env
CMD ["conda", "run", "-n", "research_gpt2", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]


# docker build -t backend-conda ./backend
# docker run --env-file ./backend/.env -p 8888:8888 backend-conda
