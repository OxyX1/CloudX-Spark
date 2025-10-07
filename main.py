#!/usr/bin/env python3
import os, re, requests, time, secrets
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
CORS(app)

# ---- CONFIG ----
MODEL = "gpt-4o-mini"
TEMP = 0.15
MAX_TOKENS = 900
SEARCH_RESULTS_COUNT = 5
SELF_REFINE_PASSES = 1
RATE_LIMIT_WINDOW = 15  # seconds
MAX_REQUESTS = 5
# ----------------

SYSTEM_PROMPT = """You are CloudX, a god-tier coding assistant.
You think deeply and reason internally — but **only** when the question involves coding, logic, math, or technical problem-solving.

If the user is just chatting or asking something simple, reply normally without deep reasoning.

When reasoning internally, never show your thought process — only output the final, polished answer in **Markdown** format.

If you need external info, end your private reasoning with:
RESEARCH_QUERY: <query or NONE>

Rules:
- Never reveal your reasoning or steps.
- Always make final answers clean, well-formatted, and helpful.
- For code or technical stuff, use triple backticks for code blocks and `inline code` for short snippets.
"""


sessions = {}  # {session_token: {"messages": [...], "timestamps": [..]}}

# --- Helpers ---

def get_session():
    token = request.headers.get("X-Session-Token")
    if not token or token not in sessions:
        token = secrets.token_hex(16)
        sessions[token] = {"messages": [{"role": "system", "content": SYSTEM_PROMPT}], "timestamps": []}
    return token, sessions[token]

def check_rate_limit(session):
    now = time.time()
    timestamps = session["timestamps"]
    timestamps[:] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= MAX_REQUESTS:
        return False
    timestamps.append(now)
    return True

def extract_research_query(text):
    m = re.search(r"RESEARCH_QUERY\s*:\s*(.+)", text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None

def search_serpapi(query, num=5):
    try:
        from serpapi import GoogleSearch
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY not set.")
        params = {"engine": "google", "q": query, "api_key": api_key, "num": num}
        search = GoogleSearch(params)
        res = search.get_dict()
        hits = []
        for r in (res.get("organic_results") or [])[:num]:
            hits.append({
                "title": r.get("title"),
                "snippet": r.get("snippet"),
                "link": r.get("link")
            })
        return hits
    except Exception as e:
        print("SerpAPI fallback:", e)
        return search_duckduckgo(query, num)

def search_duckduckgo(query, num=5):
    try:
        res = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        soup = BeautifulSoup(res.text, "html.parser")
        hits = []
        for r in soup.select("div.result")[:num]:
            a = r.select_one("a")
            title = a.get_text().strip() if a else ""
            link = a.get("href") if a else ""
            snippet_tag = r.select_one(".result__snippet") or r.select_one("a")
            snippet = snippet_tag.get_text().strip() if snippet_tag else ""
            hits.append({"title": title, "snippet": snippet, "link": link})
        return hits or [{"title": "No results", "snippet": "N/A", "link": ""}]
    except Exception as e:
        return [{"title": "Search failure", "snippet": str(e), "link": ""}]

def format_search_results(results):
    return "\n\n".join([f"**{r['title']}**\n{r['snippet']}\n{r['link']}" for r in results])

def ask_model(messages):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content

@app.route("/api/chat", methods=["POST"])
def chat():
    token, session = get_session()

    if not check_rate_limit(session):
        return jsonify({"error": "Rate limit reached. Try again later."}), 429

    user_msg = request.json.get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    session["messages"].append({"role": "user", "content": user_msg})
    reply = ask_model(session["messages"])
    session["messages"].append({"role": "assistant", "content": reply})

    rq = extract_research_query(reply)
    if rq and rq.upper() != "NONE":
        hits = search_serpapi(rq)
        sr = format_search_results(hits)
        session["messages"].append({"role": "assistant", "content": f"TOOL: {sr}"})
        session["messages"].append({"role": "user", "content": "Revise your answer using the results above."})
        revised = ask_model(session["messages"])
        session["messages"].append({"role": "assistant", "content": revised})
        reply = revised

    return jsonify({"reply": reply, "session_token": token})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
