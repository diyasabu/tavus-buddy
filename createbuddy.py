"""Create (or re-create) Tara from the prompt files and attach her tools.

Run this after setup_tools.py, and again whenever you change prompts/.
Writes Tara's pal_id to logs/buddy.json, which the landing page reads.

Usage:
  python createbuddy.py                 # new Tara + an anonymous call link
  python createbuddy.py call            # call with the existing Tara, no memory
  python createbuddy.py call me@x.io    # call with memory for that participant
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
ROOT = Path(__file__).parent
GREETING = "Hey! Tara here. How's it going today?"


def tool_ids() -> list:
    p = ROOT / "logs" / "tools.json"
    if not p.exists():
        sys.exit("logs/tools.json not found. Run setup_tools.py first.")
    return list(json.loads(p.read_text()).values())


def create_pal() -> str:
    r = httpx.post(f"{API}/pals", headers=H, timeout=30, json={
        "pal_name": "Tara (CE Onboarding Buddy)",
        "system_prompt": (ROOT / "prompts" / "buddy_system_prompt.md").read_text(),
        "context": (ROOT / "prompts" / "buddy_context.md").read_text(),
        "pipeline_mode": "full",
        "default_face_id": "rc9cff32ceba",  # stock "Anna"
        "layers": {
            "llm": {"model": "tavus-gpt-5.6-terra", "speculative_inference": True,
                    "extra_body": {"temperature": 0.7}},
            "perception": {"perception_model": "raven-1"},
            "conversational_flow": {"turn_detection_model": "sparrow-2",
                                    "turn_taking_patience": "medium",
                                    "pal_interruptibility": "medium"},
        },
    })
    if r.status_code >= 400:
        sys.exit(f"PAL create failed: {r.status_code} {r.text}")
    pal_id = r.json()["pal_id"]
    print("Tara pal_id:", pal_id)
    a = httpx.post(f"{API}/pals/{pal_id}/tools", headers=H, timeout=30, json={"tool_ids": tool_ids()})
    print("attach tools:", a.status_code)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs" / "buddy.json").write_text(json.dumps({"buddy_pal_id": pal_id}))
    return pal_id


def start_call(pal_id: str, participant) -> None:
    body = {
        "pal_id": pal_id,
        "conversation_name": "Tara onboarding",
        "custom_greeting": GREETING,
        "document_tags": ["tavus-docs"],
        "document_retrieval_strategy": "balanced",
    }
    if participant:
        body["participant_tags"] = [participant]
    r = httpx.post(f"{API}/conversations", headers=H, timeout=30, json=body)
    if r.status_code >= 400:
        sys.exit(f"conversation failed: {r.status_code} {r.text}")
    print(f"\nParticipant: {participant or 'anonymous (no memory)'}\nOPEN THIS: {r.json()['conversation_url']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    participant = next((a for a in args if "@" in a), None)
    if "call" in args:
        pal_id = json.loads((ROOT / "logs" / "buddy.json").read_text())["buddy_pal_id"]
    else:
        pal_id = create_pal()
    start_call(pal_id, participant)
