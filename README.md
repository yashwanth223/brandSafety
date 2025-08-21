# Content Fetch → S3 (AWS Lambda + API Gateway)

This Lambda takes a webpage URL, downloads the page, extracts a readable **title + text**, and saves a **JSON** file to **Amazon S3**. You call it through an **API Gateway** URL like:


## How it works (plain English)
1. You hit the API with `?url=...`.
2. API Gateway invokes the Lambda.
3. Lambda fetches the page, strips scripts/styles, keeps readable text + title.
4. It saves JSON to S3 at: `YYYY-MM-DD/<host>/<title-slug>-<random>.json`.
5. The API response tells you the `s3://...` path.

## Folder contents (minimal)
- `lambda_function.py` — the Lambda code.
- `README.md` — this file.
- `.gitignore` — keeps junk files out of Git.

## Deploy (Console‑only, no packaging)
1. **S3 bucket**: Create a bucket (e.g., `my-content-bucket-123`). Keep public access blocked.
2. **Lambda**: Create a function (Python 3.11). Paste `lambda_function.py` in the inline editor and **Deploy**.
3. **Env var**: In Lambda → Configuration → Environment variables, add:
   - `CONTENT_BUCKET = <your-bucket-name>`
4. **IAM permission**: On the Lambda **execution role**, add inline policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:PutObject"],
         "Resource": "arn:aws:s3:::<your-bucket-name>/*"
       }
     ]
   }

https://<api-id>.execute-api.<region>.amazonaws.com/default/content-fetch-to-s3?url=https%3A%2F%2Fexample.com

curl "https://<api-id>.execute-api.<region>.amazonaws.com/default/content-fetch-to-s3?url=https%3A%2F%2Fexample.com"

curl -X POST -H "Content-Type: application/json" \
  "https://<api-id>.execute-api.<region>.amazonaws.com/default/content-fetch-to-s3" \
  -d '{"url":"https://site/article?id=123&lang=en"}'

{
  "meta": {
    "source_url": "https://example.com",
    "title": "Example Domain",
    "fetched_at": "2025-08-19T20:50:00Z",
    "content_length": 1256
  },
  "content": {
    "text": "Readable page text...",
    "length": 201
  }
}
