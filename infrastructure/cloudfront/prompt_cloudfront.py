import boto3
import json
import time
from botocore.exceptions import ClientError

# =========================
# MANDATORY INPUTS (EDIT)
# =========================
REGION = "us-east-1"

WEBSITE_BUCKET = "vb-website-2025"
AWS_ACCOUNT_ID = "123456789012"  # TODO: ضع رقم حساب AWS بتاعك هنا (12 رقم)

# تعليق للتفريق بين الدستربيوشنز
DISTRIBUTION_COMMENT = "MVP CloudFront distribution for vb-website-2025 (OAC, HTTPS-only)"

# =========================
# VALIDATION
# =========================

def validate_inputs():
    if not REGION:
        raise ValueError("REGION is required")

    if not WEBSITE_BUCKET:
        raise ValueError("WEBSITE_BUCKET is required")

    if not AWS_ACCOUNT_ID or not AWS_ACCOUNT_ID.isdigit() or len(AWS_ACCOUNT_ID) != 12:
        raise ValueError("AWS_ACCOUNT_ID must be a 12-digit string")

    # CloudFront is global, but we validate S3 bucket region
    s3 = boto3.client("s3", region_name=REGION)
    try:
        resp = s3.get_bucket_location(Bucket=WEBSITE_BUCKET)
        loc = resp.get("LocationConstraint")
        # For us-east-1, LocationConstraint is None
        bucket_region = "us-east-1" if loc is None else loc
        if bucket_region != REGION:
            raise ValueError(
                f"S3 bucket {WEBSITE_BUCKET} is in region {bucket_region}, "
                f"but script is configured for {REGION}"
            )
    except ClientError as e:
        raise RuntimeError(f"Unable to validate bucket {WEBSITE_BUCKET}: {e}")


# =========================
# S3 BUCKET POLICY FOR OAC
# =========================

def apply_s3_bucket_policy_for_oac(distribution_id):
    """
    يجعل البكت private بالكامل ويسمح فقط لـ CloudFront distribution هذا يقرأ objects.
    نستخدم Condition على AWS:SourceArn لضبط أقل صلاحيات ممكنة.
    """
    s3 = boto3.client("s3", region_name=REGION)

    distribution_arn = f"arn:aws:cloudfront::{AWS_ACCOUNT_ID}:distribution/{distribution_id}"

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowCloudFrontServiceReadOnly",
                "Effect": "Allow",
                "Principal": {
                    "Service": "cloudfront.amazonaws.com"
                },
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{WEBSITE_BUCKET}/*",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceArn": distribution_arn
                    }
                }
            }
        ]
    }

    print(f"[INFO] Applying S3 bucket policy for CloudFront on bucket: {WEBSITE_BUCKET}")
    try:
        s3.put_bucket_policy(
            Bucket=WEBSITE_BUCKET,
            Policy=json.dumps(policy)
        )
        print("[OK] S3 bucket policy applied successfully.")
    except ClientError as e:
        print(f"[ERROR] Failed to apply bucket policy: {e}")
        raise


# =========================
# CLOUDFRONT HELPERS
# =========================

def create_origin_access_control(cloudfront):
    """
    ينشئ Origin Access Control (OAC) جديد للـ S3 origin.
    نستخدم SigV4 + always signing حسب best practices.
    """
    name = f"oac-{WEBSITE_BUCKET}-{int(time.time())}"
    print(f"[INFO] Creating Origin Access Control with name: {name}")

    try:
        resp = cloudfront.create_origin_access_control(
            OriginAccessControlConfig={
                "Name": name,
                "Description": f"OAC for S3 bucket {WEBSITE_BUCKET}",
                "SigningProtocol": "sigv4",
                "SigningBehavior": "always",
                "OriginAccessControlOriginType": "s3",
            }
        )
        oac_id = resp["OriginAccessControl"]["Id"]
        print(f"[OK] Created OAC with Id: {oac_id}")
        return oac_id
    except ClientError as e:
        print(f"[ERROR] Failed to create Origin Access Control: {e}")
        raise


def create_cloudfront_distribution_with_oac(oac_id):
    """
    ينشئ CloudFront distribution:
    - Origin = S3 bucket vb-website-2025
    - OAC = origin_access_control_id
    - HTTPS only (redirect HTTP -> HTTPS)
    - PriceClass_100
    - No logging, no WAF, no geo restrictions
    """
    cloudfront = boto3.client("cloudfront")

    caller_reference = f"vb-website-2025-{int(time.time())}"
    origin_id = "S3-vb-website-2025"

    # S3 regional endpoint (best practice)
    s3_domain_name = f"{WEBSITE_BUCKET}.s3.us-east-1.amazonaws.com"

    distribution_config = {
        "CallerReference": caller_reference,
        "Comment": DISTRIBUTION_COMMENT,
        "Enabled": True,
        "IsIPV6Enabled": True,
        "PriceClass": "PriceClass_100",  # low cost
        "DefaultRootObject": "index.html",
        "Aliases": {
            "Quantity": 0,
            "Items": []
        },
        "Origins": {
            "Quantity": 1,
            "Items": [
                {
                    "Id": origin_id,
                    "DomainName": s3_domain_name,
                    "OriginPath": "",
                    "OriginShield": {
                        "Enabled": False
                    },
                    "S3OriginConfig": {
                        # With OAC, OriginAccessIdentity must be empty
                        "OriginAccessIdentity": ""
                    },
                    "OriginAccessControlId": oac_id,
                }
            ]
        },
        "DefaultCacheBehavior": {
            "TargetOriginId": origin_id,
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"],
                "CachedMethods": {
                    "Quantity": 2,
                    "Items": ["GET", "HEAD"]
                }
            },
            # Legacy ForwardedValues is enough for MVP and simple static site
            "ForwardedValues": {
                "QueryString": False,
                "Cookies": {
                    "Forward": "none"
                },
                "Headers": {
                    "Quantity": 0,
                    "Items": []
                }
            },
            "Compress": True,  # Brotli/Gzip
            "MinTTL": 0,
            "DefaultTTL": 86400,      # 1 day
            "MaxTTL": 31536000        # 1 year
        },
        "CustomErrorResponses": {
            "Quantity": 0,
            "Items": []
        },
        "Logging": {
            "Enabled": False,
            "IncludeCookies": False,
            "Bucket": "",
            "Prefix": ""
        },
        "Restrictions": {
            "GeoRestriction": {
                "RestrictionType": "none",
                "Quantity": 0,
                "Items": []
            }
        },
        "ViewerCertificate": {
            # Default CloudFront certificate (*.cloudfront.net)
            "CloudFrontDefaultCertificate": True,
            "MinimumProtocolVersion": "TLSv1.2_2021"
        },
        "HttpVersion": "http2and3",  # HTTP/2 + HTTP/3
        "WebACLId": ""  # No WAF in MVP
    }

    print("[INFO] Creating CloudFront distribution...")
    try:
        resp = cloudfront.create_distribution(
            DistributionConfig=distribution_config
        )
        dist_id = resp["Distribution"]["Id"]
        dist_domain = resp["Distribution"]["DomainName"]
        print(f"[OK] Created CloudFront distribution: {dist_id}")
        print(f"[INFO] CloudFront Domain: https://{dist_domain}")
        return dist_id, dist_domain
    except ClientError as e:
        print(f"[ERROR] Failed to create CloudFront distribution: {e}")
        raise


# =========================
# MAIN
# =========================

def main():
    validate_inputs()

    # CloudFront is global service
    cloudfront = boto3.client("cloudfront")

    # 1) Create Origin Access Control
    oac_id = create_origin_access_control(cloudfront)

    # 2) Create CloudFront distribution with this OAC
    dist_id, dist_domain = create_cloudfront_distribution_with_oac(oac_id)

    # 3) Apply S3 bucket policy that allows only this distribution to read objects
    apply_s3_bucket_policy_for_oac(dist_id)

    print("\n============================")
    print("[DONE] MVP CloudFront setup completed.")
    print(f"Distribution ID     : {dist_id}")
    print(f"CloudFront Domain   : https://{dist_domain}")
    print(f"S3 Origin (private) : s3://{WEBSITE_BUCKET}")
    print("============================\n")


if __name__ == "__main__":
    main()