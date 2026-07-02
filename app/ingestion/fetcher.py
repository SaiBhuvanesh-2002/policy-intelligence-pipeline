"""Fetch and extract text from public policy sources.

Live fetching is gated behind PIP_ALLOW_NETWORK_FETCH so the demo is fully
deterministic by default. The shipped seed corpus is the guaranteed source.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import settings


@dataclass
class FetchedDocument:
    url: str
    title: str
    text: str
    content_type: str


def _extract_html(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled"
    text = "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )
    return f"{title}\n\n{text}"


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def fetch_url(url: str, timeout: float = 20.0) -> FetchedDocument:
    """Fetch a public document. Raises if network fetching is disabled."""
    if not settings.allow_network_fetch:
        raise RuntimeError(
            "Live network fetch is disabled. Set PIP_ALLOW_NETWORK_FETCH=true to enable, "
            "or ingest from the shipped seed corpus."
        )
    headers = {"User-Agent": "PolicyIntelligencePipeline/0.1 (+demo)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            text = _extract_pdf(resp.content)
            title = url.rsplit("/", 1)[-1]
        else:
            text = _extract_html(resp.text)
            title = text.split("\n", 1)[0][:200]
        return FetchedDocument(url=url, title=title, text=text, content_type=ctype)
