// SubmitTextractJob (Node.js 24.x)
// Trigger: S3 ObjectCreated:* with prefix raw/ and suffix .pdf
// Flow: StartDocumentTextDetection → SNS → Lambda 2

import {
  TextractClient,
  StartDocumentTextDetectionCommand
} from "@aws-sdk/client-textract";

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";

const REGION = process.env.AWS_REGION;
const TABLE_NAME = process.env.TABLE_NAME;

// SNS configuration
const SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:273144884300:vb-textract-complete-topic";
const SNS_ROLE_ARN = "arn:aws:iam::273144884300:role/vb-textract-sns-role";

const STRICT_KEY = (process.env.STRICT_KEY || "false").toLowerCase() === "true";

if (!REGION) throw new Error("Missing AWS_REGION");
if (!TABLE_NAME) throw new Error("Missing TABLE_NAME");

const textract = new TextractClient({ region: REGION });

const ddbDoc = DynamoDBDocumentClient.from(
  new DynamoDBClient({ region: REGION })
);

function decodeS3Key(key) {
  return decodeURIComponent(String(key).replace(/\+/g, " "));
}

function parseKeyOrThrow(s3Key) {

  const parts = s3Key.split("/").filter(Boolean);

  if (parts.length < 3) {
    throw new Error(`Invalid key format: ${s3Key}`);
  }

  const prefix = parts[0];
  const sub = parts[1];
  const fileName = parts[parts.length - 1];

  if (prefix !== "raw") throw new Error("Invalid prefix");
  if (!sub) throw new Error("Missing cognito-sub");
  if (!fileName.toLowerCase().endsWith(".pdf")) throw new Error("Not a PDF");

  if (STRICT_KEY && parts.length !== 3) {
    throw new Error("STRICT_KEY enabled but extra folders found");
  }

  const docId = fileName.slice(0, -4);
  if (!docId) throw new Error("Empty docId");

  return { sub, docId };
}

function isoNow() {
  return new Date().toISOString();
}

export const handler = async (event) => {

  const records = Array.isArray(event?.Records) ? event.Records : [];

  if (records.length === 0) {
    console.log("No records found in event");
    return { ok: true };
  }

  for (const rec of records) {

    const bucket = rec?.s3?.bucket?.name;
    const rawKey = rec?.s3?.object?.key;

    if (!bucket || !rawKey) {
      console.log("Skipping record with missing bucket or key");
      continue;
    }

    const s3Key = decodeS3Key(rawKey);

    if (!s3Key.startsWith("raw/") || !s3Key.toLowerCase().endsWith(".pdf")) {
      console.log(`Skipping non-PDF object: ${s3Key}`);
      continue;
    }

    const { sub, docId } = parseKeyOrThrow(s3Key);

    console.log(`Starting Textract job for: ${bucket}/${s3Key}`);

    const startResp = await textract.send(
      new StartDocumentTextDetectionCommand({

        DocumentLocation: {
          S3Object: {
            Bucket: bucket,
            Name: s3Key
          }
        },

        NotificationChannel: {
          SNSTopicArn: SNS_TOPIC_ARN,
          RoleArn: SNS_ROLE_ARN
        },

        JobTag: docId

      })
    );

    const jobId = startResp?.JobId;

    if (!jobId) {
      throw new Error("Textract did not return JobId");
    }

    console.log(`Textract JobId: ${jobId}`);

    const pk = `USER#${sub}`;
    const sk = `PDF#${docId}`;

    await ddbDoc.send(
      new UpdateCommand({
        TableName: TABLE_NAME,
        Key: { PK: pk, SK: sk },

        UpdateExpression:
          "SET #status=:s, #textractJobId=:j, #s3Key=:k, #updatedAt=:u",

        ConditionExpression:
          "attribute_not_exists(#status) OR #status = :err",

        ExpressionAttributeNames: {
          "#status": "status",
          "#textractJobId": "textractJobId",
          "#s3Key": "s3Key",
          "#updatedAt": "updatedAt"
        },

        ExpressionAttributeValues: {
          ":s": "TEXTRACT_SUBMITTED",
          ":j": jobId,
          ":k": s3Key,
          ":u": isoNow(),
          ":err": "ERROR"
        }
      })
    );

    console.log(`Textract job submitted successfully: ${jobId}`);
  }

  return { ok: true };
};