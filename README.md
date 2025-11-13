# KPMG Home Assignment – Full README

## 📦 Repository Structure

This repository contains **two independent parts**:

* **Part 1:** Document Intelligence + Azure OpenAI extraction pipeline
* **Part 2:** Microservice-based medical chatbot system

---

# 🧩 Part 1 – Document Extraction System

Extract fields from ביטוח לאומי (NII) PDF forms using **Azure Document Intelligence (OCR)** + **Azure OpenAI**.

### 🔧 Setup

### 🔑 Environment variables

Create a `.env` file in the repo root from the template:

```bash
cp .env.example .env
````

Then open .env and fill in your Azure credentials.

Then install dependencies:
```bash
cd KPMG_home_ass
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ▶️ Run Extraction
To run the Gradio GUI simply run:
```bash
python Part_1/app.py
```

You can also specify a PDF file to extract via CLI using the `--file` flag or `--url` flag:
Also, you can specify the output directory via `--out` flag.
```bash
python Part_1/extract_pdf_to_json.py --file Part_1/phase1_data/283_ex1.pdf --out Part_1/phase1_data/283_ex1.json
```

Produces JSON with extracted fields.

### 🧪 Evaluate Extraction

Dataset: `Part_1/evaluation/dataset`

```bash
pytest Part_1
```

Evaluation outputs saved to: `Part_1/evaluation/out_eval`

---

# 🧩 Part 2 – Microservice Chatbot System

A fully stateless microservice architecture:

* **Orchestrator Service** (LLM logic)
* **API Gateway** (frontend/backend communication layer)
* **Gradio Frontend UI** (client-side session memory)
* **Retriever** (HTML Knowledge Base)

### 🚀 Quick Start (Run All Services)

From **repo root**:

```bash
python -m Part_2.run_all
```

Services:

* **Frontend:** [http://127.0.0.1:7860](http://127.0.0.1:7860)
* **API Gateway:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Orchestrator:** [http://127.0.0.1:8001](http://127.0.0.1:8001)

### 🧪 Tests

```bash
pytest Part_2
```
---
### ▶️ Running the app locally
```bash
python Part_2/run_all.py
```
---

# ⚙️ Requirements

* Python **3.12**
* Azure OpenAI keys in `.env`
* Run repo always from **root directory**

---

# 🙌 Notes

* `run_all.py` automatically handles all microservices.
* All session memory is stored client-side (required by assignment).
* For HTTPS locally, use any reverse proxy (Caddy, mkcert, local CA) if needed.

---

# 👍 You're Ready!

You now have a full working pipeline:

* PDF → JSON extraction (Part 1)
* AI-powered medical chatbot using microservices (Part 2)

Happy coding! 🎉
