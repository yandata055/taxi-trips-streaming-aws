import os
import boto3
import base64
import json
import logging
from datetime import datetime
from decimal import Decimal

# ---------- Configuration and logging----------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.getenv("DDB_TABLE_NAME")
GLUE_JOB_NAME = os.getenv("GLUE_JOB_NAME")
SQS_URL  = os.getenv("SQS_URL")
# ---------- Clients Initialized Once ----------
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table(TABLE_NAME)
sqs = boto3.client("sqs")
glue = boto3.client("glue", region_name="us-east-1")

# ---------- Helpers ----------
def parse_decimal_json(payload: bytes) -> dict:
    """Parse JSON with Decimal support for DynamoDB."""
    return json.loads(payload, parse_float=Decimal, parse_int=Decimal)

def update_trip_details(data_item: dict) -> bool:
    """Update trip details in DynamoDB and return True if successful."""
    if "trip_id" not in data_item:
        logger.warning("Skipping record without trip_id.")
        return False

    trip_id = data_item["trip_id"]

    # Check existence
    response = table.get_item(Key={"trip_id": trip_id})
    if "Item" not in response:
        logger.info(f"Skipping trip_id {trip_id}: not found in table.")
        return False

    # Build safe update expression
    update_fields = {k: v for k, v in data_item.items() if k != "trip_id"}
    if not update_fields:
        logger.info(f"No updatable fields for trip_id {trip_id}.")
        return False

    expression_attribute_names = {f"#{k}": k for k in update_fields}
    expression_attribute_values = {f":{k}": v for k, v in update_fields.items()}
    update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in update_fields])
    print(update_expression)

    update_response = table.update_item(
        Key={"trip_id": trip_id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="UPDATED_NEW",
    )

    return "Attributes" in update_response and bool(update_response["Attributes"])

def lambda_handler(event, context):
    """Triggered by Kinesis; updates trip records and optionally runs Glue job."""
    success = 0
    errors = 0

    for record in event.get("Records", []):
        try:
            payload = base64.b64decode(record["kinesis"]["data"])
            data = parse_decimal_json(payload)

            if update_trip_details(data):
                success += 1
            else:
                raise ValueError ("Failed to update trip details. Missing required attributes!")    
        except Exception as e:
            logger.error(f"End trip error: {e} | {datetime.utcnow().isoformat()}")
            sqs.send_message(
                QueueUrl=SQS_URL,
                MessageBody=json.dumps({
                    "error": str(e),
                    "record": record,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
            errors += 1
            logger.info("Sent failed record to SQS DLQ.")
    
    glue_triggered = False

    # Trigger Glue job once per batch if has failed updates
    if errors > 0:
        try:
            args = {
                "--sqs_url": SQS_URL,
                "--source_table": TABLE_NAME,      
            }
            # Passing args to the Glue Job
            glue_response = glue.start_job_run(JobName=GLUE_JOB_NAME, Arguments=args)
            glue_triggered = True
            logger.info(f"Triggered Glue job {GLUE_JOB_NAME} ({glue_response['JobRunId']}).")
        except glue.exceptions.ConcurrentRunsExceededException:
            logger.warning(f"Glue job {GLUE_JOB_NAME} already running; skipping trigger.")
            
    logger.info(
        f"{'triggered' if glue_triggered else 'did not trigger'} Glue job."
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Updated {success} trips with {errors} errors.",
            "glue_triggered": glue_triggered,
        })
    }
