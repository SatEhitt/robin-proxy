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

    keywords = ["search", "find", "look up", "latest", "scrape", "fetch", "browse"]
    if any(kw in last_msg for kw in keywords):
        query = messages[-1]["content"]
        results = await ddg_search(query)
        if results:
            search_context = "\n\nWEB SEARCH RESULTS:\n"
            for r in results:
                search_context += f"- {r['title']}: {r['url']}\n"
            if results[0]["url"].startswith("http"):
                content = await scrape(results[0]["url"])
                search_context += f"\nPAGE CONTENT:\n{content}"

    full_system = system + search_context

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama3-70b-8192",
                "max_tokens": 1000,
                "messages": [
                    {"role": "system", "content": full_system},
                    *messages
                ],
            }
        )
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return {"content": [{"type": "text", "text": text}]}
