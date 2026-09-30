"""Langfuse Prompt Management Script for Day 13 Lab.

Supports:
- init: Create version 1 (labels: baseline, production) and version 2 (label: candidate)
- promote: Move label 'production' to version 2
- rollback: Move label 'production' back to version 1
- status: Print current prompts, versions, and labels
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

try:
    from langfuse import Langfuse
except ImportError:
    print("Error: langfuse library not found. Run in the repository virtualenv.")
    sys.exit(1)


V1_TEMPLATE = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
V2_TEMPLATE = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\nHãy trả lời ngắn gọn và súc tích."


def get_client() -> Langfuse:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    if not (public_key and secret_key):
        raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set in .env")
    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def cmd_status(client: Langfuse, prompt_name: str) -> None:
    print(f"\n--- Checking Langfuse prompts for '{prompt_name}' ---")
    try:
        # Check production label
        try:
            prod_p = client.get_prompt(prompt_name, label="production", type="text")
            print(f"[production] -> Version {prod_p.version} (labels: {getattr(prod_p, 'labels', [])})")
        except Exception as e:
            print(f"[production] -> Not found or error: {e}")

        # Check baseline label
        try:
            base_p = client.get_prompt(prompt_name, label="baseline", type="text")
            print(f"[baseline]   -> Version {base_p.version} (labels: {getattr(base_p, 'labels', [])})")
        except Exception as e:
            print(f"[baseline]   -> Not found or error: {e}")

        # Check candidate label
        try:
            cand_p = client.get_prompt(prompt_name, label="candidate", type="text")
            print(f"[candidate]  -> Version {cand_p.version} (labels: {getattr(cand_p, 'labels', [])})")
        except Exception as e:
            print(f"[candidate]  -> Not found or error: {e}")

    except Exception as e:
        print(f"Error fetching prompt status: {e}")


def cmd_init(client: Langfuse, prompt_name: str) -> None:
    print(f"\n--- Initializing prompt '{prompt_name}' ---")
    print("1. Creating Version 1 with labels: ['baseline', 'production']...")
    try:
        p1 = client.create_prompt(
            name=prompt_name,
            prompt=V1_TEMPLATE,
            type="text",
            labels=["baseline", "production"],
            commit_message="Version 1: baseline prompt with {{feature}}, {{docs}}, {{message}}",
        )
        print(f"   Created Version {p1.version} successfully.")
    except Exception as e:
        print(f"   Version 1 creation note: {e}")

    print("2. Creating Version 2 with labels: ['candidate']...")
    try:
        p2 = client.create_prompt(
            name=prompt_name,
            prompt=V2_TEMPLATE,
            type="text",
            labels=["candidate"],
            commit_message="Version 2: candidate prompt with conciseness instruction",
        )
        print(f"   Created Version {p2.version} successfully.")
    except Exception as e:
        print(f"   Version 2 creation note: {e}")

    cmd_status(client, prompt_name)


def cmd_promote(client: Langfuse, prompt_name: str) -> None:
    print(f"\n--- Promoting Version 2 to 'production' for '{prompt_name}' ---")
    try:
        updated = client.update_prompt(
            name=prompt_name,
            version=2,
            new_labels=["candidate", "production"],
        )
        print(f"Successfully moved 'production' label to Version 2.")
    except Exception as e:
        print(f"Error promoting prompt: {e}")
    cmd_status(client, prompt_name)


def cmd_rollback(client: Langfuse, prompt_name: str) -> None:
    print(f"\n--- Rolling back 'production' to Version 1 for '{prompt_name}' ---")
    try:
        updated = client.update_prompt(
            name=prompt_name,
            version=1,
            new_labels=["baseline", "production"],
        )
        print(f"Successfully rolled back 'production' label to Version 1.")
    except Exception as e:
        print(f"Error rolling back prompt: {e}")
    cmd_status(client, prompt_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Langfuse prompts for Day 13")
    parser.add_argument("action", choices=["status", "init", "promote", "rollback"], default="status", nargs="?")
    parser.add_argument("--name", default=os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat"))
    args = parser.parse_args()

    client = get_client()
    if args.action == "init":
        cmd_init(client, args.name)
    elif args.action == "promote":
        cmd_promote(client, args.name)
    elif args.action == "rollback":
        cmd_rollback(client, args.name)
    else:
        cmd_status(client, args.name)


if __name__ == "__main__":
    main()
