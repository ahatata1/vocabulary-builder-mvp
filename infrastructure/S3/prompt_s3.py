import boto3
import json
from botocore.exceptions import ClientError

# =========================
# MANDATORY INPUTS (EDIT)
# =========================
REGION = "us-east-1"

WEBSITE_BUCKET = "vb-website-2025"
DOCS_BUCKET = "vb-documents-2025"

AWS_ACCOUNT_ID = "123456789012"          # TODO: replace with your AWS account ID
CLOUDFRONT_DISTRIBUTION_ID = "DXXXXXXXXXXX"  # TODO: replace with your CloudFront distribution ID

# Existing IAM role names (must already exist in IAM)
APP_BACKEND_ROLE_NAME = ""         # Backend (presigned URLs, business logic)
TEXTRACT_ROLE_NAME = ""        # Orchestrator that calls Textract
COMPREHEND_ROLE_NAME = ""    # Orchestrator that calls Comprehend

# =========================
# VALIDATION
# =========================

def validate_inputs():
    if not REGION:
        raise ValueError("REGION is required")
    if not WEBSITE_BUCKET or not DOCS_BUCKET:
        raise ValueError("Bucket names (WEBSITE_BUCKET, DOCS_BUCKET) are required")
    if REGION != "us-east-1":
        # For non us-east-1, CreateBucketConfiguration is required; your requirement is us-east-1.
        raise ValueError("This script is hard-coded for us-east-1 to match your requirements.")
    if not AWS_ACCOUNT_ID or len(AWS_ACCOUNT_ID) != 12 or not AWS_ACCOUNT_ID.isdigit():
        raise ValueError("AWS_ACCOUNT_ID must be a 12-digit AWS account ID.")
    if not CLOUDFRONT_DISTRIBUTION_ID:
        raise ValueError("CLOUDFRONT_DISTRIBUTION_ID is required for the CloudFront OAC policy.")

# =========================
# S3 CONFIGURATION HELPERS
# =========================

def create_bucket_if_not_exists(s3_client, bucket_name):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"[INFO] Bucket already exists: {bucket_name}")
        return
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code not in ("404", "NoSuchBucket", "NotFound"):
            raise

    print(f"[INFO] Creating bucket: {bucket_name}")
    # For us-east-1, do NOT supply CreateBucketConfiguration
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"[OK] Created bucket: {bucket_name}")
    except ClientError as e:
        print(f"[ERROR] Failed to create bucket {bucket_name}: {e}")
        raise


def configure_public_access_and_acl(s3_client, bucket_name):
    print(f"[INFO] Configuring Block Public Access and OwnershipControls for {bucket_name}")
    # Block Public Access = ON
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )

    # Disable ACLs (BucketOwnerEnforced)
    s3_client.put_bucket_ownership_controls(
        Bucket=bucket_name,
        OwnershipControls={
            "Rules": [
                {
                    "ObjectOwnership": "BucketOwnerEnforced"
                }
            ]
        },
    )


def configure_default_encryption_sse_s3(s3_client, bucket_name):
    print(f"[INFO] Enabling default SSE-S3 encryption on {bucket_name}")
    s3_client.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }
            ]
        },
    )


def configure_versioning(s3_client, bucket_name, enabled):
    status = "Enabled" if enabled else "Suspended"
    print(f"[INFO] Setting versioning on {bucket_name} to {status}")
    s3_client.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": status},
    )


def configure_docs_lifecycle(s3_client, bucket_name):
    """
    Lifecycle:
    - raw/ → delete after 90 days
    - textract-output/, comprehend-output/ → delete after 730 days
    """
    print(f"[INFO] Configuring lifecycle rules on documents bucket {bucket_name}")
    lifecycle_configuration = {
        "Rules": [
            {
                "ID": "ExpireRawPdfsAfter90Days",
                "Status": "Enabled",
                "Filter": {"Prefix": "raw/"},
                "Expiration": {"Days": 90},
            },
            {
                "ID": "ExpireTextractOutputAfter730Days",
                "Status": "Enabled",
                "Filter": {"Prefix": "textract-output/"},
                "Expiration": {"Days": 730},
            },
            {
                "ID": "ExpireComprehendOutputAfter730Days",
                "Status": "Enabled",
                "Filter": {"Prefix": "comprehend-output/"},
                "Expiration": {"Days": 730},
            },
        ]
    }

    s3_client.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration=lifecycle_configuration,
    )


def configure_website_bucket_policy_for_cloudfront(s3_client, bucket_name):
    """
    Allow ONLY CloudFront OAC to GetObject from website bucket.
    Using standard pattern: principal cloudfront.amazonaws.com with SourceArn condition.
    """
    print(f"[INFO] Applying CloudFront OAC bucket policy to {bucket_name}")

    cf_distribution_arn = f"arn:aws:cloudfront::{AWS_ACCOUNT_ID}:distribution/{CLOUDFRONT_DISTRIBUTION_ID}"

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowCloudFrontServicePrincipalReadOnly",
                "Effect": "Allow",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceArn": cf_distribution_arn
                    }
                },
            }
        ],
    }

    s3_client.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps(policy),
    )

# =========================
# IAM POLICY HELPERS
# =========================

def build_app_backend_inline_policy():
    """
    Backend → Put raw/, Get AI outputs, List with prefixes
    No wildcards.
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                # Put PDFs in raw/ and maybe textract-input if needed later
                "Sid": "AllowPutRawPdfs",
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/raw/*"
                ],
            },
            {
                # Backend can read raw and AI outputs for business logic
                "Sid": "AllowReadDocsAndOutputs",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/raw/*",
                    f"arn:aws:s3:::{DOCS_BUCKET}/textract-output/*",
                    f"arn:aws:s3:::{DOCS_BUCKET}/comprehend-output/*",
                ],
            },
            {
                # Optional: allow delete (if you want manual cleanup)
                "Sid": "AllowDeleteDocsAndOutputs",
                "Effect": "Allow",
                "Action": [
                    "s3:DeleteObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/raw/*",
                    f"arn:aws:s3:::{DOCS_BUCKET}/textract-output/*",
                    f"arn:aws:s3:::{DOCS_BUCKET}/comprehend-output/*",
                ],
            },
            {
                # List, but restricted by prefixes using condition
                "Sid": "AllowListDocsPrefixes",
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}"
                ],
                "Condition": {
                    "StringLike": {
                        "s3:prefix": [
                            "raw/",
                            "textract-output/",
                            "comprehend-output/"
                        ]
                    }
                },
            },
        ],
    }
    return policy


def build_textract_inline_policy():
    """
    Textract orchestrator → Get raw/, Put textract-output/
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowTextractReadRawPdfs",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/raw/*"
                ],
            },
            {
                "Sid": "AllowTextractWriteOutput",
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/textract-output/*"
                ],
            },
        ],
    }
    return policy


def build_comprehend_inline_policy():
    """
    Comprehend orchestrator → Get textract-output/, Put comprehend-output/
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowComprehendReadTextractOutput",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/textract-output/*"
                ],
            },
            {
                "Sid": "AllowComprehendWriteOutput",
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{DOCS_BUCKET}/comprehend-output/*"
                ],
            },
        ],
    }
    return policy


def attach_inline_policy(iam_client, role_name, policy_name, policy_doc):
    """
    Attach inline policy to an existing role with no wildcards in Actions/Resources.
    """
    print(f"[INFO] Attaching inline policy {policy_name} to role {role_name}")
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_doc),
        )
    except ClientError as e:
        print(f"[ERROR] Failed to attach policy {policy_name} to {role_name}: {e}")
        raise

# =========================
# MAIN EXECUTION
# =========================

def main():
    validate_inputs()

    s3_client = boto3.client("s3", region_name=REGION)
    iam_client = boto3.client("iam")

    # 1) Create buckets if they don't exist
    create_bucket_if_not_exists(s3_client, WEBSITE_BUCKET)
    create_bucket_if_not_exists(s3_client, DOCS_BUCKET)

    # 2) Security baseline: Block Public Access + ACLs disabled + SSE-S3
    for bucket in (WEBSITE_BUCKET, DOCS_BUCKET):
        configure_public_access_and_acl(s3_client, bucket)
        configure_default_encryption_sse_s3(s3_client, bucket)

    # 3) Versioning
    # Website: optional (disabled for MVP)
    configure_versioning(s3_client, WEBSITE_BUCKET, enabled=False)
    # Documents: enabled
    configure_versioning(s3_client, DOCS_BUCKET, enabled=True)

    # 4) Lifecycle for documents bucket
    configure_docs_lifecycle(s3_client, DOCS_BUCKET)

    # 5) Website bucket policy for CloudFront OAC
    configure_website_bucket_policy_for_cloudfront(s3_client, WEBSITE_BUCKET)

    # 6) IAM inline policies (no wildcards)
    #    Attach to existing roles (must be created separately with correct trust policies)
    if APP_BACKEND_ROLE_NAME:
        backend_policy = build_app_backend_inline_policy()
        attach_inline_policy(iam_client, APP_BACKEND_ROLE_NAME, "AppBackendS3Access", backend_policy)

    if TEXTRACT_ROLE_NAME:
        textract_policy = build_textract_inline_policy()
        attach_inline_policy(iam_client, TEXTRACT_ROLE_NAME, "TextractS3Access", textract_policy)

    if COMPREHEND_ROLE_NAME:
        comprehend_policy = build_comprehend_inline_policy()
        attach_inline_policy(iam_client, COMPREHEND_ROLE_NAME, "ComprehendS3Access", comprehend_policy)

    print("[DONE] S3 buckets and IAM policies configured according to mandatory requirements.")


if __name__ == "__main__":
    main()
