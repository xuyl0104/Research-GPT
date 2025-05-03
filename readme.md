Steps to run the project:

- frontend: 
    inside the folder /ir_gpt, run 'npm run dev'

- backend:
    inside the folder /backend, run 'uvicorn main:app --reload'

- local embedding server:
    in WSL2 of windows, inside folder ~/projects/local_embed_server (change to your folder accordingly), run 'docker-compose up -d' to start embedding server
    run 'docker-compose down' to shut down server

- pgsql
    inside 
