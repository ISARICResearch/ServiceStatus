# -- IMPORTS --

# -- Standard libraries --
import json
import os
import typing
from datetime import datetime, timezone

# -- 3rd party libraries --
import boto3
import urllib.request
import urllib.error


ENDPOINTS = [
    {"name": "BRIDGE", "url": "https://bridge.isaric.org"},
    {"name": "VERTEX", "url": "https://vertex.isaric.org"},
    {"name": "LINK",   "url": "https://link.isaric.org"},
]

S3_BUCKET = os.environ.get("S3_BUCKET")
S3_KEY    = os.environ.get("S3_KEY")


def sanitise_error(msg: str) -> str:
    """Genericise any potentially sensitive internal details from error messages."""
    m = msg.lower()
    if "timeout" in m:
        return "timeout"
    if "ssl" in m or "certificate" in m:
        return "ssl error"
    if "connection" in m:
        return "connection error"
    if "http" in m:
        return "http error"
    return "unreachable"


def check_endpoint(name, url) -> dict[str, typing.Any]:
    """Check endpoint health by name and URL."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            ok = 200 <= status_code < 400
            return {
                "name":        name,
                "url":         url,
                "status":      "up" if ok else "degraded",
                "status_code": status_code,
                "error":       None,
            }
    except urllib.error.HTTPError as e:
        return {
            "name":        name,
            "url":         url,
            "status":      "degraded",
            "status_code": e.code,
            "error":       sanitise_error(str(e.reason)),
        }
    except Exception as e:
        return {
            "name":        name,
            "url":         url,
            "status":      "down",
            "status_code": None,
            "error":       sanitise_error(str(e)),
        }


def lambda_handler(event, context) -> dict[str, typing.Any]:
    """The Lambda handler - checks and appends each endpoint's health status to a JSON file that it then uploads to S3."""
    results = []
    for ep in ENDPOINTS:
        try:
            result = check_endpoint(ep["name"], ep["url"])
        except Exception:
            # Broad catch — one failing check must never prevent the S3 write
            result = {
                "name":        ep["name"],
                "url":         ep["url"],
                "status":      "down",
                "status_code": None,
                "error":       "unreachable",
            }
        results.append(result)

    for r in results:
        print(json.dumps(r))

    overall = "up"
    if any(r["status"] == "down"      for r in results): overall = "down"
    elif any(r["status"] == "degraded" for r in results): overall = "degraded"

    payload = {
        "status":     overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "services":   results,
    }

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket      = S3_BUCKET,
        Key         = S3_KEY,
        Body        = json.dumps(payload, indent=2),
        ContentType = "application/json",
        CacheControl= "no-cache, no-store, must-revalidate",
    )

    return {"statusCode": 200, "body": json.dumps(payload)}
