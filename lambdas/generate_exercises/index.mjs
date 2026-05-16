"use strict";

import { BedrockRuntimeClient, InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";

const REGION = process.env.AWS_REGION;
const TABLE_NAME = process.env.TABLE_NAME;
const MODEL_ID = process.env.MODEL_ID || "anthropic.claude-3-haiku-20240307-v1:0";

if (!REGION) throw new Error("Missing AWS_REGION");
if (!TABLE_NAME) throw new Error("Missing TABLE_NAME");

const bedrock = new BedrockRuntimeClient({ region: REGION });
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

function isoNow() {
  return new Date().toISOString();
}

function buildPrompt(text) {
  return `
You are an English teacher.

Based on the text below, generate:
1) 5 multiple choice questions (MCQ)
2) 5 fill-in-the-blank questions

STRICT RULES:
- Return ONLY valid JSON
- No markdown
- No explanation
- No text before or after JSON
- Use clear English suitable for learners

Return exactly in this format:
{
  "mcq": [
    {
      "question": "",
      "options": ["", "", "", ""],
      "answer": ""
    }
  ],
  "fillInTheBlank": [
    {
      "question": "",
      "answer": ""
    }
  ]
}

Text:
${text}
`;
}

function safeParseJSON(text) {
  try {
    return JSON.parse(text);
  } catch (err) {
    console.log("Direct JSON parse failed. Raw model text:", text);

    const match = text.match(/\{[\s\S]*\}/);
    if (match) {
      try {
        return JSON.parse(match[0]);
      } catch (innerErr) {
        console.log("Fallback JSON parse failed.");
      }
    }
    return null;
  }
}

export const handler = async (event) => {
  console.log("DynamoDB Stream Event:", JSON.stringify(event));

  const records = Array.isArray(event?.Records) ? event.Records : [];
  if (records.length === 0) {
    console.log("No records found.");
    return { ok: true };
  }

  for (const record of records) {
    try {
      if (record.eventName !== "INSERT" && record.eventName !== "MODIFY") {
        continue;
      }

      const newImage = record?.dynamodb?.NewImage;
      if (!newImage) {
        continue;
      }

      const status = newImage.status?.S;
      if (status !== "TEXTRACT_DONE") {
        continue;
      }

      const pk = newImage.PK?.S;
      const sk = newImage.SK?.S;
      const text = newImage.textractText?.S || "";

      if (!pk || !sk) {
        console.log("Missing PK or SK, skipping record.");
        continue;
      }

      if (!text.trim()) {
        console.log(`No textractText found for ${pk} / ${sk}, skipping.`);
        continue;
      }

      console.log(`Generating exercises for ${pk} / ${sk}`);

      const prompt = buildPrompt(text.slice(0, 8000));

      const command = new InvokeModelCommand({
        modelId: MODEL_ID,
        contentType: "application/json",
        accept: "application/json",
        body: JSON.stringify({
          anthropic_version: "bedrock-2023-05-31",
          max_tokens: 1200,
          temperature: 0.4,
          messages: [
            {
              role: "user",
              content: prompt
            }
          ]
        })
      });

      const response = await bedrock.send(command);
      const responseBody = JSON.parse(new TextDecoder().decode(response.body));
      const aiText = responseBody?.content?.[0]?.text || "";

      if (!aiText) {
        console.log(`Empty model response for ${pk} / ${sk}`);
        continue;
      }

      const exercises = safeParseJSON(aiText);
      if (!exercises) {
        console.log(`Failed to parse Bedrock JSON for ${pk} / ${sk}`);
        continue;
      }

      const mcq = Array.isArray(exercises.mcq) ? exercises.mcq : [];
      const fillInTheBlank = Array.isArray(exercises.fillInTheBlank)
        ? exercises.fillInTheBlank
        : [];

      await ddb.send(
        new UpdateCommand({
          TableName: TABLE_NAME,
          Key: {
            PK: pk,
            SK: sk
          },
          UpdateExpression: `
            SET #status = :s,
                #mcq = :m,
                #fill = :f,
                #updatedAt = :u
          `,
          ExpressionAttributeNames: {
            "#status": "status",
            "#mcq": "mcq",
            "#fill": "fillInTheBlank",
            "#updatedAt": "updatedAt"
          },
          ExpressionAttributeValues: {
            ":s": "EXERCISES_DONE",
            ":m": mcq,
            ":f": fillInTheBlank,
            ":u": isoNow()
          }
        })
      );

      console.log(`Exercises stored successfully for ${pk} / ${sk}`);
    } catch (error) {
      console.error("Lambda 3 record processing error:", error);
    }
  }

  return { ok: true };
};
