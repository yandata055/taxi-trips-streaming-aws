---
noteId: "3fdf23a015dd11f19f2a71ba5d01594e"
tags: []

---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands
### Environment Setup

Always use `uv` — never `pip` directly.

```bash
# Install uv package manager (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Add new dependencies
uv add <package>
```

## Running Scripts

```bash
# Run the producer
uv run python producer/taxi_trip_kinesis_stream.py
```
Python version is pinned to 3.10 (`.python-version`). Dependencies are in `pyproject.toml` (boto3, pyarrow).

## Architecture

Real-time AWS streaming pipeline for SF taxi trip events with fault-tolerant failure recovery.

```
Parquet files
     │
     ▼
Producer (producer/taxi_trip_kinesis_stream.py)
     │                          │
     ▼                          ▼
start-trip-stream          end-trip-stream
(Kinesis)                  (Kinesis)
     │                          │
     ▼                          ▼
start-taxi-trips           end-taxi-trips
(Lambda)                   (Lambda)
     │                          │
     ├─→ DynamoDB put_item       ├─→ DynamoDB update_item
     └─→ SNS (invalid records)   ├─→ SQS (failed updates → DLQ)
                                 └─→ triggers Glue job (on errors)
                                           │
                                           ▼
                                  Glue: replay SQS → DynamoDB
```

**DynamoDB table** `taxi_trip_details`: partition key `trip_id` (String), PAY_PER_REQUEST billing.

**Data flow detail:**
1. Producer reads `data/start_taxi_trips.parquet` and `data/end_taxi_trips.parquet`, converts rows to JSON, sends in batches of 500 to Kinesis (with one retry on partial failure). Start and end batches are interleaved with sleep delays.
2. Start Lambda (`streaming/start_taxi_trips_lambda.py`): decodes Kinesis records, does `put_item` to DynamoDB. Invalid records (missing `trip_id`) trigger an SNS notification. Env vars: `DDB_TABLE_NAME`, `SNS_TOPIC_ARN`.
3. End Lambda (`streaming/end_taxi_trips_lambda.py`): decodes records, checks trip exists via `get_item`, then does `update_item` with safe expression attribute names. Failed records go to SQS DLQ; if any errors in the batch, triggers the Glue job once (skips if already running). Env vars: `DDB_TABLE_NAME`, `SQS_URL`, `GLUE_JOB_NAME`.
4. Glue job (`recovering/taxi_trip_glue_replay.py`): polls SQS in a loop (10 messages at a time, long-poll 5s), replays each failed record into DynamoDB, deletes the SQS message on success. Uses `awsglue.utils.getResolvedOptions` for args (`sqs_url`, `source_table`).

**Key implementation details:**
- All JSON is parsed with `parse_float=Decimal, parse_int=Decimal` everywhere numbers touch DynamoDB (DynamoDB rejects Python floats).
- End Lambda skips orphaned end events (trip not found in DynamoDB) rather than erroring.
- Kinesis event source mappings use batch size 5, `LATEST` starting position.

## Infrastructure

`infra/aws_source_sample.yaml` is a CloudFormation/SAM template with placeholder values (`XXX`, `ACCOUNT_ID_REPLACED`, `placeholder@example.com`). Replace these before deploying. IAM policy ARNs are also incomplete stubs.

AWS resources defined: S3 bucket, 2 Kinesis streams (`start-trip-stream`, `end-trip-stream`), DynamoDB table, SQS queue (`failed-updated-trips`), SNS topic (`Invalid-taxi-trips`), 2 Lambda functions, 2 Kinesis event source mappings, IAM role.

## Data Files

The producer expects:
- `data/start_taxi_trips.parquet` — trip start events
- `data/end_taxi_trips.parquet` — trip end events

Sample/archived versions live in `data/previous/` (gitignored).
