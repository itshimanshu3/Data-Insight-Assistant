import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# ===== REPLACE THIS WITH YOUR SESSION POOLER URL =====
ADMIN_URL = 'postgresql://postgres.zxqxejsojshtmkvdvjfd:genaidataassistant@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres'
# =====================================================

def to_float(v):
    if pd.isna(v):
        return 0.0
    if isinstance(v, str):
        v = v.strip().lower()
        if 'no rating' in v or 'not available' in v or 'rating' in v:
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0

print('📂 Loading CSV...')
df = pd.read_csv('flipkart_com-ecommerce_sample.csv')
print(f'✅ Loaded {len(df)} rows')

print('🔌 Connecting to Supabase via Session Pooler (IPv4)...')
conn = psycopg2.connect(
    ADMIN_URL,
    connect_timeout=10,          # fail fast instead of hanging
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5,
)
cur = conn.cursor()
cur.execute("SET statement_timeout = '600000';")  # 10 minutes, single quotes
conn.commit()

try:
    print('📊 Creating table...')
    cur.execute('DROP TABLE IF EXISTS flipkart_products CASCADE;')
    cur.execute('''
        CREATE TABLE flipkart_products (
            id SERIAL PRIMARY KEY,
            product_name TEXT,
            brand TEXT,
            category TEXT,
            price NUMERIC,
            rating NUMERIC,
            description TEXT
        );
    ''')
    conn.commit()
    print('✅ Table created')

    print('📝 Preparing rows...')
    records = [
        (
            str(row.get('product_name', ''))[:500],
            str(row.get('brand', ''))[:100],
            str(row.get('product_category_tree', ''))[:100],
            to_float(row.get('discounted_price')),
            to_float(row.get('product_rating')),
            str(row.get('description', ''))[:1000],
        )
        for _, row in df.iterrows()
    ]

    print(f'📝 Inserting {len(records)} rows in batches of 500...')
    chunk_size = 500
    inserted = 0
    for start in range(0, len(records), chunk_size):
        batch = records[start:start + chunk_size]
        execute_values(cur, '''
            INSERT INTO flipkart_products
                (product_name, brand, category, price, rating, description)
            VALUES %s
        ''', batch, page_size=500)
        conn.commit()
        inserted += len(batch)
        print(f'   ✅ Inserted {inserted} rows...')

    print(f'\n🎉 Successfully imported {inserted} rows into Supabase!')

except Exception as e:
    conn.rollback()
    print(f'❌ Import failed: {e}')
    raise
finally:
    cur.close()
    conn.close()
EOF