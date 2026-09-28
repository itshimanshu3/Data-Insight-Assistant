# GenAI Data Insight Assistant

A data assistant that lets you query a database in plain English instead of SQL. You can type something like:

"Show me the 5 most expensive brands by average price, but only brands with at least 20 products."

...and get back the SQL that was generated, a results table, a chart, and a short plain-English summary of what the numbers say, not just a raw table.

I built this as a RAG (Retrieval-Augmented Generation) pipeline with five stages: the system first retrieves only the parts of the database schema that matter for your question, has an LLM write the SQL from that context, validates the query before it can run, executes it on a read-only connection (with one automatic retry if it fails), and finally explains the result. A cache sits in front of all of it so repeated questions cost nothing.

## How it works

```
User question
│
▼
Cache → the normalized question is hashed and checked against a local
SQLite cache (a hit skips everything below)
│
▼
Retrieve → the question is embedded locally and searched against schema
descriptions in ChromaDB, returning only the most relevant tables
│
▼
Generate → the LLM writes a PostgreSQL SELECT using only that retrieved
schema plus the last few turns of conversation
│
▼
Validate → sqlglot parses the SQL into a syntax tree; anything that isn't
a SELECT on an allow-listed table is rejected before it runs
│
▼
Execute → runs on Supabase through a read-only Postgres role; if it errors,
the exact database error goes back to the LLM for one corrected retry
│
▼
Explain → a smaller LLM writes a 2-3 sentence summary while a rule-based
step picks the chart type
│
▼
Streamlit frontend → shows SQL, table, chart, and insight; result is cached
and the query is logged
```

I went with separate stages instead of one giant prompt that does everything, mainly because it keeps each stage testable on its own and makes it obvious where things break when they do.

## Stack

- **Data:** Supabase (free hosted PostgreSQL) holding a Flipkart products table, plus a `query_logs` table for observability
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`), small enough to run locally on CPU, so retrieval costs nothing and never touches API rate limits
- **Vector search:** ChromaDB, persisted locally, storing table and column descriptions
- **LLM:** Groq's free API. `openai/gpt-oss-120b` writes the SQL and `openai/gpt-oss-20b` writes the summaries (swapped in from Llama 3.3 70B and Llama 3.1 8B after Groq deprecated them, more on that below)
- **SQL validation:** sqlglot
- **Cache:** SQLite
- **Charts:** Plotly, with rule-based chart selection
- **Frontend:** Streamlit, calling the pipeline modules directly
- **Tests:** pytest, plus a small evaluation script (more on that below)

## Why RAG and not just sending the whole schema

The obvious approach is to paste the full schema into every prompt. That works for a handful of tables, but it gets expensive fast, since every request pays for tokens it doesn't need, and it gives the model more chances to grab a plausible-sounding but wrong table or column. Retrieving only the relevant tables keeps the prompt small and gives the model less room to wander.

To be honest, my sample schema is small enough that this doesn't make a dramatic difference on accuracy today. I built it this way because the pattern is what scales: the same pipeline works on a 200-table schema without changing anything except what's in the vector store.

## Why two models instead of one

Writing correct SQL needs real reasoning, so it gets the larger model. Summarizing a five-row result into two sentences doesn't, so it gets a smaller, faster one. That cuts latency on the step where the user is waiting, and since Groq's free-tier limits are tracked per model, the two tasks also draw from separate quotas instead of competing for one.

## Why sqlglot and a read-only role

A keyword blocklist ("reject anything containing DROP") is easy to get around with comments or odd formatting, and it can't tell that a query touches a table it shouldn't. Parsing the SQL into an actual syntax tree lets me check what the query structurally is: which statement type, which tables.

But I didn't want the whole safety story to depend on my validator having no bugs. So the database connection itself uses a Postgres role that only has SELECT privileges. If the validator ever let something bad through, the database would still refuse to execute it. Two independent layers, so a mistake in one doesn't cause damage.

## Stopping bad SQL

The generation step only ever sees the retrieved schema and is told to use exact table and column names from it. On top of that, the validator rejects any table that isn't on the allow-list, so an invented table name never reaches the database. And if a query still fails at execution (a wrong column name, say), the exact error message is fed back to the LLM for one corrected attempt. It only retries once, so a bad question can't loop forever or burn through the free-tier quota.

## Living on free tiers

The whole project runs at zero cost, which shaped a few decisions:

- **Caching:** repeated questions never hit the LLM at all, which matters when you're demoing the same queries over and over against a rate-limited API.
- **Local embeddings:** retrieval doesn't consume any API quota.
- **Model deprecation:** partway through the build, Groq retired the two models I was using and every call started failing with a 400 error. Swapping the model names fixed it, but the real lesson was that hardcoding a model string is a dependency risk. Checking the provider's live model list at startup, and falling back to another model if one disappears, is the change I'd make next.

## Evaluation

I put together a test set of [N] questions against the sample dataset, each with a reference SQL query I wrote by hand, and ran three kinds of checks:

- Execution accuracy (does the generated query return the same result as the reference query): XX%
- Exact SQL match (generated SQL parses to the same structure as the reference): XX%
- Safety tests (destructive requests like "delete all customers" get blocked before execution): N/N blocked

The two accuracy numbers will disagree, and I kept both on purpose. Two different SQL queries can return exactly the same answer (different join order, different aliases, a subquery instead of a join), so exact match undercounts real correctness. Execution accuracy is the fairer read on whether the answer is right, and exact match is the stricter one.

## What doesn't work perfectly (and I know about it)

- **The validator checks structure, not meaning.** A perfectly valid SELECT on an allowed table can still answer the wrong question. Validation guarantees a query is safe, not that it's correct. It also checks tables, not individual columns.
- **No handling for ambiguous questions.** If a question is vague, the model just picks an interpretation and runs with it. Detecting low-confidence retrieval and asking the user to rephrase would be the fix.
- **Insights are based on a preview.** The summary step only sees the first five rows and the column names of the result, so on a large result set it can describe the top of the table more confidently than the data justifies. Passing aggregates (min, max, averages) alongside the preview would help.
- **Memory is shallow.** Follow-up questions only carry the last few user questions, not the earlier SQL or results, so complicated multi-step follow-ups can lose context.
- **The cache is exact-match.** "top 5 products by price" and "5 most expensive products" are two separate cache entries. Matching on semantic similarity would raise the hit rate.
- **Free-tier ceiling.** Rate limits are fine for one person or a live demo, but not for many concurrent users. SQLite is also a single-writer database, so a real deployment would move the cache to Postgres.
- **No access control.** There's one global table allow-list, no per-user or per-role permissions.
- **No few-shot examples yet.** Storing verified question-and-SQL pairs and retrieving similar ones alongside the schema would likely improve accuracy on the trickier queries.

## Project layout

```
genai-data-assistant/
├── app.py                      # Streamlit frontend
├── modules/
│   ├── retriever.py            # embeds the question, searches ChromaDB
│   ├── prompt_builder.py       # assembles the LLM prompt
│   ├── sql_generator.py        # stage 3: question -> SQL via Groq
│   ├── validator.py            # stage 4: sqlglot safety checks
│   ├── executor.py             # runs SQL on Supabase (read-only role)
│   ├── insight_generator.py    # stage 5: plain-English summary via Groq
│   ├── visualizer.py           # rule-based chart selection
│   ├── cache.py                # SQLite cache
│   └── logger.py               # writes query logs to Supabase
├── config/
│   └── allowed_tables.yaml     # tables the assistant may query
├── scripts/
│   └── index_schema.py         # embeds schema descriptions into ChromaDB
├── tests/
│   ├── test_validator.py       # no API key needed
│   ├── test_pipeline.py        # exercises the full pipeline
│   ├── test_eval.py            # accuracy evaluation
│   └── eval_set.json           # questions + reference SQL
└── requirements.txt
```

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY and your Supabase connection strings
```

Set up the database once in the Supabase SQL editor: load your dataset, create the `query_logs` table, and create the read-only role.

```sql
CREATE ROLE readonly WITH LOGIN PASSWORD 'your_readonly_password';
GRANT CONNECT ON DATABASE postgres TO readonly;
GRANT USAGE ON SCHEMA public TO readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
```

Then list the tables the assistant is allowed to query in `config/allowed_tables.yaml`, and:

```bash
# embed the schema into ChromaDB (re-run whenever the schema changes)
python scripts/index_schema.py

# tests and evaluation
python tests/test_validator.py
python tests/test_pipeline.py
python tests/test_eval.py

# run the app
streamlit run app.py
```

You can also run a single stage by itself to debug it, for example `python modules/sql_generator.py`.
