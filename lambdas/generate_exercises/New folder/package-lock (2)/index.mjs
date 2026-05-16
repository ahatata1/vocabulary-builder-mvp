"use strict";

import { BedrockRuntimeClient, InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";

const REGION = process.env.AWS_REGION;
const TABLE_NAME = process.env.TABLE_NAME;

if (!REGION) throw new Error("Missing AWS_REGION");
if (!TABLE_NAME) throw new Error("Missing TABLE_NAME");

const bedrock = new BedrockRuntimeClient({ region: REGION });
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

const MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0";

function buildPrompt(text, keyPhrases) {
  return `
You are an English teacher.

Based on the following text and vocabulary,
generate:

1) 5 multiple choice questions (MCQ)
2) 5 fill-in-the-blank questions

Return ONLY valid JSON in this format:

{
  "mcq": [
    {
      "question": "",
      "options": ["A", "B", "C", "D"],
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

Vocabulary:
${keyPhrases.join(", ")}
`;
}

export const handler = async (event) => {
  for (const record of event.Records) {

    // ✅ Modified condition هنا
    if (record.eventName !== "INSERT" && record.eventName !== "MODIFY") {
      continue;
    }

    const newImage = record.dynamodb.NewImage;
    if (!newImage) continue;

    const status = newImage.status?.S;
    if (status !== "COMPREHEND_DONE") continue;

    const sub = newImage.PK.S.replace("USER#", "");
    const docId = newImage.SK.S.replace("PDF#", "");

    const text = newImage.textractText?.S || "";
    const keyPhrases = newImage.keyPhrases?.L?.map(x => x.S) || [];

    console.log(`Generating exercises for ${sub} - ${docId}`);

    const prompt = buildPrompt(text.slice(0, 8000), keyPhrases);

    const command = new InvokeModelCommand({
      modelId: MODEL_ID,
      contentType: "application/json",
      accept: "application/json",
      body: JSON.stringify({
        anthropic_version: "bedrock-2023-05-31",
        max_tokens: 2000,
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

    const aiText = responseBody.content[0].text;
    const exercises = JSON.parse(aiText);

    await ddb.send(
      new UpdateCommand({
        TableName: TABLE_NAME,
        Key: {
          PK: `USER#${sub}`,
          SK: `PDF#${docId}`
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
          ":m": exercises.mcq,
          ":f": exercises.fillInTheBlank,
          ":u": new Date().toISOString()
        }
      })
    );

    console.log("Exercises stored successfully.");
  }

  return { ok: true };
};