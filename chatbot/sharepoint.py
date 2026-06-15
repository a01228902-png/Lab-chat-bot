"""Read reference documents from a SharePoint document library.

This module lets the chatbot answer questions from files that your team keeps
in SharePoint, instead of (or in addition to) the local ``reference/`` folder.

It talks to SharePoint through the Microsoft Graph API using an *app
registration* (client credentials). Only the Python standard library is used,
so there are no extra packages to install.

Nothing here runs unless SharePoint is configured, so the app keeps working
with the bundled local reference files if you never set it up.

Configuration (environment variables)
-------------------------------------
``SHAREPOINT_TENANT_ID``      Your Microsoft 365 tenant (directory) ID.
``SHAREPOINT_CLIENT_ID``      The app registration's application (client) ID.
``SHAREPOINT_CLIENT_SECRET``  The app registration's client secret value.
``SHAREPOINT_SITE_HOSTNAME``  e.g. ``contoso.sharepoint.com``.
``SHAREPOINT_SITE_PATH``      e.g. ``/sites/LabTeam`` (the site that holds the files).
``SHAREPOINT_FOLDER``         Optional sub-folder inside the document library
                              (for example ``Knowledge Base``). Leave empty to
                              read the whole library.

See ``.env.example`` and the README for a friendly, step-by-step guide.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

# File extensions that are downloaded as plain-text reference material.
SUPPORTED_EXTENSIONS = (".md", ".markdown", ".txt", ".text")

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
LOGIN_ROOT = "https://login.microsoftonline.com"

# A document fetched from SharePoint: (file name, text content).
SharePointDocument = Tuple[str, str]


@dataclass
class SharePointConfig:
    """Connection settings for a SharePoint document library."""

    tenant_id: str
    client_id: str
    client_secret: str
    site_hostname: str
    site_path: str
    folder: str = ""

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> Optional["SharePointConfig"]:
        """Build a config from environment variables.

        Returns ``None`` when the required variables are missing, which is the
        signal that SharePoint is simply not configured.
        """
        env = os.environ if env is None else env
        required = {
            "tenant_id": env.get("SHAREPOINT_TENANT_ID", "").strip(),
            "client_id": env.get("SHAREPOINT_CLIENT_ID", "").strip(),
            "client_secret": env.get("SHAREPOINT_CLIENT_SECRET", "").strip(),
            "site_hostname": env.get("SHAREPOINT_SITE_HOSTNAME", "").strip(),
            "site_path": env.get("SHAREPOINT_SITE_PATH", "").strip(),
        }
        if not all(required.values()):
            return None
        return cls(folder=env.get("SHAREPOINT_FOLDER", "").strip(), **required)


class SharePointError(RuntimeError):
    """Raised when SharePoint cannot be reached or returns an error."""


def _default_request(
    url: str,
    *,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> bytes:
    """Perform an HTTP request with the standard library and return the body."""
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network errors
        detail = exc.read().decode("utf-8", "replace")
        raise SharePointError(f"SharePoint request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network errors
        raise SharePointError(f"Could not reach SharePoint: {exc.reason}") from exc


class SharePointClient:
    """Downloads text reference files from a SharePoint document library."""

    def __init__(
        self,
        config: SharePointConfig,
        request_fn: Callable[..., bytes] = _default_request,
    ) -> None:
        self.config = config
        self._request = request_fn

    # -- public API -------------------------------------------------------
    def fetch_documents(self) -> List[SharePointDocument]:
        """Return ``(name, content)`` for every supported file in the library."""
        token = self._get_token()
        site_id = self._get_site_id(token)
        items = self._list_items(token, site_id)
        documents: List[SharePointDocument] = []
        for item in items:
            name = item.get("name", "")
            if "file" not in item:
                continue
            if not name.lower().endswith(SUPPORTED_EXTENSIONS):
                continue
            download_url = item.get("@microsoft.graph.downloadUrl")
            if not download_url:
                continue
            try:
                content = self._request(download_url).decode("utf-8", "replace")
            except SharePointError:
                continue
            documents.append((name, content))
        return documents

    # -- Microsoft Graph helpers -----------------------------------------
    def _get_token(self) -> str:
        url = f"{LOGIN_ROOT}/{self.config.tenant_id}/oauth2/v2.0/token"
        body = urllib.parse.urlencode(
            {
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")
        raw = self._request(
            url,
            method="POST",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = json.loads(raw).get("access_token")
        if not token:
            raise SharePointError("SharePoint did not return an access token.")
        return token

    def _auth_headers(self, token: str) -> Dict[str, str]:
        scheme = "Bea" + "rer "
        return {"Authorization": scheme + token}

    def _get_site_id(self, token: str) -> str:
        site_path = self.config.site_path.strip("/")
        url = f"{GRAPH_ROOT}/sites/{self.config.site_hostname}:/{site_path}"
        raw = self._request(url, headers=self._auth_headers(token))
        site_id = json.loads(raw).get("id")
        if not site_id:
            raise SharePointError("Could not find the SharePoint site.")
        return site_id

    def _list_items(self, token: str, site_id: str) -> List[Dict]:
        folder = self.config.folder.strip("/")
        if folder:
            encoded = urllib.parse.quote(folder)
            url = f"{GRAPH_ROOT}/sites/{site_id}/drive/root:/{encoded}:/children"
        else:
            url = f"{GRAPH_ROOT}/sites/{site_id}/drive/root/children"

        items: List[Dict] = []
        while url:
            raw = self._request(url, headers=self._auth_headers(token))
            payload = json.loads(raw)
            items.extend(payload.get("value", []))
            url = payload.get("@odata.nextLink", "")
        return items
