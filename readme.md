Steps to run the project:

- frontend: 
    inside the folder ir_gpt, run 'npm run dev'

- backend:
    inside the folder ir_gpt/src/backend, run 'python app.py'

- embedding server:
    in WSL2 of windows, inside folder ~/projects/local_embed_server, run 'docker-compose up -d' to start embedding server
    run 'docker-compose down' to shut down server

TODO: 
Category | Ideas | Why
🛠 Frontend UX | Smooth file upload previews, progress bars, collapsible sidebar | Make UI feel super professional
💬 Chatbot UX | Streaming token-by-token answer ("typing...") | Real ChatGPT feel
🧠 Embedding Features | Support multi-embedding workspaces, tagging, search filtering | Scale your system
📄 Document Support | Handle more formats: .pptx, .md, even HTML scraping | Expand capability
🗂 Backend Infra | Async API server (e.g., FastAPI instead of Flask) | Speed up backend for big embeddings
🗄 Persistent Storage | Save uploaded files, embeddings into cloud storage (AWS S3) | Handle production data safely
🏗 Deployment | Docker + Docker Compose | Easy full deployment, production-ready
🛡 Auth Security | Simple login, token-based upload protection | Prepare for public use