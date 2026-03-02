import os
import boto3
import json
import base64
import logging
from decimal import Decimal

# ----- Configuration and logging -----
logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.getenv("DDB_TABLE_NAME")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
# ----- DynamoDB (resource API) -----
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
sns = boto3.client("sns", region_name="us-east-1")
table = dynamodb.Table(TABLE_NAME)

def _load_json_with_decimals(payload_bytes: bytes) -> dict:
    # Ensure numbers are Decimal (not float) so DynamoDB stores them as Number
    return json.loads(payload_bytes, parse_float=Decimal, parse_int=Decimal)

def send_error_notification(error_message: str, record_data: dict = None):
    """Send error details to SNS for alerting."""
    try:
        message = {
            "error": error_message,
            "record": record_data
        }
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="Kinesis Processing Error",
            Message=json.dumps(message, default=str)
        )
        logger.info("Error message sent to SNS.")
    except Exception as sns_error:
        logger.error(f"Failed to create trip records: {sns_error}")

def process_record(record) -> bool:
    """Process a single Kinesis record and write it to DynamoDB (resource API)."""
    try:
        payload = base64.b64decode(record["kinesis"]["data"])
        item = _load_json_with_decimals(payload)

        # Optional: basic validation to ensure your PK exists and is a string
        if "trip_id" not in item or not isinstance(item["trip_id"], str):
            raise ValueError("Item missing string partition key 'trip_id'.")

        table.put_item(Item=item)
        logger.info(f"Wrote trip_id={item['trip_id']}")
        return True
    except Exception as e:
        error_msg = f"Start trip error: {e}"
        logger.error(error_msg)
        send_error_notification(error_msg, record)
        return False

def lambda_handler(event, context):
    success = 0
    errors = 0
    sns_triggered = False

    records = event.get("Records", [])
    # Simple per-record puts (fine for modest batch sizes)
    for r in records:
        if process_record(r):
            success += 1
        else:
            errors += 1

    if errors > 0:
        sns_triggered = True
    
    # Use batch_writer() if each record is an independent item:
    # with table.batch_writer() as batch:
    #     for r in records:
    #         try:
    #             payload = base64.b64decode(r["kinesis"]["data"])
    #             item = _load_json_with_decimals(payload)
    #             if "trip_id" not in item or not isinstance(item["trip_id"], str):
    #                 raise ValueError("Item missing string partition key 'trip_id'.")
    #             batch.put_item(Item=item)
    #             success += 1
    #         except Exception as e:
    #             error_msg = f"Start trip error: {e}"
    #             logger.error(error_msg)
    #             send_error_notification(error_msg, r)
    #             errors += 1
      
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Created {success} trips with {errors} errors.",
            "sns_triggered": sns_triggered,
        })
    }
