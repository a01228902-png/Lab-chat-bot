# Lab-chat-bot

GDC TME Lab Chat bot — a small **online chatbot** that answers basic questions
from a set of reference files.

It runs as a simple Flask web app with a browser chat UI. Answers are retrieved
directly from local reference documents using a lightweight TF-IDF
similarity model, so **no external AI service or API key is required**.

## How it works

1. Every `.md` / `.txt` file in the [`reference/`](reference) folder is read and
   split into passages.
2. When you ask a question, the engine ranks the passages with TF-IDF cosine
   similarity and returns the best match (along with the source file).
3. If nothing is relevant enough, the bot says it couldn't find an answer
   instead of guessing.

## Project layout

```
app.py              Flask app: serves the chat UI and the /api/chat endpoint
chatbot/engine.py   Pure-Python TF-IDF retrieval engine (no extra dependencies)
reference/          Reference documents the bot answers from (edit these!)
templates/          HTML for the chat page
static/             CSS and JavaScript for the chat UI
tests/              pytest tests for the engine and the API
```

## Getting started

Requires Python 3.9+.

```bash
# 1. Install dependencies (a virtual environment is recommended)
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Open the chat UI
#    http://localhost:5000
```

Set `PORT` to use a different port, or `REFERENCE_DIR` to point at a different
folder of reference files:

```bash
PORT=8080 REFERENCE_DIR=/path/to/docs python app.py
```

## Adding your own knowledge

Drop additional `.md` or `.txt` files into the `reference/` folder (restart the
app to pick them up). Using Markdown headings as short questions works well, for
example:

```markdown
## What time does the lab close?

The lab closes at 5:00 PM on weekdays.
```

## API

`POST /api/chat`

```json
// request
{ "message": "What are the lab hours?" }

// response
{
  "reply": "...answer text...",
  "source": "faq.md",
  "score": 0.35,
  "found": true
}
```

`GET /api/health` returns `{ "status": "ok", "documents": <count> }`.

## Running the tests

```bash
pip install -r requirements.txt pytest
pytest
```
