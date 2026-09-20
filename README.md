# Translingo — live multi-user chat with on-the-fly translation (Flask)

Any two (or more) people can open this page, each pick their own language,
and chat in real time — every message is translated on the way to each
other participant, using Ollama Cloud (`gemma4:31b-cloud`).

## How it works

- One person clicks **Start a new chat** and gets a 6-character room code.
- They share that code with the other person, who enters it under
  **Join room**.
- Both are now in the same Socket.IO room. When either sends a message,
  the server translates it into every *other* participant's chosen
  language before delivering it — the sender always sees their own
  message untranslated.
- The original text is always available via "show original" under a
  translated message.

## Project structure

- `app.py` — Flask + Flask-SocketIO server. Handles room creation/joining
  and calls Ollama Cloud from `translate()`.
- `templates/index.html` — the whole UI (landing + chat) in one page.
- `requirements.txt` — Python dependencies.
- `Procfile` — start command for Render/Heroku-style platforms.

The Ollama API key lives only in the `OLLAMA_API_KEY` environment
variable — never in the code or in the browser.

## Run it locally

```
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OLLAMA_API_KEY=your_key_here   # Windows PowerShell: $env:OLLAMA_API_KEY="your_key_here"
python app.py
```

Open http://localhost:5000 in two different browser windows (or two
different browsers) to simulate two people, and try chatting between them
with different languages selected.

## Deploy on Render

1. Push this folder to a GitHub repository.
2. On Render, create a new **Web Service** from that repo, environment
   **Python 3**.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn --worker-class eventlet -w 1 app:app`
   (this is also what the included `Procfile` specifies)
5. Add an environment variable: `OLLAMA_API_KEY` = your key from
   ollama.com. Optionally also set `SECRET_KEY` to a random string.
6. Deploy. Once live, open the URL Render gives you from two devices (or
   two browser tabs/profiles) and try creating a room on one and joining
   it from the other.

## Notes

- Room and participant data is kept in memory in `app.py` — it resets if
  the server restarts, and won't stay in sync across multiple server
  instances. Fine for a PoC; for production at scale you'd move that
  state into something shared like Redis (Flask-SocketIO supports a Redis
  message queue for exactly this).
- `eventlet` is required for Flask-SocketIO to handle concurrent
  connections efficiently under gunicorn — it's already wired into both
  `app.py` and the `Procfile`.
