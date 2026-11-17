# Vocabulary Builder MVP
## Phase 3 - Architecture & Workflow Report
### AI Exercise Generation Layer - No Troubleshooting

## 1. Phase 3 Overview

Phase 3 introduces the AI exercise-generation layer of the Vocabulary Builder MVP. Phase 2 finishes when Amazon Textract has processed the uploaded PDF and the extracted text is stored in DynamoDB with status `TEXTRACT_DONE`. Phase 3 begins from this state and transforms the extracted educational content into structured exercises using Amazon Bedrock.

```text
Extracted Text
      ↓
AI Processing
      ↓
Structured Exercises
      ↓
DynamoDB
```

The generated learning content consists of 5 Multiple Choice Questions (MCQ) and 5 Fill-in-the-Blank questions.

## 2. Phase 3 Architecture

```text
Amazon DynamoDB - Vocabulary_Builder_2025
        │
        │ status = TEXTRACT_DONE
        ▼
DynamoDB Stream
        ▼
Lambda 3 - generate-exercises
        ▼
Amazon Bedrock - Claude Haiku 4.5
        ▼
Structured JSON Response
        ▼
Lambda 3
        ▼
Amazon DynamoDB
        │
        └─ status = EXERCISES_DONE
           mcq = [...]
           fillInTheBlank = [...]
```

The design extends the event-driven architecture established in Phase 2. No manual action is required to start exercise generation once a document reaches `TEXTRACT_DONE`.

## 3. AWS Services Used

### Amazon DynamoDB

DynamoDB acts as both the document data store and workflow state store. The table is `Vocabulary_Builder_2025`.

```text
PK = USER#<sub>
SK = PDF#<docId>
```

At the beginning of Phase 3, the document item contains:

```text
PK
SK
status = TEXTRACT_DONE
textractText
updatedAt
```

At the end of Phase 3, the same item additionally contains:

```text
status = EXERCISES_DONE
mcq
fillInTheBlank
updatedAt
```

### DynamoDB Streams

DynamoDB Streams provides the event mechanism connecting Phase 2 to Phase 3. The stream captures New and Old Images. When Lambda 2 updates the document status to `TEXTRACT_DONE`, the resulting stream event invokes Lambda 3.

### AWS Lambda 3 - generate-exercises

Lambda 3 orchestrates the Phase 3 transformation:

```text
Receive DynamoDB Stream event
        ↓
Inspect NewImage
        ↓
Check document status
        ↓
Read textractText
        ↓
Build AI prompt
        ↓
Call Amazon Bedrock
        ↓
Parse AI response
        ↓
Update DynamoDB
```

Lambda 3 processes only records where `status = TEXTRACT_DONE`. Other stream events are ignored.

## 4. Amazon Bedrock Integration

Amazon Bedrock provides the generative-AI capability for Phase 3. The project uses Claude Haiku 4.5 through the Amazon Bedrock Runtime Converse API. Lambda authenticates to Bedrock through its AWS IAM execution role, so no application-level API key is required for this service-to-service interaction.

```text
Lambda 3
   ↓
Converse API
   ↓
Amazon Bedrock
   ↓
Claude Haiku 4.5
```

## 5. AI Input Processing

The source of the AI input is `textractText`, stored in DynamoDB during Phase 2. Phase 3 does not require Amazon Comprehend or `keyPhrases`. The extracted text is sent directly to Bedrock.

```text
PDF
 ↓
Textract
 ↓
textractText
 ↓
Bedrock
```

Before sending the document text to Bedrock, Lambda limits the input using:

```javascript
text.slice(0, 8000)
```

## 6. Prompt and Exercise Generation

Lambda 3 constructs an instructional prompt around the extracted document text. Bedrock is asked to return exactly two exercise types in structured JSON.

### Multiple Choice Questions

Exactly 5 MCQs are generated. Each contains a question, four answer options, and the correct answer.

```json
{
  "question": "",
  "options": ["", "", "", ""],
  "answer": ""
}
```

### Fill-in-the-Blank Questions

Exactly 5 Fill-in-the-Blank questions are generated.

```json
{
  "question": "",
  "answer": ""
}
```

## 7. Bedrock Response Processing

Claude Haiku 4.5 returns structured educational content to Lambda 3. Lambda parses the response into the `mcq` and `fillInTheBlank` arrays and prepares them for storage.

```json
{
  "mcq": [
    {"question": "...", "options": ["...", "...", "...", "..."], "answer": "..."}
  ],
  "fillInTheBlank": [
    {"question": "...", "answer": "..."}
  ]
}
```

## 8. DynamoDB Update

After successful exercise generation, Lambda 3 updates the original document item. The workflow state changes from `TEXTRACT_DONE` to `EXERCISES_DONE`, and the generated exercise arrays are stored with an updated timestamp.

```text
PK = USER#<sub>
SK = PDF#<docId>

status = EXERCISES_DONE
textractText = ...
mcq = [...]
fillInTheBlank = [...]
updatedAt = ...
```

## 9. Phase 3 State Transition

```text
TEXTRACT_DONE
      ↓
Generate Exercises
      ↓
EXERCISES_DONE
```

Combined with Phase 2, the document lifecycle is:

```text
TEXTRACT_SUBMITTED
        ↓
TEXTRACT_DONE
        ↓
EXERCISES_DONE
```

## 10. Event-Driven Workflow

1. Lambda 2 finishes Textract processing.
2. DynamoDB is updated with `status = TEXTRACT_DONE` and `textractText`.
3. DynamoDB Stream detects the MODIFY event.
4. The stream invokes Lambda 3.
5. Lambda 3 reads NewImage and verifies `status == TEXTRACT_DONE`.
6. Lambda 3 reads `textractText` and builds the exercise-generation prompt.
7. Lambda sends the request to Amazon Bedrock through the Converse API.
8. Claude Haiku 4.5 generates 5 MCQs and 5 Fill-in-the-Blank questions.
9. Lambda parses the structured response.
10. Lambda updates DynamoDB with `status = EXERCISES_DONE`, `mcq`, `fillInTheBlank`, and `updatedAt`.

## 11. Separation of Responsibilities

| Component | Responsibility |
|---|---|
| DynamoDB | Store document state, extracted text, and exercises |
| DynamoDB Streams | Detect the Phase 2 to Phase 3 state transition |
| Lambda 3 | Orchestrate exercise generation |
| Amazon Bedrock | Provide the managed generative-AI runtime |
| Claude Haiku 4.5 | Generate structured MCQ and Fill-in-the-Blank exercises |

## 12. Boundary Between Phase 2 and Phase 3

```text
PHASE 2
PDF → S3 → Lambda 1 → Textract → SNS → Lambda 2 → DynamoDB
status = TEXTRACT_DONE
textractText = ...

                    ↓

PHASE 3
DynamoDB Stream → Lambda 3 → Bedrock → Claude Haiku 4.5 → DynamoDB
status = EXERCISES_DONE
mcq = [...]
fillInTheBlank = [...]
```

Phase 2 converts the PDF into usable text, while Phase 3 converts that text into structured educational content.

## Phase 3 Result

At the end of Phase 3, the Vocabulary Builder has progressed from document processing into AI-powered educational-content generation. The student's document record contains the extracted text, five generated MCQs, five Fill-in-the-Blank exercises, and the `EXERCISES_DONE` workflow state, ready for the subsequent student-facing application layer.
