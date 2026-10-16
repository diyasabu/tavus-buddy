"""Crawl docs.tavus.io into the Tavus knowledge base, tagged `tavus-docs`.

Processing takes 5-10 minutes; check status in the portal under Knowledge Base
or with GET /v2/documents/{document_id}.

Usage:  python setup_knowledge.py
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()
r = httpx.post(
    "https://tavusapi.com/v2/documents",
    headers={"x-api-key": os.environ["TAVUS_API_KEY"], "Content-Type": "application/json"},
    timeout=30,
    json={
        "document_name": "Tavus docs",
        "document_url": "https://docs.tavus.io/sections/conversational-video-interface/overview",
        "tags": ["tavus-docs"],
        "crawl": {"depth": 2, "max_pages": 40},
    },
)
print(r.status_code, r.json())
