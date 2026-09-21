"""
AWS Lambda handler — triggers on S3 upload to raw-pdfs/.
NOT DEPLOYED in this submission: packaging sentence-transformers (multi-GB with
torch) for Lambda requires container images or large layers, which wasn't
feasible in the available time. The same logic runs successfully as a local
script in scripts/process_pdf.py, which was tested end-to-end against real
S3 + Textract.
"""
import json
import boto3

s3 = boto3.client("s3")
textract = boto3.client("textract")


def lambda_handler(event, context):
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    response = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = response["JobId"]

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Started Textract job {job_id} for {key}"}),
    }