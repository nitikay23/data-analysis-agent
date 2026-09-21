# Project 4 — Agentic Data Analysis with Tool Selection and Guardrails

A GenAI data-analysis agent that interprets natural-language questions, validates operations via deterministic guardrails, executes calculations strictly through a deterministic Python analysis engine, and formats structured results.

## Architecture

```text
User Question
     │
     ▼
LLM Client (Probabilistic Intent & Tool Call Selection)
     │
     ▼
Guardrails Validator (Untrusted Tool Request Sanitization & Safety Boundary)
     │
     ▼
Tool Registry (Restricted Capability Execution)
     │
     ▼
Analysis Engine (Deterministic Arithmetic, Filtering, Aggregation, Grouping)
     │
     ▼
Presentation Formatter (Exact Decimal & Monetary Rules)
     │
     ▼
CLI Output / Response
```

## Structure

```text
project/
├── src/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── data/
│   │   ├── loader.py
│   │   └── schema.py
│   ├── analysis/
│   │   ├── engine.py
│   │   └── metrics.py
│   ├── guardrails/
│   │   └── validator.py
│   ├── tools/
│   │   ├── registry.py
│   │   └── analysis_tool.py
│   ├── agent/
│   │   └── orchestrator.py
│   ├── llm/
│   │   ├── client.py
│   │   ├── prompts.py
│   │   └── exceptions.py
│   └── presentation/
│       └── formatter.py
├── tests/
├── data/
│   └── project_4.csv
├── docs/
├── pyproject.toml
├── README.md
└── .env.example
```

## Setup & Running

```bash
# Install dependencies
pip install -e .

# Run full test suite (106 unit & integration tests)
pytest

# Run a single query using local deterministic mock LLM
python src/main.py "What is the total revenue for UK transactions?" --mock

# Run the complete Q001-Q010 evaluation benchmark
python src/main.py --eval --mock

# Run against a local Ollama instance (default model: llama3.2 at http://localhost:11434)
python src/main.py "What is the total revenue for UK transactions?"
```
