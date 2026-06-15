"""Flask web application that serves the chatbot UI and chat API."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from chatbot import ChatbotEngine, SharePointClient, SharePointConfig

BASE_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = Path(os.environ.get("REFERENCE_DIR", BASE_DIR / "reference"))


def _load_dotenv(path: Path) -> None:
    """Load simple ``KEY=value`` pairs from a ``.env`` file if it exists.

    This keeps setup friendly for non-technical users: copy ``.env.example`` to
    ``.env``, fill in the blanks, and run the app. Existing environment
    variables always win, so nothing is overwritten.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")


def _build_sources():
    """Return the external document sources that are configured.

    Currently this is SharePoint. When the SharePoint environment variables are
    not set, an empty list is returned and the chatbot falls back to the local
    reference files, so the app always works out of the box.
    """
    config = SharePointConfig.from_env()
    if config is None:
        return []
    return [SharePointClient(config)]


def create_app(reference_dir: str | Path = REFERENCE_DIR, sources=None) -> Flask:
    """Application factory so the app can be configured for tests."""
    app = Flask(__name__)
    if sources is None:
        sources = _build_sources()
    app.config["KNOWLEDGE_SOURCE"] = "SharePoint" if sources else "local files"
    app.config["ENGINE"] = ChatbotEngine(reference_dir, sources=sources)

    @app.route("/")
    def index():
        return render_template(
            "index.html", knowledge_source=app.config["KNOWLEDGE_SOURCE"]
        )

    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "A non-empty 'message' field is required."}), 400

        answer = app.config["ENGINE"].query(message)
        return jsonify(
            {
                "reply": answer.text,
                "source": answer.source,
                "score": round(answer.score, 4),
                "found": answer.found,
            }
        )

    @app.route("/api/health")
    def health():
        engine: ChatbotEngine = app.config["ENGINE"]
        return jsonify(
            {
                "status": "ok",
                "documents": len(engine.documents),
                "knowledge_source": app.config["KNOWLEDGE_SOURCE"],
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
