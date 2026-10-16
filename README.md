# Tara: an onboarding buddy that builds PALs with you

**Demo (Loom):** https://www.loom.com/share/23e1e00b79f44a6c841393ad68ae9589
**Try her live:** Tara lives in my Tavus account as PAL `p0f88c666a0c`. Message me and I'll start a session for you.

Tara is a Tavus PAL for new engineers joining the Customer Engineering team. She makes small talk, pulls up your onboarding profile, explains what a PAL is, and then builds your first PAL with you, live, by calling the Tavus API through tools. Come back the next day and she remembers you and what you built.

## Why I built this

When I started at my current company, my first week was pretty unstructured. Everyone was busy (startup life) so nobody really had the time to onboard me. I ended up going around asking people how things were done and basically onboarded myself. I'm sure this happens at a lot of companies, and I kept thinking it would have been so helpful to have someone who always had time for my questions.

So I built that. Tara is designed with me as the end user, or really anyone who's starting new at Tavus. She makes small talk, knows who you are, teaches you the product the way the team thinks people learn best (by building something), and remembers you the next day.

It's also kind of meta on purpose. A PAL that onboards you onto Tavus by building a Tavus PAL with you touches all the things a real customer implementation touches: persona design, tool calling into a backend, the Tavus API as a tool, the knowledge base, memory. That overlap with the actual job is why I picked this over a support bot or SDR demo.

## What happens on a call

1. Tara greets you and makes a bit of small talk, then asks who you are. That calls `get_new_hire_profile`, which is fuzzy-matched because speech-to-text turns "diya@tavus.io" into "dia@tavis.io". Unknown people are treated as guests and the flow continues.
2. She explains what a PAL is, checks whether you already know, and gets into the weeds. "That's how we think people learn."
3. She asks three things, one at a time: what the PAL should do, what to call it, how it should sound. Confirms them back.
4. `create_pal` calls `POST /v2/pals` with a prompt built from your answers, Raven perception on, Sparrow turn-taking. The new PAL shows up on the status page.
5. "Want to meet it?" `start_demo_conversation` calls `POST /v2/conversations`. The link appears on the status page; you open it and talk to the PAL you just designed.
6. Next call, same email: Tara already knows you and what you built, and suggests the next step.

She also answers questions from a knowledge base built by crawling docs.tavus.io, and has guardrails for competitor comparisons, confidential company info, financial/medical advice, and credentials.

## Architecture

```
Browser ──WebRTC──▶ Tavus CVI (Tara)
                      │  perception: raven-1 · turn-taking: sparrow-2 · llm: tavus-gpt-5.6-terra
                      │  knowledge base: docs.tavus.io crawl (document_tags)
                      │  memory: per-participant store (participant_tags = email)
                      │
                      │  tool call: HTTPS POST, HMAC-signed
                      ▼
            FastAPI backend (server.py)
              ├─ /tools/get_new_hire_profile     → data/new_hires.json (mock HRIS)
              ├─ /tools/create_pal               → POST tavusapi.com/v2/pals
              ├─ /tools/start_demo_conversation  → POST tavusapi.com/v2/conversations
              ├─ /         landing page: enter email, start a call with Tara
              ├─ /status   live board: PAL just created + link to talk to it
              └─ logs/tool_calls.jsonl           every call, args, result, latency
```

Tools are registered in the Tavus tools registry (`/v2/tools`) with API delivery. Tavus POSTs a signed envelope to the backend; the backend verifies `X-Tavus-Signature` against the raw body bytes, does the work, and the 2xx response becomes the tool result the LLM speaks from (`on_resolve: generate_response`).

## Decisions worth explaining

| Choice | Why |
|---|---|
| Backend tools, not direct API delivery | Tavus can call its own API directly from a tool. A backend gives logging with latency, a status page, a guest fallback, and one place to handle errors. That's what a real implementation ends up needing. |
| `tavus-gpt-5.6-terra` | Tool adherence mattered more than latency. The flow has to call three tools in order and not skip one. |
| `on_call: static_filler` on `create_pal` | A fixed "creating that now" line while a real API call runs. No improvising mid-flight. |
| Fuzzy profile lookup | Voice-dictated emails are unreliable. Match on name, email, and local part with a similarity threshold; fall back to guest. |
| Memory via `participant_tags` | One line on conversation create and Tavus handles the store. Turns a demo into something you'd use for a week of onboarding. |
| Guardrails in the prompt | Fastest path for a take-home. In production I'd move them to Tavus Guardrails so they can't be prompted away. |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in TAVUS_API_KEY and TAVUS_TOOL_SECRET

uvicorn server:app --port 8000 --reload     # terminal 1
ngrok http 8000                             # terminal 2, put the https URL in .env as PUBLIC_BASE_URL

python setup_knowledge.py       # crawl docs.tavus.io into the knowledge base (takes ~10 min to process)
python setup_tools.py           # register the three tools pointing at PUBLIC_BASE_URL
python createbuddy.py           # create Tara from prompts/ and attach the tools

open http://localhost:8000      # enter an email, start a call. Keep /status open beside it.
```

Re-run `createbuddy.py` whenever you change `prompts/`. Re-run `setup_tools.py` if the ngrok URL changes.

## What I'd do with another week

- Let the hire pick the face and voice as a fourth question.
- Onboarding checklist tool, ticked off as things happen, shown on the status page.
- Screen-share guidance: Raven watches the hire click through the portal and points them at the next button.
- Internal docs in the knowledge base (glossary, "how we run a demo") so Tara knows how the team works, not just the product.
- Host the backend so Tara's tools work when my laptop is closed; move guardrails to the platform; idempotency key on `create_pal` using `{tavus_tool_call_id}`.

## Tests I ran

Happy path · guest user (not in HRIS) · change-of-mind before confirming · off-script Tavus question · bad API key (Tara reports the failure, doesn't pretend it worked) · memory across two calls. Log excerpts are in the Loom.
