# 🧪 Part 1 – Evaluation Pipeline

## 📌 What Is the Evaluation For?
The evaluation module measures how accurately the extraction system converts filled PDFs into structured JSON. It checks:
- **Exact-match accuracy** per field
- **Similarity scores** for fuzzy text fields
- **Overall exact-match rate** across the dataset

This ensures your extraction pipeline (OCR → LLM parsing → JSON) works reliably.

## 📁 What Is the Generated Dataset?
The dataset is a collection of **synthetically generated PDFs** and **their matching golden JSON files**. Each PDF is created by filling a template with randomized but realistic Hebrew data.

Each pair includes:
- `ex_###.pdf` – the filled and flattened PDF
- `ex_###.golden.json` – the true values used to generate the PDF

This controlled dataset enables **repeatable, deterministic evaluation**.

## ▶️ How to Generate the Dataset
```bash
python Part_1/generate_dataset.py \
  --in Part_1/phase1_data/template.pdf \
  --outdir Part_1/evaluation/dataset \
  --n 100
```

## ▶️ How to Run the Evaluation
```bash
python Part_1/evaluation/eval_dataset.py \
  --dataset Part_1/evaluation/dataset \
  --outdir Part_1/evaluation/out_eval
```

Outputs include:
- `per_example.csv` – accuracy per document
- `per_field.csv` – accuracy per field
- `summary.json` – aggregate metrics
- `plot_accuracy_per_field.png`
- `plot_similarity_per_field.png`

## 📊 Evaluation Result Images
(Add images here by placing generated evaluation PNG files in the repo and linking them)

![Accuracy per Field](Part_1/evaluation/out_eval/plot_accuracy_per_field.png)

![Similarity per Field](Part_1/evaluation/out_eval/plot_similarity_per_field.png)

---

## 📄 Extended Evaluation Guide
A full, detailed explanation of the evaluation process is available in:

➡️ **[Part_1/evaluation/README_EVAL.md](Part_1/evaluation/README_EVAL.md)**

This document explains:
- Dataset generation internals
- Field-by-field comparison logic
- Metrics definitions
- Tips for improving extraction accuracy
- How to interpret the plots
