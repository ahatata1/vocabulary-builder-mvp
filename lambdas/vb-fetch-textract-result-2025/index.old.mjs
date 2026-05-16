"use strict";

import {
  TextractClient,
  GetDocumentTextDetectionCommand
} from "@aws-sdk/client-textract";

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";

const REGION = process.env.AWS_REGION;
const TABLE_NAME = process.env.TABLE_NAME;

if (!REGION) throw new Error("Missing AWS_REGION");
if (!TABLE_NAME) throw new Error("Missing TABLE_NAME");

const textract = new TextractClient({ region: REGION });
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

function isoNow() {
  return new Date().toISOString();
}

function extractText(blocks = []) {
  return blocks
    .filter(b => b.BlockType === "LINE" && b.Text)
    .map(b => b.Text)
    .join("\n");
}

export const handler = async (event) => {

  console.log("SNS Event:", JSON.stringify(event));

  for (const record of event.Records) {

    const snsMessage = JSON.parse(record.Sns.Message);

    const jobId = snsMessage.JobId;
    const status = snsMessage.Status;
    const jobTag = snsMessage.JobTag;

    if (status !== "SUCCEEDED") {
      console.log("Textract job not successful:", status);
      continue;
    }

    const [sub, docId] = jobTag.split("|");

    console.log(`Fetching Textract result for ${sub} ${docId}`);

    let nextToken;
    const allBlocks = [];

    do {

      const resp = await textract.send(
        new GetDocumentTextDetectionCommand({
          JobId: jobId,
          NextToken: nextToken
        })
      );

      if (resp.Blocks) {
        allBlocks.push(...resp.Blocks);
      }

      nextToken = resp.NextToken;

    } while (nextToken);

    console.log("Blocks fetched:", allBlocks.length);

    const text = extractText(allBlocks);

    await ddb.send(
      new UpdateCommand({
        TableName: TABLE_NAME,
        Key: {
          PK: `USER#${sub}`,
          SK: `PDF#${docId}`
        },
        UpdateExpression:
          "SET #status = :s, #textractText = :t, #updatedAt = :u",
        ExpressionAttributeNames: {
          "#status": "status",
          "#textractText": "textractText",
          "#updatedAt": "updatedAt"
        },
        ExpressionAttributeValues: {
          ":s": "TEXTRACT_DONE",
          ":t": text,
          ":u": isoNow()
        }
      })
    );

    console.log("Text saved to DynamoDB");
  }

  return { ok: true };
};