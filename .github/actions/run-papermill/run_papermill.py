#!/usr/bin/env python3
import json
import os
import sys
import time
import requests

POLL_INTERVAL = int(os.environ.get("INPUT_POLL_INTERVAL", 10))
MAX_WAIT = int(os.environ.get("INPUT_MAX_WAIT", 3600))  # seconds

def parse_notebook_dirs(value):
    if not value:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    return [v.strip() for v in value.split(",") if v.strip()]


def main():
    repo = os.environ["INPUT_REPO"]
    ref = os.environ.get("INPUT_REF", "HEAD")
    api_url = os.environ["INPUT_API_URL"].rstrip("/")
    token = os.environ["INPUT_TOKEN"]
    notebook_dirs_raw = os.environ.get("INPUT_NOTEBOOK_DIRS", "")
    notebook_dirs = parse_notebook_dirs(notebook_dirs_raw)

    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Connection": "close",
    }

    payload = {
        "user_options": {
            "option": "repo2docker",
            "repo2docker": {
                "repotype": "gh",
                "repourl": repo,
                "reporef": ref,
            }
        }
    }
    
    if notebook_dirs:
        payload["notebook_dirs"] = notebook_dirs

    print(f"Triggering Papermill job for {repo}@{ref}")
    resp = requests.post(api_url, headers=headers, json=payload)
    resp.raise_for_status()

    job_url = resp.headers.get("Location")
    if not job_url:
        print("Missing Location header in response")
        sys.exit(1)

    print(f"Job URL: {job_url}")

    start = time.time()

    while True:
        if time.time() - start > MAX_WAIT:
            print("Timeout waiting for Papermill job")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)

        status_resp = requests.get(job_url, headers=headers, timeout=5)
        status_resp.raise_for_status()
        data = status_resp.json()

        status = data.get("status")
        print(f"Job status: {status}")

        if status == "stopped":
            break

    # ---- Job finished: analyze result ----
    exit_code = data.get("exit_code", 1)
    logs = data.get("logs", [])

    print("\n========== PAPERMILL LOGS ==========")
    for line in logs:
        print(line.replace("\\n", "\n").replace("\\u2588", "█"))
    print("===================================")

    if exit_code != 0:
        print(f"Papermill job failed (exit_code={exit_code})")
        sys.exit(exit_code)

    print("Papermill job completed successfully")
if __name__ == "__main__":
    main()
