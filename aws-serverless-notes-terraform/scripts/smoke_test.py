"""End-to-end smoke test against the deployed API. Deletes its own sample note."""
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(url, method="GET", body=None):
    payload = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=payload, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=20) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else None
    except HTTPError as err:
        print(f"{method} {url} failed: HTTP {err.code}: {err.read().decode()}")
        raise


def main():
    if len(sys.argv) != 2:
        print('Usage: python scripts/smoke_test.py "https://your-api-id.execute-api.eu-west-2.amazonaws.com"')
        raise SystemExit(2)
    base = sys.argv[1].rstrip("/")
    status, health = call(f"{base}/health")
    assert status == 200 and health["status"] == "ok", health
    print("PASS health")

    note_id = None
    try:
        status, note = call(f"{base}/notes", "POST", {"content": "Terraform smoke test"})
        assert status == 201 and note["noteId"]
        note_id = note["noteId"]
        print("PASS create")

        status, fetched = call(f"{base}/notes/{note_id}")
        assert status == 200 and fetched["content"] == "Terraform smoke test"
        print("PASS get")

        status, listing = call(f"{base}/notes")
        assert status == 200 and isinstance(listing["items"], list)
        print("PASS list")

        status, changed = call(f"{base}/notes/{note_id}", "PUT", {"content": "Updated by smoke test"})
        assert status == 200 and changed["content"] == "Updated by smoke test"
        print("PASS update")
    finally:
        if note_id:
            status, _ = call(f"{base}/notes/{note_id}", "DELETE")
            assert status == 204
            print("PASS delete / cleanup")
    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
