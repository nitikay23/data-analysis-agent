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
│   │   └── client.py
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

## Setup

```bash
# Install dependencies
pip install -e .

# Run test suite
pytest
```
