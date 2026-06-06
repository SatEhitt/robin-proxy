from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

async def scrape(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text[:3000]
    except Exception as e:
        return f"Scrape error: {str(e)}"

async def ddg_search(query: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for a in soup.select(".result__a")[:5]:
                results.append({"title": a.get_text(), "url": a.get("href", "")})
            return results
    except Exception as e:
        return [{"title": "Search error", "url": str(e)}]

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    system = body.get("system", "")

    last_msg = messages[-1]["content"].lower() if messages else ""
    search_context = ""

    if any(kw in last_msg for kw in ["search", "find", "look up", "latest", "scrape", "fetch", "browse"]):
