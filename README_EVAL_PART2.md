# 🧪 Part 2 – Evaluation Guide

This folder contains the **evaluation framework for the Orchestrator + Retriever** in the medical chatbot system.

The goal is to ensure that the chatbot:

* Produces correct medical service responses
* Handles user profile overrides properly
* Returns valid citations
* Switches phases correctly
* Responds in the correct language and structure

---

## 📁 What This Evaluation Does

The evaluation runner loads a set of **structured test cases** from `cases.json`, each defining:

* **User input** (a question)
* **Profile overrides** (optional changes to default user profile)
* **Expectation functions** that assert correctness of the chatbot's output

It then:

1. Calls the Orchestrator service for each case
2. Runs all expectation checks
3. Records pass/fail, errors, latency, and citation count
4. Generates plots and a CSV report

---

## ▶️ How to Run the Retriever Evaluation

Run from repo root:

```bash
python -m Part_2.evaluation.eval_retriever --cases Part_2/evaluation/retriever_cases.json
```

**Output:**

* `retriever_eval.csv` with: `hit_at_k`, `mrr`, retrieved vs expected URIs.
* `retriever_pie.png`

![retriever_pie.png](Part_2/evaluation/eval_out/retriever_pie.png)


**Purpose:**
Checks if the retriever returns the correct KB HTML chunk IDs for each query.

**Case File Format:**
Each entry contains:

* `id`
* `query`
* optional `hmo`, `tier`
* `expected_uris` (IDs after `#`)

**How it Works:**

1. Loads cases.
2. Builds embedder + HtmlKB.
3. Runs `kb.search()`.
4. Computes Hit@K + MRR.
5. Saves CSV.

---

## 📄 Test Case Format (cases.json)

Each case looks like:

```json
{
  "id": "basic_maccabi_case",
  "user_input": "מה ההטבה במסלול זהב במכבי?",
  "profile_overrides": {"hmo_name": "MACCABI"},
  "expectations": [
    {"fn": "expect_type_and_basics"},
    {"fn": "expect_words", "args": ["מכבי"]}
  ]
}
```

---

## ✔ Output Example

After running, the terminal prints:

```
✔ Passed 9/12
Wrote CSV and plots to: Part_2/evaluation/eval_out
```

---

## 📌 Notes

* Expectation builders are fully modular and extendable
* No external services beyond the Orchestrator + Retriever are needed
* Evaluation does **not** require the API Gateway or frontend

---
