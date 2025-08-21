import json, re, uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser
import os
import boto3

# Read this from Lambda environment variables (Configuration > Environment variables)
BUCKET = os.getenv("CONTENT_BUCKET", "")

# --- Simple HTML text extractor (no external libs) ---
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_script = False
        self._in_style = False
        self._in_noscript = False
        self._in_title = False
        self.title = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "script": self._in_script = True
        elif t == "style": self._in_style = True
        elif t == "noscript": self._in_noscript = True
        elif t == "title": self._in_title = True

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "script": self._in_script = False
        elif t == "style": self._in_style = False
        elif t == "noscript": self._in_noscript = False
        elif t == "title": self._in_title = False

    def handle_data(self, data):
        if self._in_script or self._in_style or self._in_noscript:
            return
        if self._in_title:
            text = data.strip()
            if text:
                # keep first non-empty title we see
                if self.title is None:
                    self.title = text
            return
        if data and data.strip():
            self.parts.append(data.strip())

    def get_text(self):
        text = "\n".join(self.parts)
        # collapse too many newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

def _slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"\s+", "-", (text or "").strip().lower())
    text = re.sub(r"[^a-z0-9\-]+", "", text)
    return (text[:max_len].strip("-")) or "page"

def fetch_url(url: str, timeout_sec: int = 20) -> str:
    req = Request(
        url,
        headers={"User-Agent": "LambdaContentFetcher/1.0 (+https://aws.amazon.com/lambda/)"}
    )
    with urlopen(req, timeout=timeout_sec) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read()
        return body.decode(charset, errors="replace")

def extract_text_and_title(html: str):
    parser = TextExtractor()
    parser.feed(html)
    return parser.title, parser.get_text()

def save_json_to_s3(bucket: str, key: str, record: dict):
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(record, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"

def lambda_handler(event, context):
    # 1) Validate bucket config
    if not BUCKET:
        return {"statusCode": 500, "body": "Please set CONTENT_BUCKET environment variable."}

    # 2) Get URL from event
    url = None
    if isinstance(event, dict):
        url = event.get("url")
        if not url:
            qs = event.get("queryStringParameters") or {}
            url = qs.get("url")
    if not url:
        return {"statusCode": 400, "body": "Provide 'url' in the event or as query parameter."}

    # 3) Fetch and parse
    try:
        html = fetch_url(url,30)
    except HTTPError as e:
        return {"statusCode": e.code, "body": f"HTTPError fetching URL: {e}"}
    except URLError as e:
        return {"statusCode": 502, "body": f"URLError fetching URL: {e}"}
    except Exception as e:
        return {"statusCode": 500, "body": f"Unexpected error: {e}"}

    title, text = extract_text_and_title(html)

    # 4) Build S3 key
    host = urlparse(url).netloc.replace("www.", "")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = _slugify(title or "page")
    key = f"{date}/{host}/{base}-{uuid.uuid4().hex[:8]}.json"

    # 5) Create record and save to S3
    record = {
        "meta": {
            "source_url": url,
            "title": title,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "content_length": len(html),
        },
        "content": {
            "text": text,
            "length": len(text),
        }
    }

    uri = save_json_to_s3(BUCKET, key, record)

    return {
        "statusCode": 200,
        "body": json.dumps({"saved_to": uri, "title": title})
    }
