"""Tara's backend: tool endpoints Tavus calls, plus two small pages for humans.

Run:  uvicorn server:app --port 8000 --reload
"""

import difflib
import hmac
import hashlib
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

load_dotenv()
SECRET = os.environ["TAVUS_TOOL_SECRET"].encode()
API_KEY = os.environ["TAVUS_API_KEY"]
# Stock face for PALs Tara creates. Tara herself uses Anna (rc9cff32ceba);
# Lucas keeps the created PAL visibly distinct in the demo.
FACE_ID = "r3f4182ef554"
TAVUS = "https://tavusapi.com/v2"
GREETING = "Hey! Tara here. How's it going today?"

ROOT = Path(__file__).parent
LOG = ROOT / "logs" / "tool_calls.jsonl"
STATE = ROOT / "logs" / "state.json"
BUDDY = ROOT / "logs" / "buddy.json"
HIRES = json.loads((ROOT / "data" / "new_hires.json").read_text())

app = FastAPI(title="Tara backend")

PAGE = """<!doctype html><meta charset=utf-8><title>{title}</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;max-width:640px;margin:48px auto;padding:0 16px;line-height:1.6;color:#1a1a1a">
{body}</body>"""


# ---------- helpers ----------

def log(entry: dict):
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def save_state(**kw):
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    state.update(kw)
    STATE.write_text(json.dumps(state, indent=2))


async def verify(request: Request) -> dict:
    """Verify Tavus's HMAC signature against the raw body, then parse the envelope."""
    raw = await request.body()
    sig = request.headers.get("X-Tavus-Signature", "")
    expected = hmac.new(SECRET, raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="bad signature")
    env = json.loads(raw)
    env["args"] = json.loads(env.get("arguments") or "{}")  # arguments is a JSON *string*
    return env


async def tavus_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(f"{TAVUS}{path}", json=body,
                              headers={"x-api-key": API_KEY, "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Tavus {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def finish(env: dict, result: dict, started: float, status="success"):
    log({"tool": env.get("name"), "status": status, "args": env.get("args"), "result": result,
         "latency_ms": round((time.time() - started) * 1000),
         "conversation_id": env.get("conversation_id"), "turn_idx": env.get("turn_idx")})
    return result


def find_hire(ident: str):
    """Fuzzy match because speech-to-text mangles emails ("dia@tavis.io")."""
    def norm(s): return "".join(ch for ch in s.lower() if ch.isalnum())
    def score(h):
        local = h["email"].split("@")[0]
        return max(difflib.SequenceMatcher(None, norm(ident), norm(c)).ratio()
                   for c in (h["first_name"], local, h["email"]))
    if not HIRES or not ident:
        return None
    best = max(HIRES, key=score)
    return best if score(best) >= 0.75 else None


# ---------- tool handlers (called by Tavus) ----------

@app.post("/tools/get_new_hire_profile")
async def get_new_hire_profile(request: Request):
    started = time.time()
    env = await verify(request)
    ident = env["args"].get("identifier", "").strip()
    match = find_hire(ident)
    if match:
        return finish(env, {"found": True, **match}, started)
    return finish(env, {"found": False, "first_name": ident.split("@")[0].title() or "there",
                        "note": "Not in the onboarding system. Treat as a guest and continue the same flow."}, started)


@app.post("/tools/create_pal")
async def create_pal(request: Request):
    started = time.time()
    env = await verify(request)
    a = env["args"]
    prompt = (f"You are {a['pal_name']}. {a['purpose'].strip().rstrip('.')}. "
              f"Speak in a {a['tone'].strip().rstrip('.')} tone. "
              "Keep replies short and conversational; this is a live video call.")
    try:
        pal = await tavus_post("/pals", {
            "pal_name": a["pal_name"], "system_prompt": prompt, "pipeline_mode": "full",
            "default_face_id": FACE_ID,
            "layers": {"perception": {"perception_model": "raven-1"},
                       "conversational_flow": {"turn_detection_model": "sparrow-2"}},
        })
    except HTTPException as e:
        finish(env, {"ok": False, "error": e.detail}, started, status="error")
        raise  # 502 -> Tavus retries once, then tells the user the tool failed
    result = {"ok": True, "pal_id": pal.get("pal_id"), "pal_name": a["pal_name"],
              "summary": f"Created PAL '{a['pal_name']}' with raven-1 perception and sparrow-2 turn-taking."}
    save_state(last_pal=result, last_pal_prompt=prompt, last_conversation={})
    return finish(env, result, started)


@app.post("/tools/start_demo_conversation")
async def start_demo_conversation(request: Request):
    started = time.time()
    env = await verify(request)
    conv = await tavus_post("/conversations", {"pal_id": env["args"]["pal_id"],
                                               "conversation_name": "Demo of new PAL"})
    result = {"ok": True, "conversation_url": conv.get("conversation_url"),
              "summary": "The conversation is live and the link is on the screen."}
    save_state(last_conversation=result)
    return finish(env, result, started)


# ---------- pages (for humans) ----------

@app.get("/", response_class=HTMLResponse)
async def landing():
    return PAGE.format(title="Meet Tara", body="""
<h1 style="margin-bottom:4px">Meet Tara</h1>
<p style="margin-top:0;color:#555">Your onboarding buddy on the Tavus Customer Engineering team.
She'll get to know you, explain how PALs work, and build your first one with you, live.</p>
<form method=post action=/start style="margin:24px 0">
  <label>Your work email <span style="color:#888">(optional: lets Tara remember you next time)</span></label><br>
  <input name=email type=email placeholder="you@tavus.io" style="font-size:16px;padding:8px;width:280px;margin:8px 0">
  <br><button style="font-size:16px;padding:10px 18px;background:#e2466c;color:#fff;border:0;border-radius:6px;cursor:pointer">Start a call with Tara</button>
</form>
<p style="color:#888;font-size:14px">Keep <a href=/status>the status page</a> open in another window: the PAL Tara builds, and the link to talk to it, show up there.</p>
""")


@app.post("/start")
async def start(email: str = Form("")):
    pal_id = os.environ.get("TARA_PAL_ID") or json.loads(BUDDY.read_text())["buddy_pal_id"]
    email = email.strip().lower()
    body = {
        "pal_id": pal_id,
        "conversation_name": f"Tara onboarding: {email or 'guest'}",
        "custom_greeting": GREETING,
        "document_tags": ["tavus-docs"],
        "document_retrieval_strategy": "balanced",
    }
    if email:
        body["participant_tags"] = [email]  # one tag -> Tavus keeps a memory store per PAL + participant
    conv = await tavus_post("/conversations", body)
    log({"tool": "start_tara_call", "status": "success", "args": {"email": email or None},
         "result": {"conversation_id": conv.get("conversation_id")}})
    save_state(last_pal={}, last_pal_prompt="", last_conversation={})
    return RedirectResponse(conv["conversation_url"], status_code=303)


@app.get("/status", response_class=HTMLResponse)
async def status_page():
    s = json.loads(STATE.read_text()) if STATE.exists() else {}
    pal, conv = s.get("last_pal", {}), s.get("last_conversation", {})
    link = (f'<a href="{conv["conversation_url"]}" target=_blank>{conv["conversation_url"]}</a>'
            if conv.get("conversation_url") else "—")
    return PAGE.format(title="Tara: live status", body=f"""
<meta http-equiv=refresh content=3>
<h2>Tara: live status</h2>
<p><b>Last PAL created:</b> {pal.get('pal_name','—')} <code>{pal.get('pal_id','')}</code></p>
<p><b>Its prompt:</b><br><em>{s.get('last_pal_prompt') or '—'}</em></p>
<p><b>Live conversation:</b> {link}</p>
<p style="color:#888;font-size:14px">Auto-refreshes every 3s.</p>""")


@app.get("/health")
async def health():
    return {"ok": True}
