Unit 3 Capstone: Building an Intelligent Document Search Pipeline
===========================

### Project Overview

In this capstone, you'll design and build a real-world intelligent document search system using AWS. Your pipeline will automate document ingestion, ETL, vectorization, structured data storage, and setup for future Retrieval-Augmented Generation (RAG) workflows.

**You'll deliver a working pipeline that processes both unstructured (PDF) and structured (CSV, JSON) files, making them searchable and ready for analytics.**

**This year, the AI query layer (previously a stretch goal) is a required Bronze deliverable, and includes a mandatory SQL validation layer and tokenomics tracking.**

**Two implementation notes based on confirmed sandbox testing:**
1. **Document embeddings use Sentence Transformers, not Bedrock.** Both of Bedrock's embedding model families were tested directly and both are denied — `amazon.titan-embed-text-v2:0` and `cohere.embed-english-v3` — while Claude (text generation) is confirmed working. This is a structural gap in current sandbox permissions (embeddings capability, not one specific model), not something fixable by picking a different Bedrock embedding model. Sentence Transformers runs locally, requires no API key, and produces the same kind of embedding vector for OpenSearch indexing.
2. **All Bedrock/Claude calls must use the inference-profile ARN as the model ID, not the bare model name.** Newer Claude models on Bedrock (including `claude-sonnet-4-6`) require this — calling with just `anthropic.claude-sonnet-4-6-v1:0` returns a `ValidationException`. See Step 2.5 for the correct pattern.

**✅ This entire pipeline has been verified end-to-end in a live sandbox run** — chunking, Sentence Transformers embedding generation, vector indexing, semantic retrieval, and Claude-via-Bedrock generation were all confirmed working together against a real test document, producing a correct, properly-cited answer. This is not a theoretical fix; every piece has been run and confirmed. See the Instructor Guide's verification script for the exact test used.

* * * * *

Step 1: Review Your Materials
-----------------------------

-   **Understand your reference architecture** and data flow (diagram will be provided in class).

-   Review AWS service documentation and code/lab samples provided in the course.

Step 2: Build the Required AWS Data Flow & Infrastructure
---------------------------------------------------------

#### **Must-Have Features:**

-   **Central Storage:**

    -   Use **S3** as the main repository for all incoming documents (PDFs, CSVs, JSON).

-   **Automated Ingestion & Processing:**

    -   Uploads to S3 automatically trigger **AWS Lambda** functions.

    -   For PDFs: Lambda uses **Amazon Textract** to extract text, intelligently chunks the text (500-1000 tokens), and generates embeddings via **Sentence Transformers** (local, no API key required — see implementation note above).

    -   Store raw extracted text in **AWS RDS** for structured querying.

    -   Store vector embeddings in **OpenSearch** for semantic search.

-   **ETL for Structured Data:**

    -   Use **AWS Glue Crawler** to automatically catalog and discover schemas in all ingested files.

    -   Use **AWS Glue Transform** to run ETL jobs for:

        -   Data normalization

        -   Schema validation

        -   Systematic loading of CSV/JSON into **Redshift** tables

        -   Populate Redshift with both structured data and vector embeddings

-   **Unified Data Warehouse:**

    -   **AWS Redshift** acts as your consolidated warehouse for SQL-queryable data and vector embeddings.

-   **Visualization & BI:**

    -   Generate at least 2 charts from your Redshift data using matplotlib (Python), saved as image files.

-   **Automation, Security & Control:**

    -   Use **Lambda** for workflow automation and event handling.

    -   Use **BOTO3** for scripting and programmatic control.

    -   Apply **IAM** best practices for security and permissions.

Step 2.5: Build the Required AI Query Layer (Now Bronze, Not Stretch)
------------------------------------------------------------------------

Using **Amazon Bedrock (Claude)**, build a query interface that can:

-   **Route intelligently** — given a natural language question, decide whether it needs OpenSearch (semantic/document search), Redshift (SQL/structured data), or both

-   **Translate to SQL** — for questions requiring Redshift, generate and execute a SQL query using Claude via Bedrock

-   **Generate contextual responses** — for questions requiring OpenSearch, retrieve relevant chunks and generate a grounded answer citing sources

```python
import boto3, json

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
account_id = boto3.client("sts").get_caller_identity()["Account"]

# Claude models on Bedrock (including claude-sonnet-4-6) require the
# inference-profile ARN, not the bare model ID. Calling with just
# "anthropic.claude-sonnet-4-6-v1:0" returns a ValidationException.
MODEL_ID = f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-6"

def invoke_claude(prompt: str, max_tokens: int = 500) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    result = json.loads(response["body"].read())
    return {"text": result["content"][0]["text"],
            "input_tokens": result["usage"]["input_tokens"],
            "output_tokens": result["usage"]["output_tokens"]}
```

> **✅ Check before building anything else:** Run this function once, standalone, with a simple test prompt. Confirm you get a real response before building the rest of the query layer on top of it.

Step 2.75: Add a Required SQL Validation Layer
-------------------------------------------------

No Bedrock-generated SQL query may execute against Redshift without passing through validation first:

```python
BLOCKED_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]

def validate_sql(query: str) -> dict:
    query_upper = query.upper().strip()
    for keyword in BLOCKED_KEYWORDS:
        if f" {keyword} " in f" {query_upper} " or query_upper.startswith(keyword):
            return {"valid": False, "reason": f"Blocked: {keyword} not permitted"}
    if not query_upper.startswith("SELECT"):
        return {"valid": False, "reason": "Only SELECT queries are permitted"}
    return {"valid": True, "reason": "OK"}
```

Test with at least 5 cases including at least one stacked-query attempt (`SELECT ...; DROP TABLE ...;`) before wiring the validator into a live Redshift connection.

Step 2.9: Add Tokenomics Tracking
-------------------------------------

Log token usage for every Bedrock call (classification, SQL generation, and contextual response generation), and produce a cost summary after a 10-query test run.

Step 3: Test and Document
-------------------------

-   Test your pipeline end-to-end by uploading PDFs and structured files and validating data flow to RDS, OpenSearch, and Redshift.

-   Test your AI query layer against both the standard query types and the harder synthesis queries below.

-   Document your architecture, how each service is used, and how to test or extend the pipeline.

### New Harder Queries (Required This Year)

These require your system to route to **both** OpenSearch and Redshift and combine the results into a single answer citing both sources — not two separate answers, and not just whichever source was checked first:

-   "Does our current customer churn rate (from the data warehouse) align with what our documented retention strategy says we should be seeing?"

-   "Based on our data governance policy documents, are any of the currently-ingested datasets missing required metadata fields (check against the Glue Catalog)?"

* * * * *

Must-Have Checklist
-------------------
>🥉 Bronze - complete all must-haves

-   S3 stores raw PDFs, CSVs, and JSONs

-   Lambda triggers on upload; calls Textract for PDFs

-   Textract extracts and chunks PDF text

-   **Sentence Transformers generates document embeddings** (Bedrock embedding models — both Titan and Cohere — confirmed denied; see implementation note)

-   Raw text stored in RDS; embeddings in OpenSearch

-   Glue Crawler catalogs and discovers data schemas

-   Glue ETL normalizes, validates, and loads CSV/JSON into Redshift

-   Redshift consolidates structured and vector data

-   Matplotlib charts (2+) visualize Redshift data

-   Lambda and BOTO3 automate flows

-   IAM secures resources

-   **AI query layer implemented: smart routing, NL-to-SQL, and contextual document response generation, all using Bedrock (Claude), via the inference-profile ARN**

-   **SQL validation layer implemented and tested (minimum 5 cases, including a stacked-query test)**

-   **Tokenomics logging across all Bedrock calls, with a 10-query cost summary**

-   **Both new harder synthesis queries answered correctly, citing both sources**

Stretch Goals
-------------
>🥈 Silver - complete 1 stretch goal <br> 🥇 Gold - complete both

**Push further by adding intelligence and unified user experience:**

-   **LangGraph Routing Refactor:**

    -   Refactor your routing logic using LangGraph instead of a single classification prompt

-   **Enterprise Knowledge API:**

    -   Build a simple API Gateway + Lambda endpoint exposing your query interface for programmatic access, rather than only a CLI or notebook interface — deliver unified endpoints that blend document retrieval with structured data insights, enabling users to query both with natural language

Tips for Success
----------------

-   **Work in stages:** Build one piece, test it, then connect it to the next.

-   **Automate everything:** Use Lambda, Glue, and BOTO3 to keep manual steps to a minimum.

-   **Confirm infrastructure before AI work:** Make sure your S3, RDS, OpenSearch, Redshift, and Glue pipeline is fully working before building the AI query layer on top of it — debugging infrastructure and AI logic at the same time wastes your capstone time.

-   **Confirm Bedrock access before building the AI layer:** Run a single standalone test call to `invoke_claude()` using the inference-profile ARN pattern above before writing any routing or SQL-generation logic on top of it.

-   **Validate before you execute:** Never let a Bedrock-generated SQL query run against Redshift without passing through your validator first.

-   **Focus on clarity:** Comment your code and document every architectural choice.

-   **Ask for help:** Don't spend too long blocked!

Deliverables
------------

-   Full pipeline codebase and infrastructure setup (Boto3 scripts, Glue jobs, Lambda functions)

-   Working AI query interface supporting SQL, search, and combined routing

-   Validation test suite output

-   Tokenomics summary from a 10-query test run

-   README with architecture diagram, setup instructions, and test results for both new harder queries
