#!/usr/bin/env python3
import os, re, time, secrets, json, requests
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
TEMP = 0.2
MAX_TOKENS = 1200
SELF_REFINE_PASSES = 1
SEARCH_RESULTS_COUNT = 5
RATE_LIMIT_WINDOW = 15  # seconds
MAX_REQUESTS = 5
VECTOR_DB_PATH = "./vector_db.json"  # simple local storage
# ----------------

SYSTEM_PROMPT = """You are CloudX, a god-tier coding assistant.
Think deeply **only for technical tasks** (coding, math, logic), but never reveal internal reasoning.
For casual chat, reply naturally.

Use Markdown formatting for code snippets and structured responses.
Use triple backticks for code blocks and inline code for short snippets.
Keep replies concise, clear, and professional.
End reasoning with RESEARCH_QUERY: <query or NONE> if external info is needed.
"""

sessions = {}  # {token: {"messages": [...], "timestamps": [...], "memory": []}}

# ---------------- Helpers ----------------

def get_session():
    token = request.headers.get("X-Session-Token")
    if not token or token not in sessions:
        token = secrets.token_hex(16)
        sessions[token] = {"messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                           "timestamps": [], "memory": []}
    return token, sessions[token]

def check_rate_limit(session):
    now = time.time()
    session["timestamps"] = [t for t in session["timestamps"] if now - t < RATE_LIMIT_WINDOW]
    if len(session["timestamps"]) >= MAX_REQUESTS:
        return False
    session["timestamps"].append(now)
    return True

def extract_research_query(text):
    m = re.search(r"RESEARCH_QUERY\s*:\s*(.+)", text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None

def is_technical(message):
    keywords = ["code", "python", "javascript", "function", "class", "algorithm",
                "debug", "compile", "error", "logic", "calculate"]
    return any(word.lower() in message.lower() for word in keywords)

# ---------- External search ----------

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

# ---------- Vector DB ----------

def load_vector_db():
    if os.path.exists(VECTOR_DB_PATH):
        with open(VECTOR_DB_PATH) as f:
            return json.load(f)
    return []

def save_vector_db(vectors):
    with open(VECTOR_DB_PATH, "w") as f:
        json.dump(vectors, f)

def embed_text(text):
    # simple placeholder: in prod, use OpenAI embeddings
    return text.lower().split()

def vector_search(query, db, top_k=3):
    q_vec = set(embed_text(query))
    scored = [(entry, len(q_vec.intersection(set(embed_text(entry["content"])))) ) for entry in db]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s[0]["content"] for s in scored[:top_k] if s[1]>0]

# ---------- AI call ----------

def ask_model(messages):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMP,
        max_tokens=MAX_TOKENS
    )
    return resp.choices[0].message.content

# ---------- Routes ----------

@app.route("/api/chat", methods=["POST"])
def chat():
    token, session = get_session()

    if not check_rate_limit(session):
        return jsonify({"error": "Rate limit reached. Try later."}), 429

    user_msg = request.json.get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # inject vector memory
    vector_db = load_vector_db()
    relevant_mem = vector_search(user_msg, vector_db)
    for mem in relevant_mem:
        session["messages"].append({"role": "system", "content": "Memory context:\n" + mem})

    session["messages"].append({"role": "user", "content": user_msg})
    reply = ask_model(session["messages"])
    session["messages"].append({"role": "assistant", "content": reply})

    # optional research if AI requests it
    rq = extract_research_query(reply)
    if rq and rq.upper() != "NONE":
        hits = search_duckduckgo(rq)
        sr = format_search_results(hits)
        session["messages"].append({"role":"assistant", "content": f"TOOL: {sr}"})
        session["messages"].append({"role":"user", "content":"Revise answer using above results."})
        reply = ask_model(session["messages"])
        session["messages"].append({"role":"assistant","content":reply})

    # self-refinement only if technical
    if is_technical(user_msg):
        for _ in range(SELF_REFINE_PASSES):
            session["messages"].append({"role":"user","content":"Reviewer: list issues (max 3) and produce improved answer only."})
            reply = ask_model(session["messages"])
            session["messages"].append({"role":"assistant","content":reply})

    return jsonify({"reply": reply, "session_token": token})

# ---------- File ingestion ----------

@app.route("/api/ingest_file", methods=["POST"])
def ingest_file():
    token, session = get_session()
    file_data = request.json.get("content", "")
    description = request.json.get("description", "File content")
    vector_db = load_vector_db()
    vector_db.append({"content": file_data, "description": description})
    save_vector_db(vector_db)
    return jsonify({"status": "ok", "entries": len(vector_db)})

# ---------- Run ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
