import os
import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
BUCKET = os.environ["S3_BUCKET_NAME"]
s3 = boto3.client("s3", region_name="us-east-1")

data = {
    "product": ["Widget A", "Widget A", "Widget B", "Widget B", "Widget C", "Widget C"],
    "month": ["2026-01", "2026-02", "2026-01", "2026-02", "2026-01", "2026-02"],
    "revenue": [12000, 15000, 8000, 9500, 20000, 21000],
    "customer_id": [1, 1, 2, 2, 3, 3],
    "churned": [0, 0, 1, 1, 0, 0],
}
pd.DataFrame(data).to_csv("sales_sample.csv", index=False)

s3.upload_file("sales_sample.csv", BUCKET, "raw-structured/sales_sample.csv")
print("Uploaded sales_sample.csv to raw-structured/")