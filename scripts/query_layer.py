import os
import json
import sqlite3
import boto3
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
account_id = boto3.client("sts").get_caller_identity()["Account"]
MODEL_ID = f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-6"

DB_PATH = "capstone.db"
VECTOR_STORE_PATH = "vector_store.json"

token_log = []


def invoke_claude(prompt: str, max_tokens: int = 500) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
        result = json.loads(response["body"].read())
        usage = {
            "input_tokens": result["usage"]["input_tokens"],
            "output_tokens": result["usage"]["output_tokens"],
        }
        token_log.append(usage)
        return {"text": result["content"][0]["text"], **usage}
    except Exception as e:
        print(f"  [Bedrock call failed: {e}]")
        return {"text": f"[Bedrock call failed: {e}]", "input_tokens": 0, "output_tokens": 0}


# ---------- SQL validation (required layer) ----------

BLOCKED_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]


def validate_sql(query: str) -> dict:
    query_upper = query.upper().strip()
    for keyword in BLOCKED_KEYWORDS:
        if f" {keyword} " in f" {query_upper} " or query_upper.startswith(keyword):
            return {"valid": False, "reason": f"Blocked: {keyword} not permitted"}
    if not query_upper.startswith("SELECT"):
        return {"valid": False, "reason": "Only SELECT queries are permitted"}
    return {"valid": True, "reason": "OK"}


def run_sql_validation_tests():
    test_cases = [
        "SELECT * FROM sales",
        "SELECT product, SUM(revenue) FROM sales GROUP BY product",
        "DROP TABLE sales",
        "SELECT * FROM sales; DROP TABLE sales;",
        "DELETE FROM sales WHERE customer_id = 1",
        "UPDATE sales SET revenue = 0",
        "INSERT INTO sales VALUES (1,2,3)",
    ]
    print("\n=== SQL Validation Tests ===")
    for tc in test_cases:
        result = validate_sql(tc)
        print(f"  {tc[:50]:<50} -> valid={result['valid']}  ({result['reason']})")


# ---------- Structured data (Redshift substitute - documented in README) ----------

def load_structured_data():
    conn = sqlite3.connect(DB_PATH)
    data = {
        "product": ["Widget A", "Widget A", "Widget B", "Widget B", "Widget C", "Widget C"],
        "month": ["2026-01", "2026-02", "2026-01", "2026-02", "2026-01", "2026-02"],
        "revenue": [12000, 15000, 8000, 9500, 20000, 21000],
        "customer_id": [1, 1, 2, 2, 3, 3],
        "churned": [0, 0, 1, 1, 0, 0],
    }
    df = pd.DataFrame(data)
    df.to_sql("sales", conn, if_exists="replace", index=False)
    conn.close()
    print("Loaded sample structured data into SQLite table 'sales'")
    return df


# ---------- Charts ----------

def make_charts(df):
    import matplotlib.pyplot as plt

    os.makedirs("charts", exist_ok=True)

    df.groupby("product")["revenue"].sum().plot(kind="bar", title="Total Revenue by Product")
    plt.ylabel("Revenue ($)")
    plt.tight_layout()
    plt.savefig("charts/revenue_by_product.png")
    plt.close()

    df.groupby("month")["revenue"].sum().plot(kind="line", marker="o", title="Revenue Trend by Month")
    plt.ylabel("Revenue ($)")
    plt.tight_layout()
    plt.savefig("charts/revenue_trend.png")
    plt.close()

    print("Saved charts/revenue_by_product.png and charts/revenue_trend.png")


# ---------- Document search (OpenSearch substitute - documented in README) ----------

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def search_documents(query_embedding, top_k=3):
    if not os.path.exists(VECTOR_STORE_PATH):
        return []
    with open(VECTOR_STORE_PATH, "r") as f:
        store = json.load(f)
    scored = [(cosine_similarity(query_embedding, item["embedding"]), item) for item in store]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


# ---------- Routing + AI query layer (required Bronze deliverable) ----------

def route_query(question: str) -> str:
    prompt = f"""Classify this question into exactly one category: SQL, DOCUMENT, or BOTH.
- SQL: needs structured/numeric data (revenue, sales, churn counts) from a database
- DOCUMENT: needs information from text documents
- BOTH: needs both structured data AND document context combined

Question: {question}

Answer with exactly one word: SQL, DOCUMENT, or BOTH."""
    result = invoke_claude(prompt, max_tokens=10)
    return result["text"].strip().upper()


def answer_sql_question(question: str) -> str:
    schema = "Table 'sales': product (text), month (text), revenue (int), customer_id (int), churned (0/1)"
    prompt = f"""Given this SQLite schema:
{schema}

Write ONE SQL SELECT query (no explanation, just the SQL) to answer: {question}"""
    result = invoke_claude(prompt, max_tokens=200)
    sql = result["text"].strip().strip("`").replace("sql\n", "")

    validation = validate_sql(sql)
    if not validation["valid"]:
        return f"[Blocked SQL] {validation['reason']} -- generated query was: {sql}"

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(sql).fetchall()
    except Exception as e:
        return f"[SQL execution error] {e} -- query: {sql}"
    conn.close()
    return f"SQL: {sql}\nResult: {rows}"


def answer_document_question(question: str, model) -> str:
    query_embedding = model.encode(question).tolist()
    chunks = search_documents(query_embedding)
    context = "\n\n".join(c["text"] for c in chunks)
    sources = ", ".join(f"{c['filename']} (chunk {c['chunk_index']})" for c in chunks)

    prompt = f"""Answer the question using ONLY the context below. Cite the source filename.

Context:
{context}

Question: {question}"""
    result = invoke_claude(prompt, max_tokens=400)
    return f"{result['text']}\n[Sources: {sources}]"


def answer_query(question: str, model) -> str:
    route = route_query(question)
    print(f"\nQ: {question}\nRoute: {route}")

    if route == "SQL":
        return answer_sql_question(question)
    elif route == "DOCUMENT":
        return answer_document_question(question, model)
    else:
        sql_part = answer_sql_question(question)
        doc_part = answer_document_question(question, model)
        synth_prompt = f"""Combine these two findings into one answer citing both sources:

Structured data finding:
{sql_part}

Document finding:
{doc_part}

Question: {question}"""
        result = invoke_claude(synth_prompt, max_tokens=400)
        return result["text"]


def tokenomics_summary():
    total_input = sum(t["input_tokens"] for t in token_log)
    total_output = sum(t["output_tokens"] for t in token_log)
    # Example rate - check actual Bedrock Claude pricing for your model and update
    cost = (total_input / 1_000_000 * 3) + (total_output / 1_000_000 * 15)
    print("\n=== Tokenomics Summary ===")
    print(f"Total Bedrock calls: {len(token_log)}")
    print(f"Total input tokens: {total_input}")
    print(f"Total output tokens: {total_output}")
    print(f"Estimated cost: ${cost:.4f}")


if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    run_sql_validation_tests()

    df = load_structured_data()
    make_charts(df)

    test_queries = [
        "What was the total revenue for Widget A?",
        "What was the total revenue for Widget B?",
        "Which product had the highest revenue?",
        "How many customers churned?",
        "What is the average monthly revenue across all products?",
        "What experience does the person in the document have?",
        "What skills are listed in the document?",
        "What is the person's educational background?",
        "Does our current customer churn rate align with what our documented retention strategy says we should be seeing?",
        "Based on our data governance policy documents, are any of the currently-ingested datasets missing required metadata fields (check against the Glue Catalog)?",
    ]

    for q in test_queries:
        answer = answer_query(q, model)
        print(f"A: {answer}\n{'-'*60}")

    tokenomics_summary()