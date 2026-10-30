"""Serverless Notes API handler for API Gateway HTTP API (payload version 2.0)."""

import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "Notes"))
MAX_CONTENT_LENGTH = 1000
PAGE_SIZE = 25


def response(status_code, data=None):
    if status_code == 204:
        return {"statusCode": 204, "body": ""}
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data if data is not None else {}),
    }


def parse_body(event):
    raw = event.get("body")
    if not raw:
        raise ValueError("Request body must contain JSON")
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def validate_content(payload):
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    content = content.strip()
    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(f"content cannot exceed {MAX_CONTENT_LENGTH} characters")
    return content


def lambda_handler(event, context):
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "").rstrip("/") or "/"
    note_id = (event.get("pathParameters") or {}).get("noteId")
    logger.info("Request method=%s path=%s", method, path)

    try:
        if method == "GET" and path == "/health":
            return response(200, {"status": "ok", "service": "notes-api"})

        if method == "POST" and path == "/notes":
            content = validate_content(parse_body(event))
            note = {"noteId": str(uuid.uuid4()), "content": content}
            table.put_item(Item=note, ConditionExpression="attribute_not_exists(noteId)")
            logger.info("Created note id=%s", note["noteId"])
            return response(201, note)

        if method == "GET" and path == "/notes":
            query = event.get("queryStringParameters") or {}
            next_token = query.get("nextToken")
            arguments = {"Limit": PAGE_SIZE}
            if next_token:
                arguments["ExclusiveStartKey"] = {"noteId": next_token}
            result = table.scan(**arguments)
            items = result.get("Items", [])
            last_key = result.get("LastEvaluatedKey")
            logger.info("Listed %d notes", len(items))
            return response(200, {
                "items": items,
                "nextToken": last_key.get("noteId") if last_key else None,
            })

        if method == "GET" and note_id:
            item = table.get_item(Key={"noteId": note_id}).get("Item")
            if item is None:
                return response(404, {"error": "Note not found"})
            return response(200, item)

        if method == "PUT" and note_id:
            content = validate_content(parse_body(event))
            result = table.update_item(
                Key={"noteId": note_id},
                UpdateExpression="SET content = :content",
                ExpressionAttributeValues={":content": content},
                ConditionExpression="attribute_exists(noteId)",
                ReturnValues="ALL_NEW",
            )
            logger.info("Updated note id=%s", note_id)
            return response(200, result["Attributes"])

        if method == "DELETE" and note_id:
            table.delete_item(
                Key={"noteId": note_id},
                ConditionExpression="attribute_exists(noteId)",
            )
            logger.info("Deleted note id=%s", note_id)
            return response(204)

        return response(404, {"error": "Route not found"})

    except ValueError as exc:
        return response(400, {"error": str(exc)})
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ConditionalCheckFailedException":
            return response(404, {"error": "Note not found"})
        logger.exception("DynamoDB request failed")
        return response(500, {"error": "Internal server error"})
    except Exception:
        logger.exception("Unhandled request error")
        return response(500, {"error": "Internal server error"})
