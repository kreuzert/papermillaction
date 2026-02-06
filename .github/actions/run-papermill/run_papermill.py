#!/usr/bin/env python3
import os
import sys
import json
import requests

def main():
    repo = os.environ.get("INPUT_REPO")
    ref = os.environ.get("INPUT_REF", "HEAD")
    token = os.environ.get("INPUT_TOKEN")
    api_url = os.environ.get("INPUT_API_URL", "https://jupyter-jsc-dev1.fz-juelich.de/hub/api/job")

    if not all([repo, token, api_url]):
        print("ERROR: Missing required inputs: repo, api_url, or token")
        sys.exit(1)

    payload = {
        "user_options": {
            "option": "repo2docker",
            "repo2docker": {
                "repotype": "gh",
                "repourl": repo,
                "reporef": ref
            }
        }
    }

    resp = requests.post(
        api_url,
        headers={"Authorization": f"token {token}"},
        json=payload
    )
    resp.raise_for_status()
    data = resp.json()

    exit_code = data.get("exit_code", 1)
    logs = data.get("logs", [])

    # Format logs nicely
    formatted_logs = []
    for line in logs:
        line = line.replace("\\n", "\n").replace("\\u2588", "█")
        formatted_logs.append(line)
    print("========== PAPERMILL LOGS ==========")
    print("\n".join(formatted_logs))
    print("===================================")

    if exit_code != 0:
        print(f"Papermill job failed with exit_code={exit_code}")
        sys.exit(exit_code)
    else:
        print("Papermill job completed successfully.")

if __name__ == "__main__":
    main()

