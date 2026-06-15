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

## Deploying online

The development server above is fine for trying things out, but for a real
"online" deployment that other people can reach, run the app with a production
WSGI server. The app already exposes a WSGI entry point as `app:app`, and a
[`Procfile`](Procfile) is included so most hosting platforms work out of the box.

**Run a production server yourself** (any always-on Linux server / VM):

```bash
pip install -r requirements.txt gunicorn
gunicorn app:app --bind 0.0.0.0:8000
# the chat UI is now at http://<your-server>:8000
```

Put it behind a reverse proxy (e.g. Nginx) or your organisation's load balancer
to add HTTPS and a friendly URL.

**Deploy to a hosting platform** (Render, Railway, Heroku, Azure App Service,
Google Cloud Run, etc.):

1. Push this repository to GitHub (or your git host of choice).
2. Create a new **web service** on your platform of choice and point it at the
   repo. The bundled `Procfile`
   (`web: gunicorn app:app --bind 0.0.0.0:$PORT`) tells the platform how to
   start the app; the platform supplies the `PORT`.
3. In the platform's **environment variables / secrets** settings, add the same
   `SHAREPOINT_*` values from [`.env.example`](.env.example) (don't upload your
   `.env` file). Leave them unset to run from the local `reference/` files.
4. Deploy. Open the URL the platform gives you and visit `/api/health` to
   confirm it is up and which `knowledge_source` is active.

> Most platforms install `gunicorn` automatically when it is listed in your
> dependencies. If yours does not, add `gunicorn` to `requirements.txt`.

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
