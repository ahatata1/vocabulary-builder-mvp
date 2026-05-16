import boto3
from botocore.exceptions import ClientError, NoRegionError

try:
    dynamodb = boto3.client("dynamodb")  # أو حط region_name هنا
    dynamodb.create_table(
        TableName="Vocabulary_Builder_2025",
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"}
        ]
    )
    print("✅ Table created")
except ClientError as e:
    print("❌ AWS ClientError:", e.response["Error"]["Code"], "-", e.response["Error"]["Message"])
except NoRegionError:
    print("❌ NoRegionError: لازم تحدد region أو تعمل aws configure")
