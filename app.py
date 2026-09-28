cat > app.py << 'EOF'
import streamlit as st
from modules.retriever import retrieve_context
from modules.sql_generator import generate_sql
from modules.validator import validate_sql
from modules.executor import execute_query
from modules.insight_generator import generate_insight

st.set_page_config(page_title="Data Insight Assistant", layout="wide")
st.title("🧠 GenAI Data Insight Assistant")

question = st.text_input("Ask a question about your data:")

if st.button("Ask") and question:
    with st.spinner("🧠 Thinking..."):
        # 1. Retrieve
        context = retrieve_context(question)
        
        # 2. Generate SQL
        sql = generate_sql(question, context)
        
        # 3. Validate
        is_valid, reason, cleaned_sql = validate_sql(sql)
        if not is_valid:
            st.error(f"🚫 {reason}")
            st.code(sql, language="sql")
        else:
            # 4. Execute
            df, error = execute_query(cleaned_sql)
            if error:
                st.error(f"❌ {error}")
            else:
                # 5. Insight
                insight = generate_insight(question, df, sql)
                
                st.success("✅ Query executed!")
                st.dataframe(df)
                st.info(f"💡 {insight}")
                with st.expander("🔍 SQL"):
                    st.code(sql, language="sql")
EOF