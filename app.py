import eventlet
eventlet.monkey_patch()

import os
import uuid
import requests
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")
OLLAMA_MODEL = "gemma4:31b-cloud"
OLLAMA_URL = "https://ollama.com/api/generate"

LANGS = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "hi": "Hindi",
    "ja": "Japanese",
    "de": "German",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ar": "Arabic",
}

# In-memory room state: { room_code: { sid: {"name": str, "lang": str} } }
rooms = {}


def translate(text, from_lang, to_lang):
    """Translate text from one language to another via Ollama Cloud."""
    if from_lang == to_lang:
        return text

    if not OLLAMA_API_KEY:
        raise RuntimeError("Server is missing OLLAMA_API_KEY")

    prompt = (
        f"Translate the following {LANGS.get(from_lang, from_lang)} text into "
        f"{LANGS.get(to_lang, to_lang)}. Reply with only the translation itself — "
        f"no explanation, no quotes, no labels.\n\nText: {text}"
    )

    resp = requests.post(
        OLLAMA_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OLLAMA_API_KEY}",
        },
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    translated = (data.get("response") or "").strip()

    if not translated:
        raise RuntimeError("Model returned an empty response")

    return translated


def room_participants(room_code):
    return [
        {"name": u["name"], "lang": u["lang"]}
        for u in rooms.get(room_code, {}).values()
    ]


@app.route("/")
def index():
    return render_template("index.html", langs=LANGS)


@socketio.on("create_room")
def handle_create_room(data):
    room_code = uuid.uuid4().hex[:6].upper()
    rooms[room_code] = {}
    _join_room(room_code, data)


@socketio.on("join_room_request")
def handle_join_room(data):
    room_code = (data.get("room") or "").strip().upper()
    if room_code not in rooms:
        emit("join_error", {"error": "That room code doesn't exist."})
        return
    _join_room(room_code, data)


def _join_room(room_code, data):
    name = (data.get("name") or "Guest").strip()[:30] or "Guest"
    lang = data.get("lang") if data.get("lang") in LANGS else "en"
    sid = request.sid

    join_room(room_code)
    rooms.setdefault(room_code, {})[sid] = {"name": name, "lang": lang}

    emit("joined", {
        "room": room_code,
        "name": name,
        "lang": lang,
        "participants": room_participants(room_code),
    })
    emit("participant_update", {"participants": room_participants(room_code)}, room=room_code)
    emit("system_message", {"text": f"{name} joined the chat."}, room=room_code, include_self=False)


@socketio.on("send_message")
def handle_send_message(data):
    sid = request.sid
    room_code = data.get("room")
    text = (data.get("text") or "").strip()

    if not room_code or room_code not in rooms or sid not in rooms[room_code] or not text:
        return

    sender = rooms[room_code][sid]

    for recipient_sid, recipient in list(rooms[room_code].items()):
        if recipient_sid == sid:
            emit("new_message", {
                "from": sender["name"],
                "from_lang": sender["lang"],
                "text": text,
                "original": text,
                "translated": False,
                "self": True,
            }, room=sid)
            continue

        try:
            translated_text = translate(text, sender["lang"], recipient["lang"])
            emit("new_message", {
                "from": sender["name"],
                "from_lang": sender["lang"],
                "text": translated_text,
                "original": text,
                "translated": sender["lang"] != recipient["lang"],
                "self": False,
            }, room=recipient_sid)
        except Exception as err:
            emit("new_message", {
                "from": sender["name"],
                "from_lang": sender["lang"],
                "text": text,
                "original": text,
                "translated": False,
                "self": False,
                "error": str(err),
            }, room=recipient_sid)


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    for room_code, users in list(rooms.items()):
        if sid in users:
            name = users[sid]["name"]
            del users[sid]
            if users:
                emit("participant_update", {"participants": room_participants(room_code)}, room=room_code)
                emit("system_message", {"text": f"{name} left the chat."}, room=room_code)
            else:
                del rooms[room_code]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
