# CS533 Information Retrieval Project 3 --- Research-GPT

## Structure of the project
``` bash.
.
├── backend                          <-- backend
│   ├── app
│   │   ├── auth.py
│   │   ├── auth_utils.py
│   │   ├── aws_s3_utils.py
│   │   ├── chatbot.py
│   │   ├── __init__.py
│   │   ├── memory.py
│   │   └── pgsql                    <-- database
│   ├── Dockerfile
│   ├── embedding.py
│   ├── environment.yml
│   ├── __init__.py
│   └── main.py
├── ir_gpt                           <-- frontend
│   ├── Dockerfile.dev
│   ├── package.json
│   ├── package-lock.json
│   ├── public
│   └── src
│       └── app
├── local_embed_server               <-- local embedding
│   ├── commands
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
└── readme.md
```


### Frontend
Created with **React** and **Next**. Able to
- Register new users;
- User login;
- Upload files and create embeddings or append new files to existing embeddings;
- Load embeddings and chat history;
- Ask questions and get answers from the MistralAI server;
- Turn on FullPower model to ask LLM any questions (not limited to information in the files).



### Backend
#### API module

Created with **FastAPI**.

- **JWT** login enabled 

Utilized MistralAI language models `mistral-large-latest` for question answering.

Facebook AI Similarity Search (**faiss**) packaged was used for indexing and search.


#### Database
Persists user and embedding releted meta data (index-path, chunk-path, messages) into **PostgreSQL**.

Run in docker.

#### Embedding file and chunk cloud storage

Used **Amazon Web Service (AWS) S3** to store all the user created embedding files (index, chunks)


#### Embedding Model
Deployed the `jinaai/jina-embeddings-v2-base-en` embedding model.

Hosted in docker.

## Steps to run the project

### Frontend
    - install node, npm, npx on your machine
  
    - install packages used in React, run
        npm install

    - inside the folder /ir_gpt, run:
        npm run dev

    (
        I recommend doing all of this using docker. Enter into the folder /ir_gpt and run:
        
        docker build -f Dockerfile.dev -t react-dev .
        docker run -it --rm -p 3334:3334 --name react-ui react-dev

        before running with docker, you should have a .env in the /ir_gpt folder with the following content:

        NEXT_PUBLIC_API_URL=http://xxx.xxx.xxx.xxx:8888/api

        (replace xxx.xxx.xxx.xxx with your server IP)
    )
### PostgreSQL
    inside backend/app/pgsql folder
    to start pgsql, run:
        docker-compose up -d

    to stop shutdown pgsql, run:
        docker-compose down
    
    to check docker status, run:
        docker ps

    after you have started pgsql in docker, run the following to create the schema:
        python init_db.py

### Backend
    - create python virtual environment:
        conda env create -f environment.yml

    - (manually install any packages needed when error messages arise)

    - inside the folder /backend, run:
        uvicorn main:app --reload --host 0.0.0.0 --port 8080

Before you run the project, you need to have all the **secret tokens** ready:

In the backend/ root folder, run

``` bash
pip install python-dotenv
```

Create a **.env** file in the folder

``` bash
SECRET_KEY=super-secret-uuid-or-64-char-string
```

The **.env** file should at least have the following configs:

``` yml
# JWT tokens 
# JWT tokens 
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# AWS tokens
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=research-gpt
AWS_REGION=us-east-2

# mistral ai API key
MISTRAL_KEY=

# API port
API_PORT=8000

# Embedding server IP
EMBED_SERVER_URL=
EMBED_SERVER_PORT=8000

# PostgreSQL info
PGSQL_PORT=5432
POSTGRES_USER=
POSTGRES_PASSWORD=
DATABASE_URL=

# API main
UPLOAD_DIR=documents
EMBEDDING_DIR=embeddings

```


### Local embedding server
    current local embedding model is hosted on my personal server.
    For future extension, install docker for your OS (Windows, Linux, or Mac OS)

    inside folder local_embed_server/  run: 
        docker-compose build
        docker-compose up -d
    
    to start embedding server, run:
        docker-compose up -d 
    
    to shut down server, run:
        docker-compose down

    to check docker status, run:
        docker ps


### Ready
Now, you will have frontend running in docker, backend running in the background (you can change it to docker in the future), pgsql database running in docker, local_embedding_server running in docker, AWS S3 running in the cloud. 

### In browser
Once all the components are on, then in the browser, go to `xxx.xxx.xxx.xxx:3334` to test. (xxx.xxx.xxx.xxx is you server IP or you domain name)