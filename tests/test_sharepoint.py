"""Tests for the SharePoint document source and engine ingestion.

Network calls are replaced with a small fake so the tests run offline.
"""

import json

import pytest

from chatbot.engine import ChatbotEngine
from chatbot.sharepoint import (
    SharePointClient,
    SharePointConfig,
    SharePointError,
)


def make_config(folder=""):
    return SharePointConfig(
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
        site_hostname="contoso.sharepoint.com",
        site_path="/sites/LabTeam",
        folder=folder,
    )


class FakeGraph:
    """A tiny in-memory stand-in for the Microsoft Graph + login endpoints."""

    def __init__(self, files):
        # files: list of (name, content); content also acts as download body.
        self.files = files
        self.calls = []

    def request(self, url, *, method="GET", data=None, headers=None, timeout=30.0):
        self.calls.append((method, url, headers))
        if "oauth2/v2.0/token" in url:
            return json.dumps({"access_token": "fake-token"}).encode("utf-8")
        if url.endswith(":/sites/LabTeam") or "/sites/contoso" in url:
            return json.dumps({"id": "site-123"}).encode("utf-8")
        if "/children" in url:
            value = [
                {
                    "name": name,
                    "file": {},
                    "@microsoft.graph.downloadUrl": f"https://dl/{name}",
                }
                for name, _ in self.files
            ]
            return json.dumps({"value": value}).encode("utf-8")
        if url.startswith("https://dl/"):
            name = url.rsplit("/", 1)[-1]
            for fname, content in self.files:
                if fname == name:
                    return content.encode("utf-8")
        raise AssertionError(f"unexpected url: {url}")


def test_config_from_env_returns_none_when_unset():
    assert SharePointConfig.from_env({}) is None


def test_config_from_env_reads_values():
    config = SharePointConfig.from_env(
        {
            "SHAREPOINT_TENANT_ID": "t",
            "SHAREPOINT_CLIENT_ID": "c",
            "SHAREPOINT_CLIENT_SECRET": "s",
            "SHAREPOINT_SITE_HOSTNAME": "contoso.sharepoint.com",
            "SHAREPOINT_SITE_PATH": "/sites/LabTeam",
            "SHAREPOINT_FOLDER": "Knowledge Base",
        }
    )
    assert config is not None
    assert config.tenant_id == "t"
    assert config.folder == "Knowledge Base"


def test_config_from_env_missing_field_returns_none():
    assert (
        SharePointConfig.from_env(
            {
                "SHAREPOINT_TENANT_ID": "t",
                "SHAREPOINT_CLIENT_ID": "c",
                # missing secret
                "SHAREPOINT_SITE_HOSTNAME": "contoso.sharepoint.com",
                "SHAREPOINT_SITE_PATH": "/sites/LabTeam",
            }
        )
        is None
    )


def test_fetch_documents_downloads_supported_files():
    fake = FakeGraph(
        [
            ("faq.md", "## Hours\n\nThe lab is open 9 to 5."),
            ("notes.txt", "Some plain text notes."),
            ("ignore.docx", "binary should be skipped"),
        ]
    )
    client = SharePointClient(make_config(), request_fn=fake.request)
    documents = client.fetch_documents()
    names = {name for name, _ in documents}
    assert names == {"faq.md", "notes.txt"}


def test_token_is_sent_as_bearer_header():
    fake = FakeGraph([("faq.md", "hello world")])
    client = SharePointClient(make_config(), request_fn=fake.request)
    client.fetch_documents()
    graph_calls = [
        h for _, url, h in fake.calls if url.startswith("https://graph.microsoft.com") and h
    ]
    assert graph_calls
    auth_header = graph_calls[0]["Authorization"]
    assert auth_header.startswith("Bearer ")
    assert auth_header.endswith("fake-token")


def test_missing_token_raises():
    def no_token(url, **kwargs):
        return json.dumps({}).encode("utf-8")

    client = SharePointClient(make_config(), request_fn=no_token)
    with pytest.raises(SharePointError):
        client.fetch_documents()


def test_engine_indexes_sharepoint_documents():
    fake = FakeGraph([("faq.md", "## Hours\n\nThe lab is open Monday to Friday.")])
    client = SharePointClient(make_config(), request_fn=fake.request)
    engine = ChatbotEngine("/nonexistent-dir", sources=[client])
    answer = engine.query("When is the lab open?")
    assert answer.found is True
    assert "Monday to Friday" in answer.text
    assert answer.source == "faq.md"


def test_engine_survives_failing_source(tmp_path):
    (tmp_path / "local.md").write_text(
        "## Local\n\nThe local file answer about microscopes.", encoding="utf-8"
    )

    class BrokenSource:
        def fetch_documents(self):
            raise RuntimeError("boom")

    engine = ChatbotEngine(tmp_path, sources=[BrokenSource()])
    answer = engine.query("Tell me about microscopes")
    assert answer.found is True
    assert "microscopes" in answer.text
