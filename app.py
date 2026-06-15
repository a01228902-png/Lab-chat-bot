"""Flask web application that serves the chatbot UI and chat API."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from chatbot import ChatbotEngine

BASE_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = Path(os.environ.get("REFERENCE_DIR", BASE_DIR / "reference"))


def create_app(reference_dir: str | Path = REFERENCE_DIR) -> Flask:
    """Application factory so the app can be configured for tests."""
    app = Flask(__name__)
    app.config["ENGINE"] = ChatbotEngine(reference_dir)

    @app.route("/")
    def index():
        return render_template("index.html")

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
        return jsonify({"status": "ok", "documents": len(engine.documents)})

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
