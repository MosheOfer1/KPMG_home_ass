# 🚀 Quick Setup Instructions

## 1. Prerequisites
- Python 3.12
- Git installed
- Azure credentials in a `.env` at repo root

## 2. Installation
```bash
git clone <repo-url>
cd KPMG_home_ass
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Run All Services
From **repo root**:
```bash
python -m Part_2.run_all
```
Services:
- Frontend → http://127.0.0.1:7860

## 4. Tests
```bash
pytest Part_2
```

## 5. Notes
- Always run commands from the **repo root**.
- `.env` file must include your Azure keys.

