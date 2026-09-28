# 📊 GenAI Data Insight Assistant

> Ask questions about your database in plain English. Get back the SQL, a results table, a chart, and a plain-English summary, with no SQL knowledge required.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![LLM](https://img.shields.io/badge/LLM-Groq-orange)
![VectorDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-green)
![Database](https://img.shields.io/badge/Database-Supabase%20(PostgreSQL)-3ECF8E)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-black)

**🔗 Live Demo:** `<add your Streamlit Cloud URL here>`

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [How It Works](#-how-it-works)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [Testing & Evaluation](#-testing--evaluation)
- [Security Design](#-security-design)
- [Deployment](#-deployment)
- [Free-Tier Notes & Troubleshooting](#-free-tier-notes--troubleshooting)
- [Known Limitations](#-known-limitations)
- [Roadmap](#-roadmap)
- [Author](#-author)

---

## 🎯 Overview

Business users often have simple data questions ("What were our top 5 products by revenue?") but don't know SQL, so they wait on an analyst. This project removes that bottleneck.

A user types a question in plain English. The system:

1. Retrieves only the **relevant tables and examples** from a vector store (RAG), instead of sending the whole schema to the LLM.
2. Uses an LLM to **generate SQL** grounded in that retrieved context.
3. **Validates** the SQL for safety before it ever runs.
4. Executes it on a **read-only** database connection.
5. Generates a **plain-English insight** and an **auto-selected chart**.

The entire stack runs on **free tiers**: Groq, Supabase, ChromaDB, and Streamlit Community Cloud.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🗣️ Natural-language to SQL | Converts plain English questions into PostgreSQL `SELECT` queries |
| 🔍 RAG context retrieval | Retrieves relevant schema and few-shot examples from ChromaDB using local embeddings |
| 🛡️ SQL safety layer | AST-based validation with `sqlglot` + table allow-list + read-only DB role |
| 🔁 Self-correction | If a query fails, the DB error is fed back to the LLM for one automatic retry |
| 💡 Auto-generated insights | A smaller, faster LLM summarizes results in 2-3 plain-English sentences |
| 📈 Auto-visualization | Rule-based chart selection (line / bar / metric card) using Plotly |
| 🧠 Conversation memory | Follow-up questions use context from the last few turns |
| ⚡ Caching | Repeated questions return instantly from a local SQLite cache |
| 📝 Query logging | Every query logged (SQL, status, latency, tokens, model) for observability |

---

## 🧭 How It Works

```mermaid
flowchart TD
    A["User question (Streamlit)"] --> B{"Cache hit?"}
    B -- Yes --> J["Display cached result"]
    B -- No --> C["RAG retrieval: ChromaDB + local embeddings"]
    C --> D["SQL generation: Groq gpt-oss-120b"]
    D --> E["SQL validation: sqlglot + allow-list"]
    E -- Blocked --> X["Show safe error message"]
    E -- Valid --> F["Execute on Supabase (read-only role)"]
    F -- Error --> G["Self-correction: one LLM retry"]
    G --> E
    F -- Success --> H["Insight: Groq gpt-oss-20b + chart: Plotly"]
    H --> I["Cache result + log query"]
    I --> J
```

**Why two models?** SQL generation needs strong reasoning, so it uses the larger model (`openai/gpt-oss-120b`). Summarizing a small result table doesn't, so it uses the smaller, faster one (`openai/gpt-oss-20b`). This saves latency and spreads load across separate rate-limit pools.

**Why RAG?** Sending an entire schema on every request is expensive and increases hallucinated table/column names. Retrieving only the relevant context keeps prompts small and answers more accurate, and it scales to larger schemas.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Orchestration | Python modules / LangChain |
| LLM Inference | Groq API (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), runs locally |
| Vector Store | ChromaDB (persistent, local) |
| Business Database | Supabase (PostgreSQL) |
| SQL Validation | `sqlglot` |
| Data Handling | Pandas, psycopg2 |
| Visualization | Plotly |
| Cache | SQLite |
| Testing | pytest + custom evaluation harness |
| CI/CD | GitHub Actions |
| Hosting | Streamlit Community Cloud |

---

## 📁 Project Structure

```
genai-data-assistant/
├── app.py                      # Streamlit entrypoint
├── modules/
│   ├── retriever.py            # RAG retrieval from ChromaDB
│   ├── prompt_builder.py       # Builds the LLM prompt
│   ├── sql_generator.py        # NL -> SQL via Groq
│   ├── validator.py            # sqlglot-based safety checks
│   ├── executor.py             # Runs SQL on Supabase (read-only)
│   ├── insight_generator.py    # Plain-English summary via Groq
│   ├── visualizer.py           # Rule-based chart selection
│   ├── cache.py                # SQLite caching layer
│   └── logger.py               # Query logging to Supabase
├── config/
│   └── allowed_tables.yaml     # Table allow-list for the validator
├── scripts/
│   └── index_schema.py         # One-time script: embed schema into ChromaDB
├── tests/
│   ├── test_validator.py
│   ├── test_pipeline.py
│   └── eval_set.json           # Question -> expected SQL pairs
├── .github/workflows/ci.yml
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- A free [Supabase](https://supabase.com) account
- A free [Groq](https://console.groq.com) API key

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/genai-data-assistant.git
cd genai-data-assistant

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up the database (Supabase)

1. Create a new Supabase project.
2. Load your dataset into the SQL Editor (e.g., a products/orders dataset).
3. Create the logging table:

```sql
CREATE TABLE query_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_question TEXT NOT NULL,
    generated_sql TEXT,
    execution_status TEXT,
    latency_ms INTEGER,
    tokens_used INTEGER,
    model_used TEXT,
    cache_hit BOOLEAN DEFAULT FALSE,
    retrieved_tables TEXT
);
```

4. Create a **read-only** role for query execution:

```sql
CREATE ROLE readonly WITH LOGIN PASSWORD 'your_readonly_password';
GRANT CONNECT ON DATABASE postgres TO readonly;
GRANT USAGE ON SCHEMA public TO readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly;
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```env
# Groq
GROQ_API_KEY=your_groq_api_key

# Supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
READONLY_DB_URL=postgresql://readonly:password@db.your-project-ref.supabase.co:5432/postgres

# Local paths
VECTOR_STORE_PATH=./vector_store
CACHE_DB_PATH=./cache.db
ALLOWED_TABLES_PATH=./config/allowed_tables.yaml
```

> ⚠️ Never commit `.env`. It is listed in `.gitignore`.

### 4. Define the table allow-list

Edit `config/allowed_tables.yaml` with the tables the assistant may query:

```yaml
tables:
  - products
  - orders
  - customers
```

### 5. Index your schema into ChromaDB (run once)

```bash
python scripts/index_schema.py
```

Re-run this whenever your schema changes.

### 6. Run the app

```bash
streamlit run app.py
```

Open the URL shown in your terminal (usually `http://localhost:8501`).

---

## 💬 Usage

Type a question and press **Ask**:

- *"Show me the top 10 most expensive products"*
- *"What is the average price by brand?"*
- *"Now filter that to products rated above 4"* (follow-up using conversation memory)

For each question you get: the **generated SQL** (expandable), a **results table**, an **auto-selected chart**, and a **plain-English insight**.

You can also test individual modules on their own:

```bash
python modules/sql_generator.py
python modules/insight_generator.py
```

---

## 🧪 Testing & Evaluation

```bash
# Unit + safety tests
pytest tests/

# Accuracy evaluation against a fixed question -> SQL set
python tests/test_eval.py
```

| Test type | What it verifies |
|---|---|
| Unit tests | Validator logic, cache hit/miss behavior |
| Safety tests | Destructive requests ("delete all customers") are always blocked |
| Evaluation set | Generated SQL compared against expected SQL (AST comparison) |

**Latest evaluation result:** `XX% (N/N questions)` ← _fill in after running the eval script_

---

## 🔒 Security Design

Two independent layers protect the database:

1. **Application layer:** `sqlglot` parses generated SQL into an AST. Only `SELECT` statements are allowed, and every referenced table must be in the allow-list.
2. **Database layer:** query execution uses a PostgreSQL role with `SELECT`-only privileges, so even a validator gap cannot modify data.

Additional practices:

- API keys and credentials live in environment variables / Streamlit secrets, never in source control.
- Only schema metadata and small result previews are sent to the LLM provider, never full tables.

---

## ☁️ Deployment

1. Push the repo to GitHub.
2. On [Streamlit Community Cloud](https://streamlit.io/cloud), create a new app from the repo and set `app.py` as the entrypoint.
3. Add these values in the app's **Secrets** settings: `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `READONLY_DB_URL`.
4. GitHub Actions (`.github/workflows/ci.yml`) runs the test suite on every push.

---

## ⚠️ Free-Tier Notes & Troubleshooting

**Rate limits.** Groq's free tier is limited per model (requests/minute, tokens/minute, and daily caps). Check your live limits at `console.groq.com/settings/limits`. Caching is what keeps repeated demo questions from consuming quota. Daily limits reset at midnight UTC.

**`400 model_decommissioned` / `404 model not found`.** Groq periodically retires models. If you see this error:

1. Check the current model list and deprecations at `console.groq.com/docs/models` and `console.groq.com/docs/deprecations`.
2. Update the model strings in `modules/sql_generator.py` and `modules/insight_generator.py`.

**`GROQ_API_KEY not found`.** Make sure `.env` exists in the project root and `load_dotenv()` runs before the client is created.

**Creating files with `cat << 'EOF'`.** Run those heredoc commands directly in your terminal, not inside an editor or Python shell, or the `cat` line ends up inside the file.

---

## 🚧 Known Limitations

- Free-tier rate limits make this suitable for personal use and demos, not many concurrent users.
- SQLite cache is single-writer, so a hosted database would be needed for concurrency.
- Cache matches on normalized question text, not semantic similarity.
- No role-based access control; a single global table allow-list applies.
- Conversation memory is session-only and English-only.

---

## 🗺️ Roadmap

- [ ] Role-based access control (per-role table/column permissions)
- [ ] Semantic caching (match similar questions, not just identical ones)
- [ ] Hybrid retrieval (vector + keyword) with reranking
- [ ] Dynamic model discovery and automatic fallback chain
- [ ] FastAPI backend to decouple the pipeline from the UI
- [ ] Feedback loop: user-verified SQL added back into few-shot examples
- [ ] Docker support
- [ ] CSV / Excel export of results

---

## 👤 Author

**`<Your Name>`**
🔗 [LinkedIn](<your-linkedin-url>) · 💻 [GitHub](<your-github-url>) · 📧 `<your-email>`

---

⭐ If you found this project useful, consider giving it a star.
