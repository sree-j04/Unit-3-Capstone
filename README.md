---

## Implementation Notes & Limitations

This capstone was built end-to-end with real AWS services where sandbox permissions allowed, and documented local substitutes where they didn't:

**Real AWS services used:**

- **S3** — stores the raw PDF (`raw-pdfs/`)
- **Textract** — extracts text from the PDF (synchronous, single-page due to API limits)
- **Sentence Transformers** — generates embeddings locally (Bedrock embedding models confirmed denied in this sandbox)
- **Bedrock (Claude)** — powers the AI query layer: routing, NL-to-SQL, and grounded document answers, via the required inference-profile ARN pattern

**Local substitutes (documented, not hidden):**

- **RDS → SQLite** (`capstone.db`): RDS creation failed with a KMS encryption key permission error in this sandbox account. SQLite plays the same role — structured storage of extracted text and the sample sales dataset.
- **OpenSearch → local JSON vector store** (`vector_store.json`) with cosine-similarity search: OpenSearch domain provisioning was skipped to fit the available time; the same retrieval logic (embed query, find nearest chunks) is implemented locally.
- **Glue + Redshift → SQLite `sales` table**: structured data loading and querying logic (validated SQL, schema-aware) mirrors what would run against Redshift.

**Written but not executed (permission constrained):**

- `lambda/lambda_function.py` — real Lambda trigger logic; not deployed because packaging sentence-transformers for Lambda needs container images/layers beyond the available time. The same logic was verified working as a local script.
- `scripts/glue_setup.py` — Glue Crawler + ETL job setup; not executed due to time constraints and the same class of IAM/KMS permission issues hit on RDS.
- CSV upload to S3 (`raw-structured/`) was attempted via `scripts/upload_structured_data.py` and failed with AccessDenied — this IAM user's programmatic access does not have S3 PutObject permission on this bucket (console access differs from CLI credentials).

**Required features implemented and tested:**

- SQL validation layer blocking DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE/GRANT/REVOKE and non-SELECT queries, tested against 7 cases including a stacked-query injection attempt
- Smart routing (SQL / DOCUMENT / BOTH) via Claude
- NL-to-SQL generation, validated before execution
- Grounded document Q&A with source citations
- Combined-source synthesis for the harder queries requiring both structured and document data
- Tokenomics logging (input/output tokens) across all Bedrock calls with a cost summary
- 2 matplotlib charts generated from the structured dataset

**How to run:**
pip install -r requirements.txt
python scripts/test_s3_connection.py
python scripts/test_bedrock.py
python scripts/process_pdf.py
python scripts/query_layer.py
