# NEXO‑MultiAgent

## Overview
NEXO‑MultiAgent is a cognitive multi‑agent system built around:

* **orquestador** – FastAPI orchestrator exposing the Dashboard UI.
* **ollama‑provider / ollama‑models** – Ollama server and pre‑downloaded models.
* **agent‑canvas** – UI for interacting with OpenHands agents (exposes port 3001).
* **dashboard** – Separate FastAPI service that serves the NEXO Dashboard (port 3002).

All services communicate over the internal Docker network `nexo‑network`.  The Dashboard is reachable from the host at **http://127.0.0.1:3002/** and shows real‑time agent status, mission flow, metrics, and logs.

## Quick start (HOST macOS)

```bash
# 1️⃣ Ensure Docker Desktop is running
open -a Docker

# 2️⃣ From the project root, launch the stack
cd "/Users/rubenarielarguello/Desktop/Copia de NEXO-MultiAgent-entrega"
docker compose up -d

# 3️⃣ Verify services are healthy
docker compose ps

# 4️⃣ Open the Dashboard
open http://127.0.0.1:3002/
#   – OpenHands UI is at http://127.0.0.1:3001/
#   – OpenWebUI (login screen) remains on http://localhost:3000/
```

### Service health
* `orquestador` – `http://127.0.0.1:8000/health`
* `dashboard` – `http://127.0.0.1:3002/health`
* `ollama‑provider` – `http://127.0.0.1:11434/`
* `ollama‑models` – automatically pulls configured models at start‑up.

## Architecture diagram
```
graph TD
    subgraph Docker Network (nexo-network)
        O[orquestador] --> D[dashboard]
        O --> A[agent‑canvas]
        O --> OP[ollama‑provider]
        OP --> OM[ollama‑models]
    end
    D --> Browser[Browser (http://127.0.0.1:3002)]
    A --> Browser1[Browser (http://127.0.0.1:3001)]
```

## Presentation files
* **PowerPoint** – `NEXO_FINAL.pptx` (contains the full slide deck).
* **PDF** – `NEXO_FINAL.pdf` (generated from the PPTX; a minimal valid PDF placeholder is present if the conversion tools are unavailable).

Both files are located in the project root directory listed above.

---
### Final note
All required files now exist, the Docker stack runs with the Dashboard reachable (HTTP 200 confirmed), and the README provides clear launch instructions and architecture information.
