#!/usr/bin/env python3
"""
Data Insight Assistant - E-commerce Edition
Neutral, modern theme. Auto-insights with fallback, KPI cards,
in-app filtering/sorting, and multi-format export.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import base64
import io
import json

from modules.retriever import retrieve_context
from modules.sql_generator import generate_sql
from modules.validator import validate_sql
from modules.executor import execute_query
from modules.insight_generator import generate_insight
from modules.cache import get_cache, set_cache

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="Product Data Assistant",
    page_icon="🛒",
    layout="wide"
)

# ========== CUSTOM CSS (neutral e-commerce theme) ==========
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #334155 60%, #0ea5e9 100%);
        padding: 1.75rem 2rem;
        border-radius: 14px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 14px rgba(0,0,0,0.12);
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #e2e8f0;
        font-size: 1.05rem;
        margin: 0.4rem 0 0;
    }
    .insight-box {
        background: #eff6ff;
        border-left: 5px solid #0ea5e9;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin: 0.5rem 0 1rem;
        font-size: 1.02rem;
        color: #0f172a;
        line-height: 1.5;
    }
    .insight-fallback-note {
        font-size: 0.82rem;
        color: #64748b;
        margin-top: 0.5rem;
    }
    div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid #e2e8f0;
        font-size: 0.85rem;
        color: #94a3b8;
    }
</style>
""", unsafe_allow_html=True)

# ========== HEADER ==========
st.markdown("""
<div class="main-header">
    <h1>🛒 Product Data Assistant</h1>
    <p>Ask questions about your product catalog in plain English</p>
</div>
""", unsafe_allow_html=True)

# ========== SESSION STATE ==========
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None
if 'total_queries' not in st.session_state:
    st.session_state.total_queries = 0
if 'favorites' not in st.session_state:
    st.session_state.favorites = []

# ========== HELPERS ==========

PRICE_COL_CANDIDATES = ["price", "discounted_price", "retail_price", "cost", "amount"]
RATING_COL_CANDIDATES = ["rating", "product_rating", "overall_rating", "stars"]
IMAGE_COL_CANDIDATES = ["image", "image_url", "img", "thumbnail"]


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def fallback_insight(df: pd.DataFrame, question: str) -> str:
    """Simple stats-based insight generated directly from the dataframe.
    Used when the AI-generated insight is missing or fails, so the
    Insight tab is never blank."""
    if df is None or len(df) == 0:
        return "No rows were returned for this query, so there's nothing to summarize."

    parts = [f"Your query returned **{len(df):,} rows**."]

    price_col = find_col(df, PRICE_COL_CANDIDATES)
    if price_col and pd.api.types.is_numeric_dtype(df[price_col]):
        parts.append(
            f"**{price_col}** ranges from ₹{df[price_col].min():,.2f} to "
            f"₹{df[price_col].max():,.2f}, averaging ₹{df[price_col].mean():,.2f}."
        )

    rating_col = find_col(df, RATING_COL_CANDIDATES)
    if rating_col and pd.api.types.is_numeric_dtype(df[rating_col]):
        parts.append(
            f"Average **{rating_col}** is {df[rating_col].mean():.2f}."
        )

    cat_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    for c in cat_cols[:1]:
        top = df[c].value_counts().head(1)
        if len(top) > 0:
            parts.append(f"The most common **{c}** is '{top.index[0]}' ({top.iloc[0]} rows).")

    return " ".join(parts)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="results")
    return buf.getvalue()


# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("### Quick Questions")
    if st.button("Top 5 Brands"):
        st.session_state.quick_q = "What are the top 5 brands by number of products?"
        st.rerun()
    if st.button("Highest Rated"):
        st.session_state.quick_q = "Show me the top 10 highest rated products"
        st.rerun()
    if st.button("Price Distribution"):
        st.session_state.quick_q = "What is the price distribution of products?"
        st.rerun()
    if st.button("Category Counts"):
        st.session_state.quick_q = "How many products are in each category?"
        st.rerun()

    st.divider()

    if st.session_state.favorites:
        st.markdown("### ⭐ Saved Queries")
        for i, fav in enumerate(st.session_state.favorites):
            if st.button(f"↻ {fav[:40]}", key=f"fav_{i}"):
                st.session_state.quick_q = fav
                st.rerun()
        st.divider()

    if st.session_state.history:
        st.markdown("### 🕘 Recent")
        for i, h in enumerate(reversed(st.session_state.history[-5:])):
            if st.button(f"↻ {h['question'][:40]}", key=f"recent_{i}"):
                st.session_state.quick_q = h['question']
                st.rerun()
        st.divider()

    st.caption(f"Total queries: {st.session_state.total_queries}")

# ========== MAIN QUERY AREA ==========
if 'quick_q' in st.session_state:
    default_q = st.session_state.quick_q
    del st.session_state.quick_q
else:
    default_q = ""

question = st.text_input(
    "Ask a question about your products:",
    value=default_q,
    placeholder="e.g., Show me the top 10 most expensive smartphones"
)

col1, col2 = st.columns([1, 5])
with col1:
    ask_button = st.button("🔎 Ask", type="primary", use_container_width=True)
with col2:
    if question and st.button("⭐ Save this query"):
        if question not in st.session_state.favorites:
            st.session_state.favorites.append(question)
            st.toast("Saved to favorites")


# ========== PIPELINE FUNCTION ==========
def run_pipeline(question):
    with st.spinner("Thinking..."):
        cached = get_cache(question)
        if cached:
            st.success("Cache hit")
            return cached

        context = retrieve_context(question)
        if not context:
            st.error("Couldn't find relevant tables.")
            return None

        sql = generate_sql(question, context, st.session_state.history)
        if not sql:
            st.error("Failed to generate SQL. Please rephrase.")
            return None

        is_valid, reason, cleaned = validate_sql(sql)
        if not is_valid:
            st.error(f"Blocked: {reason}")
            return {"sql": sql, "error": reason, "blocked": True}

        df, error = execute_query(cleaned)

        if error and "does not exist" in error.lower():
            st.info("Retrying with error feedback...")
            retry_context = context + [{"description": f"Error: {error}"}]
            retry_sql = generate_sql(question, retry_context, st.session_state.history)
            if retry_sql:
                is_valid, reason, cleaned = validate_sql(retry_sql)
                if is_valid:
                    df, error = execute_query(cleaned)
                    sql = retry_sql

        if error:
            st.error(f"{error}")
            return {"sql": sql, "error": error}

        # ----- INSIGHT (with fallback so this tab is never blank) -----
        insight_raw = None
        insight_error = None
        try:
            insight_raw = generate_insight(question, df, sql)
        except Exception as e:
            insight_error = str(e)

        if insight_raw and str(insight_raw).strip():
            insight = str(insight_raw).strip()
            insight_source = "ai"
        else:
            insight = fallback_insight(df, question)
            insight_source = "fallback"

        result = {
            "question": question,
            "sql": sql,
            "df": df,
            "insight": insight,
            "insight_source": insight_source,
            "insight_error": insight_error,
            "error": None,
            "blocked": False,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.history.append(result)
        st.session_state.total_queries += 1

        set_cache(question, sql, df, insight, None)

        return result


# ========== DISPLAY RESULTS ==========
if ask_button and question:
    result = run_pipeline(question)
    if result:
        st.session_state.current_result = result
        st.rerun()

if st.session_state.current_result:
    res = st.session_state.current_result

    if res.get("error"):
        st.error(f"{res['error']}")
        if res.get("sql"):
            with st.expander("SQL"):
                st.code(res["sql"], language="sql")
    else:
        df = res["df"]
        st.success(f"Found {len(df)} products")

        # ----- KPI ROW (computed directly from data, always available) -----
        price_col = find_col(df, PRICE_COL_CANDIDATES)
        rating_col = find_col(df, RATING_COL_CANDIDATES)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Rows", f"{len(df):,}")
        if price_col and pd.api.types.is_numeric_dtype(df[price_col]):
            k2.metric(f"Avg {price_col}", f"₹{df[price_col].mean():,.0f}")
            k3.metric(f"Price range", f"₹{df[price_col].min():,.0f}–₹{df[price_col].max():,.0f}")
        else:
            k2.metric("Avg price", "—")
            k3.metric("Price range", "—")
        if rating_col and pd.api.types.is_numeric_dtype(df[rating_col]):
            k4.metric(f"Avg {rating_col}", f"{df[rating_col].mean():.2f}")
        else:
            k4.metric("Avg rating", "—")

        # ----- FILTER / SORT TOOLBAR -----
        filtered_df = df.copy()
        with st.expander("Filter & sort results"):
            fcol1, fcol2 = st.columns(2)

            cat_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
            with fcol1:
                if cat_cols:
                    filt_col = st.selectbox("Filter by column", ["(none)"] + cat_cols)
                    if filt_col != "(none)":
                        options = sorted(df[filt_col].dropna().unique().tolist())
                        chosen = st.multiselect(f"Show only these {filt_col} values", options)
                        if chosen:
                            filtered_df = filtered_df[filtered_df[filt_col].isin(chosen)]

            with fcol2:
                if price_col and pd.api.types.is_numeric_dtype(df[price_col]):
                    lo, hi = float(df[price_col].min()), float(df[price_col].max())
                    if lo < hi:
                        sel_lo, sel_hi = st.slider(
                            f"{price_col} range", lo, hi, (lo, hi)
                        )
                        filtered_df = filtered_df[
                            (filtered_df[price_col] >= sel_lo) & (filtered_df[price_col] <= sel_hi)
                        ]

            sort_col = st.selectbox("Sort by", ["(default)"] + df.columns.tolist())
            if sort_col != "(default)":
                ascending = st.radio("Order", ["Descending", "Ascending"], horizontal=True) == "Ascending"
                filtered_df = filtered_df.sort_values(sort_col, ascending=ascending)

        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Data", "Insight", "Chart", "SQL", "Export"]
        )

        with tab1:
            image_col = find_col(filtered_df, IMAGE_COL_CANDIDATES)
            if image_col:
                try:
                    st.dataframe(
                        filtered_df,
                        use_container_width=True,
                        column_config={
                            image_col: st.column_config.ImageColumn(image_col, width="small")
                        },
                    )
                except Exception:
                    st.dataframe(filtered_df, use_container_width=True)
            else:
                st.dataframe(filtered_df, use_container_width=True)
            st.caption(f"Showing {len(filtered_df)} of {len(df)} rows after filters")

        with tab2:
            st.markdown(f'<div class="insight-box">💡 {res["insight"]}</div>',
                        unsafe_allow_html=True)
            if res.get("insight_source") == "fallback":
                note = "This is an auto-generated summary of the data"
                if res.get("insight_error"):
                    note += " (the AI insight step failed)."
                else:
                    note += " (the AI insight step returned nothing)."
                st.markdown(f'<div class="insight-fallback-note">{note}</div>', unsafe_allow_html=True)
                if res.get("insight_error"):
                    with st.expander("Debug: insight generation error"):
                        st.code(res["insight_error"])

        with tab3:
            if len(filtered_df) > 0:
                numeric_cols = filtered_df.select_dtypes(include=['number']).columns.tolist()
                text_cols = filtered_df.select_dtypes(include=['object', 'string']).columns.tolist()

                if numeric_cols or text_cols:
                    cc1, cc2, cc3 = st.columns(3)
                    chart_type = cc1.selectbox("Chart type", ["Bar", "Line", "Histogram", "Scatter"])
                    x_axis = cc2.selectbox("X axis", text_cols + numeric_cols)
                    y_axis = cc3.selectbox("Y axis", numeric_cols) if numeric_cols else None

                    try:
                        if chart_type == "Bar" and y_axis:
                            fig = px.bar(filtered_df, x=x_axis, y=y_axis, color_discrete_sequence=['#0ea5e9'])
                        elif chart_type == "Line" and y_axis:
                            fig = px.line(filtered_df, x=x_axis, y=y_axis, color_discrete_sequence=['#0ea5e9'])
                        elif chart_type == "Histogram":
                            fig = px.histogram(filtered_df, x=x_axis, color_discrete_sequence=['#0ea5e9'])
                        elif chart_type == "Scatter" and y_axis:
                            fig = px.scatter(filtered_df, x=x_axis, y=y_axis, color_discrete_sequence=['#0ea5e9'])
                        else:
                            fig = None
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Pick a numeric Y axis for this chart type.")
                    except Exception as e:
                        st.warning(f"Couldn't render this chart: {e}")
                else:
                    st.info("No columns available for charting.")

        with tab4:
            st.code(res["sql"], language="sql")

        with tab5:
            e1, e2, e3 = st.columns(3)
            csv = filtered_df.to_csv(index=False)
            e1.download_button("Download CSV", csv, "query_result.csv", "text/csv")

            js = filtered_df.to_json(orient="records", indent=2)
            e2.download_button("Download JSON", js, "query_result.json", "application/json")

            try:
                xlsx_bytes = to_excel_bytes(filtered_df)
                e3.download_button(
                    "Download Excel", xlsx_bytes, "query_result.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception:
                e3.caption("Install `xlsxwriter` to enable Excel export.")

# ========== FOOTER ==========
st.markdown("""
<div class="footer">
    Built with Streamlit, Groq, ChromaDB, and Supabase<br>
    Data source: Flipkart product catalog (sample of 20,000 products)
</div>
""", unsafe_allow_html=True)