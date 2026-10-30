import json
import urllib.request
import urllib.error
import boto3
from datetime import datetime, timezone

ENDPOINTS = [
    {"name": "Bridge", "url": "https://bridge.isaric.org"},
    {"name": "Vertex", "url": "https://vertex.isaric.org"},
    {"name": "Link",   "url": "https://link.isaric.org"},
]

S3_BUCKET       = "isaric-status-891612573996-eu-west-2-an"
S3_KEY          = "status.json"
CF_DISTRIBUTION = "E2CCNNA94LH9KT"


def check_endpoint(name, url):
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
            "error":       str(e.reason),
        }
    except Exception as e:
        return {
            "name":        name,
            "url":         url,
            "status":      "down",
            "status_code": None,
            "error":       str(e),
        }


def lambda_handler(event, context):
    results = [check_endpoint(ep["name"], ep["url"]) for ep in ENDPOINTS]
    for r in results:
        print(json.dumps(r))

    overall = "up"
    if any(r["status"] == "down"     for r in results): overall = "down"
    elif any(r["status"] == "degraded" for r in results): overall = "degraded"

    payload = {
        "status":    overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "services":   results,
    }

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket       = S3_BUCKET,
        Key          = S3_KEY,
        Body         = json.dumps(payload, indent=2),
        ContentType  = "application/json",
        CacheControl = "no-cache, no-store, must-revalidate",
    )

    return {"statusCode": 200, "body": json.dumps(payload)}