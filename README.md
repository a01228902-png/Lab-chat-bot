# Lab-chat-bot

GDC TME Lab Chat bot — a small **online chatbot** that answers basic questions
from a set of reference files.

It runs as a simple Flask web app with a browser chat UI. Answers are retrieved
directly from reference documents using a lightweight TF-IDF similarity model,
so **no external AI service or API key is required**.

The reference documents can live in two places:

* the local [`reference/`](reference) folder (works out of the box), **and/or**
* a **SharePoint** document library your team already uses (optional).

## How it works

1. Every `.md` / `.txt` file in the [`reference/`](reference) folder — and, if
   configured, in your **SharePoint** document library — is read and split into
   passages.
2. When you ask a question, the engine ranks the passages with TF-IDF cosine
   similarity and returns the best match (along with the source file).
3. If nothing is relevant enough, the bot says it couldn't find an answer
   instead of guessing.

## Project layout

```
app.py                Flask app: serves the chat UI and the /api/chat endpoint
chatbot/engine.py     Pure-Python TF-IDF retrieval engine (no extra dependencies)
chatbot/sharepoint.py Reads reference files from a SharePoint document library
reference/            Local reference documents the bot answers from (edit these!)
templates/            HTML for the chat page
static/               CSS and JavaScript for the chat UI
.env.example          Copy to .env to connect SharePoint (optional)
tests/                pytest tests for the engine, the API and SharePoint
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

## Storing the knowledge in SharePoint (optional)

You can keep the documents the bot answers from in a SharePoint document
library, so non-technical team members can update the knowledge by simply
editing files in SharePoint — no code required.

**What you need (ask your Microsoft 365 / SharePoint admin):**

1. In the Microsoft Entra (Azure AD) admin center, create an **app
   registration**.
2. Give it the **`Sites.Read.All`** *application* permission and grant admin
   consent.
3. Create a **client secret** for the app registration and copy its value.
4. Note your **tenant (directory) ID**, the app's **client ID**, your
   SharePoint **hostname** (for example `contoso.sharepoint.com`) and the
   **site path** that holds the files (for example `/sites/LabTeam`).

**Connect the chatbot:**

1. Copy the example settings file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` in any text editor and paste in the values from above.
3. Start the app as usual (`python app.py`). The header and `/api/health` will
   now say it is answering from **SharePoint**.

Only `.md` and `.txt` files in the library are used. If SharePoint is
unreachable or not configured, the bot automatically falls back to the local
`reference/` folder, so it always works.

> The `.env` file holds secrets and is already listed in `.gitignore` — never
> commit it.

## Adding your own knowledge

Drop additional `.md` or `.txt` files into the `reference/` folder (or your
SharePoint library) and restart the app to pick them up. Using Markdown
headings as short questions works well, for example:

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

`GET /api/health` returns
`{ "status": "ok", "documents": <count>, "knowledge_source": "SharePoint" | "local files" }`.

## Running the tests

```bash
pip install -r requirements.txt pytest
pytest
```
