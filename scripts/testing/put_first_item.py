import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone

TABLE_NAME = "Vocabulary_Builder_2025"
REGION = "us-east-1"   # غيّرها لو جدولك في Region تاني

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

item = {
    "PK": "USER#001",
    "SK": "PROFILE#",
    "email": "user@email.com",
    "plan": "FREE",
    "monthlyLimit": 3,
    "createdAt": datetime.now(timezone.utc).isoformat()
}

try:
    resp = table.put_item(Item=item)
    print("✅ PutItem OK")
    print("HTTP:", resp["ResponseMetadata"]["HTTPStatusCode"])
    print("Region:", REGION)
    print("Table:", TABLE_NAME)
    print("Item Keys:", item["PK"], item["SK"])
except ClientError as e:
    print("❌ ClientError:", e.response["Error"]["Code"], e.response["Error"]["Message"])
