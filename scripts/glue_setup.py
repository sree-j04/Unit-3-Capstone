"""
Glue Crawler + ETL job setup — NOT EXECUTED in this submission due to time
constraints and IAM/KMS permission issues already hit on RDS/S3 in this
sandbox account (see README limitations). Written to show the required
architecture: crawl raw-structured/ in S3, catalog its schema, then run
an ETL job to normalize and load into Redshift.
"""
import boto3

glue = boto3.client("glue", region_name="us-east-1")

CRAWLER_NAME = "capstone-structured-data-crawler"
DATABASE_NAME = "capstone_catalog"
S3_TARGET_PATH = "s3://sree-capstone3/raw-structured/"
IAM_ROLE_ARN = "arn:aws:iam::065241263235:role/GlueCapstoneRole"


def create_crawler():
    glue.create_database(DatabaseInput={"Name": DATABASE_NAME})
    glue.create_crawler(
        Name=CRAWLER_NAME,
        Role=IAM_ROLE_ARN,
        DatabaseName=DATABASE_NAME,
        Targets={"S3Targets": [{"Path": S3_TARGET_PATH}]},
    )
    glue.start_crawler(Name=CRAWLER_NAME)
    print(f"Started crawler {CRAWLER_NAME} against {S3_TARGET_PATH}")


def run_etl_job():
    """
    ETL job (PySpark, run on Glue's managed Spark environment) that would:
    1. Read the cataloged CSV/JSON schema from the Glue Data Catalog
    2. Validate required columns and types
    3. Normalize (e.g. dedupe, cast types)
    4. Write the result into Redshift via a JDBC connection
    """
    pass


if __name__ == "__main__":
    create_crawler()
    run_etl_job()