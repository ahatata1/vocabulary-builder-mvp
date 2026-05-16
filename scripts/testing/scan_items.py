import boto3

TABLE_NAME = "vocabulary_Builder_2025"
REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

response = table.scan()

items = response.get("Items", [])

if not items:
    print("❌ No items found in table")
else:
    print(f"✅ Found {len(items)} item(s):")
    for item in items:
        print(item)
