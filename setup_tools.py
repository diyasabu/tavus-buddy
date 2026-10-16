"""Register (or re-point) Tara's three tools in the Tavus tools registry.

Run once after the backend is reachable at PUBLIC_BASE_URL. Safe to re-run:
if a tool name already exists it is updated to the current URL and secret.
Writes the resulting tool_ids to logs/tools.json for createbuddy.py.

Usage:  python setup_tools.py
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
API = "https://tavusapi.com/v2"
H = {"x-api-key": os.environ["TAVUS_API_KEY"], "Content-Type": "application/json"}
BASE = os.environ["PUBLIC_BASE_URL"].rstrip("/")
SECRET = os.environ["TAVUS_TOOL_SECRET"]
OUT = Path(__file__).parent / "logs" / "tools.json"


def delivery(path: str, timeout: int) -> dict:
    return {"api": {"url": f"{BASE}/tools/{path}", "method": "POST",
                    "auth": {"type": "hmac", "secret": SECRET}, "timeout": timeout}}


TOOLS = [
    {
        "name": "get_new_hire_profile",
        "description": ("Look up a new hire's onboarding profile by work email or first name. "
                        "Call this once, right after the user tells you who they are. "
                        "Returns a guest profile if not found."),
        "parameters": {"type": "object", "properties": {
            "identifier": {"type": "string", "description": "The user's work email or first name, exactly as they said it."}},
            "required": ["identifier"]},
        "origin": "llm", "on_call": "generate_filler", "on_resolve": "generate_response",
        "delivery": delivery("get_new_hire_profile", 10),
    },
    {
        "name": "create_pal",
        "description": ("Create a new Tavus PAL from the user's answers. Only call after the user has confirmed "
                        "all three: purpose, name, and tone. Never call twice for the same PAL. "
                        "Creating the PAL does not start a call or produce a link."),
        "parameters": {"type": "object", "properties": {
            "pal_name": {"type": "string", "description": "What the user wants the PAL called."},
            "purpose": {"type": "string", "description": "One sentence describing what the PAL does, in the user's words."},
            "tone": {"type": "string", "description": "How the PAL should sound, e.g. warm, direct, playful, formal."}},
            "required": ["pal_name", "purpose", "tone"]},
        "origin": "llm", "on_call": "static_filler",
        "static_filler": "Creating that PAL for you now, give me a few seconds.",
        "on_resolve": "generate_response",
        "delivery": delivery("create_pal", 30),
    },
    {
        "name": "start_demo_conversation",
        "description": ("Start a live video conversation with the PAL that was just created so the user can talk to it. "
                        "Only call after create_pal succeeded and the user said yes to trying it."),
        "parameters": {"type": "object", "properties": {
            "pal_id": {"type": "string", "description": "The pal_id returned by create_pal."}},
            "required": ["pal_id"]},
        "origin": "llm", "on_call": "generate_filler", "on_resolve": "generate_response",
        "delivery": delivery("start_demo_conversation", 30),
    },
]


def existing_tools() -> dict:
    r = httpx.get(f"{API}/tools", headers=H, timeout=30)
    r.raise_for_status()
    data = r.json()
    items = data if isinstance(data, list) else data.get("data", [])
    return {t["name"]: t["tool_id"] for t in items}


def main():
    have = existing_tools()
    ids = {}
    for t in TOOLS:
        if t["name"] in have:
            tid = have[t["name"]]
            patch = [{"op": "replace", "path": "/delivery", "value": t["delivery"]},
                     {"op": "replace", "path": "/description", "value": t["description"]}]
            r = httpx.patch(f"{API}/tools/{tid}", headers=H, json=patch, timeout=30)
            print(f"updated  {t['name']:26} {tid}  ({r.status_code})")
        else:
            r = httpx.post(f"{API}/tools", headers=H, json=t, timeout=30)
            if r.status_code >= 400:
                sys.exit(f"create {t['name']} failed: {r.status_code} {r.text}")
            tid = r.json()["tool_id"]
            print(f"created  {t['name']:26} {tid}")
        ids[t["name"]] = tid
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(ids, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
