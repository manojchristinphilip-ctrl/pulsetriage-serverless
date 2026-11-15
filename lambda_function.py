import hashlib
import json
import os
import time
import boto3

bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

TABLE_NAME = os.environ["TABLE_NAME"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def lambda_handler(event, context):
    detail = event.get("detail", event)
    service_name = detail.get("service", "checkout-api")
    error_message = detail.get("error", "Unknown runtime error")
    stack_trace = detail.get("trace", "No stack trace provided")

    # 1. Deduplicate using SHA-256 hash in DynamoDB
    error_hash = hashlib.sha256(
        f"{service_name}:{error_message}".encode()
    ).hexdigest()[:16]
    table = dynamodb.Table(TABLE_NAME)
    existing = table.get_item(Key={"error_hash": error_hash}).get("Item")

    if existing:
        table.update_item(
            Key={"error_hash": error_hash},
            UpdateExpression="SET occurrences = occurrences + :inc, last_seen = :ts",
            ExpressionAttributeValues={":inc": 1, ":ts": int(time.time())},
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "deduplicated",
                "error_hash": error_hash,
                "count": int(existing["occurrences"]) + 1,
            }),
        }

    # 2. Diagnose root cause via Amazon Bedrock (Amazon Nova Lite)
    prompt = (
        "You are an AWS Site Reliability Engineer. Analyze this production error and "
        "return a concise diagnosis with: 1) Root Cause, 2) Immediate Fix, 3) Severity (P1-P3).\n\n"
        f"Service: {service_name}\nError: {error_message}\nTrace: {stack_trace}"
    )

    response = bedrock.converse(
        modelId="amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.2},
    )
    diagnosis = response["output"]["message"]["content"][0]["text"]

    # 3. Persist incident record to DynamoDB
    table.put_item(
        Item={
            "error_hash": error_hash,
            "service": service_name,
            "error_message": error_message,
            "diagnosis": diagnosis,
            "occurrences": 1,
            "last_seen": int(time.time()),
        }
    )

    # 4. Dispatch enriched alert via Amazon SNS
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"[AI Triage] New Incident in {service_name} ({error_hash})",
        Message=f"Service: {service_name}\nError: {error_message}\n\n--- AI Diagnosis ---\n{diagnosis}",
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "triaged_and_alerted",
            "error_hash": error_hash,
            "diagnosis": diagnosis,
        }),
    }
