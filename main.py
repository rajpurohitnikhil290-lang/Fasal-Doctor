"""Fasal Doctor backend.

POST /api/analyze  (multipart: image, crop, lang)  ->  JSON diagnosis
GET  /             ->  the website (static/index.html)

Run locally:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...        (Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-...")
    uvicorn main:app --reload
"""
import base64
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from anthropic import AsyncAnthropic
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_IMAGE_BYTES = 5 * 1024 * 1024          # the website already shrinks photos to ~200 KB
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))   # photos per IP per hour (protects your API bill)

LANGS = {
    "hi": "Hindi (हिंदी, simple words a farmer understands)",
    "en": "English (simple words)",
    "gu": "Gujarati (ગુજરાતી, simple words)",
}

BASE_DIR = Path(__file__).parent
app = FastAPI(title="Fasal Doctor")
client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from the environment

_hits: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str) -> None:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "Too many requests, try again later")
    q.append(now)


def build_prompt(crop: str, lang: str) -> str:
    crop_line = (
        f"The farmer says the crop is: {crop}."
        if crop
        else "The farmer did not name the crop; identify it from the photo."
    )
    return f"""You are an expert Indian plant pathologist and agronomist helping a small farmer.
Look at the attached photo of a crop plant and identify the problem (disease, pest damage, or nutrient deficiency).
{crop_line}
Write ALL text values in {LANGS[lang]}. Use very simple words, short sentences, no jargon.
Give practical advice usable in India: cheap, locally available options first. For chemical options name the active ingredient (e.g. mancozeb, copper oxychloride) and say to follow the label dose; do not invent exact doses.
If the photo is unclear, give the most likely cause. If there is no plant in the photo, set "is_plant" to false.
Reply with ONLY valid JSON (no markdown fences), exactly this shape:
{{"is_plant":true,"plant":"crop name","healthy":false,"disease":"name of disease/pest/deficiency","severity":"low|medium|high","symptoms":["..."],"cause":"1-2 simple sentences","organic":["..."],"chemical":["..."],"prevention":["..."]}}"""


def parse_json(text: str) -> dict:
    text = text.strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("no JSON in model reply")
    return json.loads(text[a : b + 1])


@app.post("/api/analyze")
async def analyze(
    request: Request,
    image: UploadFile = File(...),
    crop: str = Form(""),
    lang: str = Form("hi"),
):
    ip = (request.headers.get("x-forwarded-for") or request.client.host or "unknown").split(",")[0].strip()
    check_rate_limit(ip)

    if lang not in LANGS:
        lang = "hi"
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Please upload a JPEG, PNG or WebP photo")
    data = await image.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Photo is empty or too large (max 5 MB)")

    try:
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.content_type,
                                "data": base64.b64encode(data).decode(),
                            },
                        },
                        {"type": "text", "text": build_prompt(crop.strip()[:60], lang)},
                    ],
                }
            ],
        )
        return parse_json(msg.content[0].text)
    except HTTPException:
        raise
    except Exception as e:  # API down, bad key, unparsable reply...
        print("analyze error:", repr(e))
        raise HTTPException(502, "Could not analyze the photo, please try again")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
