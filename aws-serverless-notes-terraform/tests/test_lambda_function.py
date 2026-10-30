"""Offline unit tests; no live AWS access."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault("TABLE_NAME", "test-notes")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))

import lambda_function as app  # noqa: E402


def event(method, path, body=None, note_id=None, query=None):
    payload = {"requestContext": {"http": {"method": method}}, "rawPath": path}
    if body is not None:
        payload["body"] = json.dumps(body) if not isinstance(body, str) else body
    if note_id:
        payload["pathParameters"] = {"noteId": note_id}
    if query:
        payload["queryStringParameters"] = query
    return payload


def call(payload):
    return app.lambda_handler(payload, None)


def body(response):
    return json.loads(response["body"]) if response["body"] else None


@pytest.fixture
def db(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(app, "table", fake)
    return fake


def test_health(db):
    actual = call(event("GET", "/health"))
    assert actual["statusCode"] == 200
    assert body(actual)["status"] == "ok"
    db.put_item.assert_not_called()


def test_create(db):
    actual = call(event("POST", "/notes", {"content": "  Hello!  "}))
    assert actual["statusCode"] == 201
    assert body(actual)["content"] == "Hello!"
    assert len(body(actual)["noteId"]) == 36
    assert db.put_item.call_args.kwargs["Item"]["content"] == "Hello!"


@pytest.mark.parametrize("content", ["", " ", None, 123, [], "x" * 1001])
def test_reject_invalid_content(db, content):
    actual = call(event("POST", "/notes", {"content": content}))
    assert actual["statusCode"] == 400
    db.put_item.assert_not_called()


def test_invalid_json(db):
    actual = call(event("POST", "/notes", "{not valid json"))
    assert actual["statusCode"] == 400
    db.put_item.assert_not_called()


def test_list_notes_with_pagination(db):
    db.scan.return_value = {"Items": [{"noteId": "n1", "content": "One"}], "LastEvaluatedKey": {"noteId": "n1"}}
    actual = call(event("GET", "/notes", query={"nextToken": "n0"}))
    assert actual["statusCode"] == 200
    assert body(actual)["nextToken"] == "n1"
    assert body(actual)["items"][0]["content"] == "One"
    db.scan.assert_called_once_with(Limit=25, ExclusiveStartKey={"noteId": "n0"})


def test_list_empty(db):
    db.scan.return_value = {"Items": []}
    assert body(call(event("GET", "/notes"))) == {"items": [], "nextToken": None}


def test_get_existing(db):
    db.get_item.return_value = {"Item": {"noteId": "n1", "content": "hello"}}
    actual = call(event("GET", "/notes/n1", note_id="n1"))
    assert actual["statusCode"] == 200
    assert body(actual)["content"] == "hello"


def test_get_missing(db):
    db.get_item.return_value = {}
    assert call(event("GET", "/notes/unknown", note_id="unknown"))["statusCode"] == 404


def test_update(db):
    db.update_item.return_value = {"Attributes": {"noteId": "n1", "content": "updated"}}
    actual = call(event("PUT", "/notes/n1", {"content": "updated"}, note_id="n1"))
    assert actual["statusCode"] == 200
    assert body(actual)["content"] == "updated"
    assert db.update_item.call_args.kwargs["ConditionExpression"] == "attribute_exists(noteId)"


def test_update_missing(db):
    db.update_item.side_effect = ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "missing"}}, "UpdateItem")
    assert call(event("PUT", "/notes/n1", {"content": "updated"}, note_id="n1"))["statusCode"] == 404


def test_delete(db):
    actual = call(event("DELETE", "/notes/n1", note_id="n1"))
    assert actual == {"statusCode": 204, "body": ""}
    db.delete_item.assert_called_once_with(Key={"noteId": "n1"}, ConditionExpression="attribute_exists(noteId)")


def test_unknown_route(db):
    assert call(event("PATCH", "/notes"))["statusCode"] == 404


def test_database_failure(db):
    db.scan.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "Scan")
    actual = call(event("GET", "/notes"))
    assert actual["statusCode"] == 500
    assert body(actual)["error"] == "Internal server error"
