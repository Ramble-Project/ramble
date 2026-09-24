#!/usr/bin/env python3
# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

import jwt
from google.cloud import bigquery

# This is used to dedupe comments
_COMMENT_MARKER = "<!-- ramble-perf-test-metrics -->"
_RECENT_RESULTS_COUNT = 5

def get_bq_historical_metrics(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    query = f"""
        SELECT
            test_name,
            AVG(duration) as avg_duration,
            MAX(CASE WHEN rn = 1 THEN duration END) as most_recent_duration,
            MAX(CASE WHEN rn = 1 THEN commit_sha END) as most_recent_commit_sha
        FROM (
            SELECT test_name, duration, commit_sha,
                   ROW_NUMBER() OVER(PARTITION BY test_name ORDER BY timestamp DESC) as rn
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE duration IS NOT NULL
        )
        WHERE rn <= {_RECENT_RESULTS_COUNT}
        GROUP BY test_name
    """
    try:
        query_job = client.query(query)
        results = query_job.result()
        return {
            row.test_name: {
                "avg_duration": row.avg_duration,
                "most_recent_duration": row.most_recent_duration,
                "most_recent_commit_sha": row.most_recent_commit_sha
            }
            for row in results
        }
    except Exception as e:
        print(f"Error querying BigQuery: {e}")
        return {}

def make_github_request(url, token, method="GET", data=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    
    if data is not None:
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"GitHub API Error: {e.code} - {error_msg}")
        raise

def get_installation_token(client_id, private_key, repo):
    if not jwt:
        print("PyJWT is required for GitHub App authentication. Please pip install PyJWT cryptography")
        sys.exit(1)
        
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": client_id
    }
    
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
    
    url_install = f"https://api.github.com/repos/{repo}/installation"
    print(f"Fetching installation ID for {repo}...")
    install_data = make_github_request(url_install, encoded_jwt)
    install_id = install_data["id"]
    
    url_token = f"https://api.github.com/app/installations/{install_id}/access_tokens"
    print("Fetching installation access token...")
    token_data = make_github_request(url_token, encoded_jwt, method="POST")
    return token_data["token"]



def format_markdown(metrics, historical_data, commit_sha=None, repo="Ramble-Project/ramble"):
    lines = [
        "## Ramble Performance Test Metrics",
    ]
    if commit_sha:
        lines.append(f"Results produced with commit: {commit_sha}")
    lines.extend([
        "",
        f"| Test Name | Outcome | Duration (s) | Most Recent Run (s) | Last {_RECENT_RESULTS_COUNT} Avg (s) |",
        "|---|---|---|---|---|"
    ])
    
    for m in metrics:
        name = m.get("test_name", "Unknown")
        duration = m.get("duration", "N/A")
        outcome = m.get("outcome", "N/A")
        
        hist = historical_data.get(name, {})
        avg_dur = hist.get("avg_duration")
        most_recent_dur = hist.get("most_recent_duration")
        most_recent_commit = hist.get("most_recent_commit_sha")

        avg_str = f"{avg_dur:.4f}" if avg_dur is not None else "N/A"
        
        if most_recent_dur is not None:
            most_recent_str = f"{most_recent_dur:.4f}"
            if most_recent_commit:
                short_sha = most_recent_commit[:7]
                commit_url = f"https://github.com/{repo}/commit/{most_recent_commit}"
                most_recent_str = f"{most_recent_str} ([{short_sha}]({commit_url}))"
        else:
            most_recent_str = "N/A"
        
        if isinstance(duration, float):
            duration = f"{duration:.4f}"
            
        lines.append(f"| {name} | {outcome} | {duration} | {most_recent_str} | {avg_str} |")
        
    lines.append("")
    lines.append(_COMMENT_MARKER)
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Post Ramble perf metrics to a GitHub PR")
    parser.add_argument("--metrics-file", required=True, help="Path to metrics JSON file")
    parser.add_argument("--project-id", help="GCP Project ID")
    parser.add_argument("--dataset-id", help="BigQuery Dataset ID")
    parser.add_argument("--table-id", help="BigQuery Table ID")
    parser.add_argument("--pr-number", required=True, help="GitHub Pull Request number")
    parser.add_argument("--repo", default="Ramble-Project/ramble", help="GitHub repository (owner/repo)")
    parser.add_argument("--commit-sha", help="Commit SHA results were produced with")
    parser.add_argument("--dry-run", action="store_true", help="Print only")
    
    args = parser.parse_args()

    client_id = os.environ.get("GITHUB_CLIENT_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    
    if (not client_id or not private_key) and not args.dry_run:
        print("GITHUB_CLIENT_ID and GITHUB_APP_PRIVATE_KEY environment variables must be set.")
        sys.exit(1)
        
    if not os.path.exists(args.metrics_file):
        print(f"Metrics file {args.metrics_file} not found.")
        sys.exit(0)
        
    with open(args.metrics_file, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    if not metrics:
        print("No metrics to post.")
        sys.exit(0)

    historical_data = get_bq_historical_metrics(args.project_id, args.dataset_id, args.table_id)
    
    body = format_markdown(metrics, historical_data, args.commit_sha, args.repo)
    
    if args.dry_run:
        print("[DRY RUN] Would post the following comment:")
        print(body)
        sys.exit(0)
        
    token = get_installation_token(client_id, private_key, args.repo)
        
    # Avoid posting multiple comments
    url_comments = f"https://api.github.com/repos/{args.repo}/issues/{args.pr_number}/comments"
    comments = make_github_request(url_comments, token)
    
    existing_comment = None
    for c in comments:
        if _COMMENT_MARKER in c.get("body", ""):
            existing_comment = c
            break
            
    if existing_comment:
        print(f"Found existing comment (ID: {existing_comment['id']}). Updating...")
        update_url = f"https://api.github.com/repos/{args.repo}/issues/comments/{existing_comment['id']}"
        make_github_request(update_url, token, method="PATCH", data={"body": body})
        print("Comment updated successfully.")
    else:
        print("Creating new comment...")
        make_github_request(url_comments, token, method="POST", data={"body": body})
        print("Comment created successfully.")

if __name__ == "__main__":
    main()
