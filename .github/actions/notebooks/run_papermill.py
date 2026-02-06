#!/usr/bin/env python3
import json
import os
import sys
import time

import requests

POLL_INTERVAL = int(os.environ.get("INPUT_POLL_INTERVAL", 10))
MAX_WAIT = int(os.environ.get("INPUT_MAX_WAIT", 3600))  # seconds


def parse_logs_as_json(logs):
    """
    Try to reconstruct logs into a JSON object.
    Returns (parsed_json, raw_text)
    """
    raw_text = "\n".join(logs)

    try:
        parsed = json.loads(raw_text)
        return parsed, raw_text
    except json.JSONDecodeError:
        return None, raw_text


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
            },
        }
    }

    if notebook_dirs:
        payload["notebook_dirs"] = notebook_dirs

    print(f"Triggering Papermill job for {repo}@{ref}")
    for i in range(5):
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            break
        except Exception as e:
            print(f"Error triggering Papermill job: {e}")
            if i == 4:
                print(
                    "Failed to trigger Papermill job after multiple attempts, aborting"
                )
                sys.exit(1)
            time.sleep(60)

    job_url = resp.headers.get("Location")
    if not job_url:
        print("Missing Location header in response")
        sys.exit(1)

    print(f"Job URL: {job_url}")

    start = time.time()
    fail_counter = 0
    while True:
        if time.time() - start > MAX_WAIT:
            print("Timeout waiting for Papermill job")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)

        try:
            status_resp = requests.get(job_url, headers=headers, timeout=10)
            status_resp.raise_for_status()
        except Exception as e:
            print(f"Error fetching job status: {e}")
            fail_counter += 1
            if fail_counter >= 5:
                print("Too many consecutive failures fetching job status, aborting")
                sys.exit(1)
            continue
        else:
            fail_counter = 0

        data = status_resp.json()

        status = data.get("status")
        print(f"Job status: {status}")

        if status == "stopped":
            break

    # ---- Job finished: analyze result ----
    logs = data.get("logs", [])

    parsed_logs, raw_logs = parse_logs_as_json(logs)

    print("\n========== PAPERMILL LOGS ==========")

    if parsed_logs:
        print(json.dumps(parsed_logs, indent=2))

        # Prefer exitCode from logs if present
        exit_code = parsed_logs.get("exitCode", data.get("exit_code", 1))
    else:
        # Fallback: plain text logs
        print(raw_logs.replace("\\n", "\n").replace("\\u2588", "█"))
        exit_code = data.get("exit_code", 1)

    print("===================================")

    if exit_code != 0:
        print(f"Papermill job failed (exitCode={exit_code})")

        # Optional: detailed per-notebook errors
        if parsed_logs and "results" in parsed_logs:
            for result in parsed_logs["results"]:
                if result.get("exitCode", 0) != 0:
                    print(
                        f"::error file={result.get('notebook','unknown')}::"
                        f"{result.get('stdout','')}"
                    )

        sys.exit(exit_code)

    print("Papermill job completed successfully")


if __name__ == "__main__":
    main()
