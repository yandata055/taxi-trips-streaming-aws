import os
import boto3
import base64
import json
import logging
import sys
from datetime import datetime
from decimal import Decimal
from awsglue.utils import getResolvedOptions

# ---------- Helpers ----------
def parse_decimal_json(payload: bytes) -> dict:
    """Parse JSON with Decimal support for DynamoDB."""
    return json.loads(payload, parse_float=Decimal, parse_int=Decimal)

def update_trip_details(data_item: dict, table: boto3.resource) -> bool:
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

    updated = "Attributes" in update_response and bool(update_response["Attributes"])
    if updated:
        logger.info(f"Updated trip_id {trip_id}: {update_response['Attributes']}")
    return updated

# ---------- Main ----------
def replay_failed_trips(sqs_url, table):
    while True:
        response = sqs.receive_message(
            QueueUrl=sqs_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5
        )
        messages = response.get('Messages', [])
        if not messages:
            logging.info("No more messages in DLQ.")
            break

        for msg in messages:
            body = json.loads(msg['Body'])
            record = body['record']
            try:
                # Reprocess logic here
                logger.info(f"Reprocessing trip_id={record.get('trip_id')}")
                if update_trip_details(record, table):
                    # Delete from SQS if replay was successful
                    sqs.delete_message(QueueUrl=sqs_url, ReceiptHandle=msg['ReceiptHandle'])
                    logger.info(f"Successfully deleted a message from DLQ: {msg['ReceiptHandle']}")
            except Exception as e:
                logger.error(f"Glue replay error: {e} | {datetime.utcnow().isoformat()}")

if __name__ == "__main__":

    # ---------- Configuration and logging----------
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    sqs = boto3.client('sqs')
    
    args = getResolvedOptions(sys.argv, ['sqs_url', 'source_table'])
    sql_url = args['sqs_url']
    table = args['source_table']

    replay_failed_trips(sqs_url, table)



