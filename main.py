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

# ---- INITIAL VECTOR DB CONTENT ----
vector_db = []

vector_db.append({
    "content": """
<!-- NAVBAR -->
<nav class="flex justify-between items-center p-4 bg-white shadow-md">
  <a href="#" class="text-xl font-bold text-gray-800">Brand</a>
  <ul class="flex space-x-4">
    <li><a href="#" class="text-gray-600 hover:text-gray-900">Home</a></li>
    <li><a href="#" class="text-gray-600 hover:text-gray-900">Portfolio</a></li>
    <li><a href="#" class="text-gray-600 hover:text-gray-900">Contact</a></li>
  </ul>
</nav>
""",
    "description": "Clean responsive navbar example"
})

vector_db.append({
    "content": """
.truncate-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
""",
    "description": "CSS utility for truncating text with ellipsis"
})

vector_db.append({
    "content": """
<!-- Modern Glassy Navbar -->
<nav class="flex items-center justify-between px-6 py-3 bg-[rgba(255,255,255,0.1)] backdrop-blur-md border border-[rgba(255,255,255,0.15)] rounded-2xl shadow-lg">
  <h1 class="text-xl font-bold text-white">CloudX</h1>
  <ul class="flex space-x-6 text-gray-200">
    <li><a href="#" class="hover:text-white transition">Home</a></li>
    <li><a href="#" class="hover:text-white transition">Projects</a></li>
    <li><a href="#" class="hover:text-white transition">Contact</a></li>
  </ul>
  <button class="px-4 py-2 rounded-full bg-blue-500 text-white hover:bg-blue-600 transition">Sign In</button>
</nav>
""",
    "description": "Glassy translucent navbar"
})

vector_db.append({
    "content": """
html {
  scroll-behavior: smooth;
}
""",
    "description": "Smooth scrolling behavior"
})

vector_db.append({
    "content": """
<!-- Project Grid -->
<section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-8">
  <div class="bg-[#1e293b] rounded-2xl p-5 hover:scale-105 transition shadow-md">
    <img src="project1.jpg" alt="Project 1" class="rounded-lg mb-3 w-full">
    <h3 class="text-xl font-semibold text-white">AI Chat Assistant</h3>
    <p class="text-gray-400 text-sm mt-2">A modern AI chatbot built with Flask and OpenAI.</p>
  </div>
  <div class="bg-[#1e293b] rounded-2xl p-5 hover:scale-105 transition shadow-md">
    <img src="project2.jpg" alt="Project 2" class="rounded-lg mb-3 w-full">
    <h3 class="text-xl font-semibold text-white">CloudX Dashboard</h3>
    <p class="text-gray-400 text-sm mt-2">A clean, interactive analytics dashboard with Tailwind UI.</p>
  </div>
</section>
""",
    "description": "Responsive project grid with hover effects"
})

vector_db.append({
    "content": """
<!-- Hero Section -->
<section class="flex flex-col items-center justify-center text-center py-24 px-6 bg-gradient-to-br from-[#0f172a] to-[#1e293b] text-white">
  <h1 class="text-5xl font-bold mb-4">Hey, I’m <span class="text-blue-400">Oxyus</span></h1>
  <p class="text-lg max-w-xl mb-6 text-gray-300">A passionate developer crafting experiences through code, design, and innovation.</p>
  <button class="px-6 py-3 bg-blue-500 rounded-xl font-medium hover:bg-blue-600 transition">View My Work</button>
</section>
""",
    "description": "Hero section for portfolio homepage"
})

vector_db.append({
    "content": """
<!-- Contact Form -->
<section class="max-w-lg mx-auto bg-[#111827] p-8 rounded-2xl shadow-lg border border-gray-800">
  <h2 class="text-2xl font-semibold text-white mb-6">Let’s Connect</h2>
  <form class="flex flex-col space-y-4">
    <input type="text" placeholder="Name" class="p-3 rounded-lg bg-[#1f2937] text-gray-200 border border-gray-700 focus:ring-2 focus:ring-blue-500 outline-none" />
    <input type="email" placeholder="Email" class="p-3 rounded-lg bg-[#1f2937] text-gray-200 border border-gray-700 focus:ring-2 focus:ring-blue-500 outline-none" />
    <textarea placeholder="Your message..." rows="4" class="p-3 rounded-lg bg-[#1f2937] text-gray-200 border border-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"></textarea>
    <button class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">Send Message</button>
  </form>
</section>
""",
    "description": "Dark-themed contact form layout"
})

vector_db.append({
    "content": """
:root {
  --accent: #3b82f6;
  --bg-dark: #0f172a;
  --text-light: #e2e8f0;
}

* {
  box-sizing: border-box;
  font-family: "Inter", sans-serif;
}

body {
  background: var(--bg-dark);
  color: var(--text-light);
  margin: 0;
  padding: 0;
}

button {
  transition: all 0.2s ease;
}

button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(59,130,246,0.3);
}
""",
    "description": "Global modern UI theme variables and hover effects"
})


SYSTEM_PROMPT = """You are CloudX, a god-tier coding assistant.
Think deeply **only for technical tasks** (coding, math, logic), but never reveal internal reasoning.
For casual chat, reply naturally.

For web design tasks:
- Use modern layouts (flexbox/grid).
- Maintain consistent padding/margins (1–2rem).
- Use `Inter`, `Poppins`, or `JetBrains Mono` fonts.
- Always apply hover states to buttons and cards.
- Ensure responsiveness and balanced spacing.


RULES FOR GUI DESIGN:
- Prefer minimal, functional layouts.
- Avoid unnecessary wrappers or divs.
- Use modern styling and spacing.
- Use semantic names for IDs/classes.
- Prioritize readability and maintainability.
- Make components reusable.
- Show only what is necessary.


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
