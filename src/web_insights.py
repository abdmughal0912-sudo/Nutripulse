from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


USER_AGENT = "NutriPulseResearchBot/4.2 (+local nutrition decision-support prototype)"
MAX_RESPONSE_BYTES = 1_500_000
MAX_EXTRACTED_CHARACTERS = 9_000
MAX_PARAGRAPHS = 18
MAX_REDIRECTS = 3

TRUSTED_SOURCES = [
    {
        "name": "World Health Organization · Healthy diet",
        "domain": "who.int",
        "url": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "description": "Global healthy-diet principles and public-health recommendations.",
        "reviewed": "2026-08-28",
        "fallback_summary": [
            "A healthy dietary pattern emphasizes varied minimally processed foods, including vegetables, fruit, legumes, nuts and whole grains.",
            "Free sugars, sodium, saturated fat and industrial trans fat should be limited within an individualized eating pattern.",
        ],
    },
    {
        "name": "NIH Office of Dietary Supplements · Fact sheets",
        "domain": "ods.od.nih.gov",
        "url": "https://ods.od.nih.gov/factsheets/list-all/",
        "description": "Evidence-oriented vitamin, mineral and supplement fact-sheet index.",
        "reviewed": "2026-08-28",
        "fallback_summary": [
            "The NIH Office of Dietary Supplements publishes evidence summaries for vitamins, minerals and other supplement ingredients.",
            "Supplement decisions should account for dose, interactions, laboratory confirmation and professional assessment.",
        ],
    },
    {
        "name": "USDA MyPlate · What is MyPlate?",
        "domain": "myplate.gov",
        "url": "https://www.myplate.gov/eat-healthy/what-is-myplate",
        "description": "Public nutrition guidance and food-group planning resources.",
        "reviewed": "2026-08-28",
        "fallback_summary": [
            "MyPlate organizes meals around fruits, vegetables, grains, protein foods and dairy or suitable alternatives.",
            "The food-group model is general guidance and must be adapted for allergies, culture, medical conditions and energy requirements.",
        ],
    },
    {
        "name": "NHS · Healthy eating tips",
        "domain": "nhs.uk",
        "url": "https://www.nhs.uk/live-well/eat-well/food-guidelines-and-food-labels/8-tips-for-healthy-eating/",
        "description": "Practical healthy-eating guidance from the UK National Health Service.",
        "reviewed": "2026-08-28",
        "fallback_summary": [
            "The NHS healthy-eating guidance emphasizes dietary variety, fibre-rich foods, suitable hydration and moderation of foods high in salt, sugar and saturated fat.",
            "Individual clinical conditions can require advice from an appropriately qualified professional.",
        ],
    },
]


class WebInsightError(ValueError):
    """Raised when a requested page cannot be fetched or safely extracted."""


def allowed_domains() -> tuple[str, ...]:
    defaults = {source["domain"] for source in TRUSTED_SOURCES}
    configured = {
        value.strip().lower().lstrip(".")
        for value in os.getenv("NUTRIPULSE_SCRAPER_DOMAINS", "").split(",")
        if value.strip()
    }
    return tuple(sorted(defaults | configured))


def validate_source_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if not cleaned:
        raise WebInsightError("Enter a source URL.")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise WebInsightError("Only http:// and https:// source URLs are supported.")
    if parsed.username or parsed.password:
        raise WebInsightError("Credentials are not allowed in source URLs.")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise WebInsightError("The source URL does not contain a valid hostname.")
    if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains()):
        raise WebInsightError(
            "This domain is not on the trusted-source allowlist. Allowed domains: "
            + ", ".join(allowed_domains())
        )
    port = parsed.port
    if port not in {None, 80, 443}:
        raise WebInsightError("Only standard web ports 80 and 443 are allowed.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def validate_public_resource_url(url: str) -> str:
    """Validate any public HTTP(S) resource while retaining SSRF protections."""
    cleaned = str(url or "").strip()
    if not cleaned:
        raise WebInsightError("Enter a public web page or API URL.")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise WebInsightError("Only http:// and https:// resource URLs are supported.")
    if parsed.username or parsed.password:
        raise WebInsightError("Credentials are not allowed inside the URL. Use the session-only API header fields.")
    if not parsed.hostname:
        raise WebInsightError("The resource URL does not contain a valid hostname.")
    try:
        literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal_ip = None
    if literal_ip and any((
        literal_ip.is_private, literal_ip.is_loopback, literal_ip.is_link_local,
        literal_ip.is_multicast, literal_ip.is_reserved, literal_ip.is_unspecified,
    )):
        raise WebInsightError("Private, local and reserved network addresses are blocked.")
    if parsed.port not in {None, 80, 443}:
        raise WebInsightError("Only standard web ports 80 and 443 are allowed.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _safe_request_headers(headers: dict[str, str] | None) -> dict[str, str]:
    result = {
        "User-Agent": "Mozilla/5.0 (compatible; NutriPulse/4.2; nutrition research)",
        "Accept": "application/json,text/csv,application/xml,text/xml,text/html,text/plain;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.8",
    }
    blocked = {"host", "cookie", "content-length", "transfer-encoding", "connection", "proxy-authorization"}
    for raw_name, raw_value in (headers or {}).items():
        name = str(raw_name).strip()
        value = str(raw_value).strip()
        if not name or not value:
            continue
        if name.lower() in blocked or not re.fullmatch(r"[A-Za-z0-9-]{1,80}", name):
            raise WebInsightError(f"The API header {name or '(blank)'} is not allowed.")
        if "\r" in value or "\n" in value or len(value) > 4000:
            raise WebInsightError(f"The API header {name} contains an invalid value.")
        result[name] = value
    return result


def _redact_structured_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 6:
        return "…"
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 60:
                output["…"] = "Additional keys omitted"
                break
            key_text = str(key)
            if any(word in key_text.lower() for word in ("password", "secret", "token", "api_key", "apikey", "authorization")):
                output[key_text] = "[redacted]"
            else:
                output[key_text] = _redact_structured_value(item, depth=depth + 1)
        return output
    if isinstance(value, list):
        return [_redact_structured_value(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:1500]
    return value


def _json_preview_lines(value: Any, prefix: str = "response", limit: int = 30) -> list[str]:
    lines: list[str] = []

    def walk(item: Any, path: str, depth: int) -> None:
        if len(lines) >= limit or depth > 4:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if len(lines) >= limit:
                    break
                walk(child, f"{path}.{key}", depth + 1)
        elif isinstance(item, list):
            for index, child in enumerate(item[:10]):
                if len(lines) >= limit:
                    break
                walk(child, f"{path}[{index}]", depth + 1)
        else:
            lines.append(f"{path}: {str(item)[:500]}")

    walk(value, prefix, 0)
    return lines or ["The API returned an empty JSON response."]


def extract_public_payload(payload: bytes, url: str, content_type: str) -> dict[str, Any]:
    """Convert JSON, CSV, XML, text or HTML into one safe preview contract."""
    lowered = content_type.lower()
    text = payload.decode("utf-8", errors="replace")
    if "json" in lowered or text.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WebInsightError(f"The API response was not valid JSON: {exc}") from exc
        preview = _redact_structured_value(parsed)
        paragraphs = _json_preview_lines(preview)
        record_count = len(parsed) if isinstance(parsed, list) else 1
        if isinstance(parsed, dict):
            for candidate in ("results", "items", "data", "records"):
                if isinstance(parsed.get(candidate), list):
                    record_count = len(parsed[candidate])
                    break
        return {
            "title": f"API response · {urlsplit(url).hostname or 'public source'}",
            "description": "Structured JSON was fetched from the supplied public API endpoint.",
            "resource_type": "json-api",
            "data_preview": preview,
            "record_count": record_count,
            "paragraphs": paragraphs,
        }
    if "html" in lowered or "<html" in text[:1000].lower():
        article = extract_article_html(payload, url)
        article["resource_type"] = "html-page"
        return article
    if "xml" in lowered or text.lstrip().startswith("<?xml"):
        soup = BeautifulSoup(text, "xml")
        lines = [_clean_text(node.get_text(" ", strip=True)) for node in soup.find_all()]
        paragraphs = [line for line in lines if len(line) >= 20][:MAX_PARAGRAPHS]
        if not paragraphs:
            raise WebInsightError("No useful XML content could be extracted.")
        return {
            "title": f"XML response · {urlsplit(url).hostname or 'public source'}",
            "description": "Structured XML preview from the supplied public endpoint.",
            "resource_type": "xml-api",
            "paragraphs": paragraphs,
            "record_count": len(paragraphs),
        }
    lines = [_clean_text(line) for line in text.splitlines()]
    paragraphs = [line[:900] for line in lines if len(line) >= 5][:MAX_PARAGRAPHS]
    if not paragraphs:
        raise WebInsightError("The public resource returned no usable text.")
    return {
        "title": f"Public data response · {urlsplit(url).hostname or 'public source'}",
        "description": "Text or delimited-data preview from the supplied public endpoint.",
        "resource_type": "text-data",
        "paragraphs": paragraphs,
        "record_count": len(paragraphs),
    }


def _assert_public_resolution(url: str) -> None:
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebInsightError(f"The trusted source hostname could not be resolved: {exc}") from exc
    if not addresses:
        raise WebInsightError("The trusted source hostname did not resolve to an address.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
            raise WebInsightError("The source resolved to a private or reserved network address and was blocked.")


def _robots_policy(session: requests.Session, url: str, timeout: tuple[float, float]) -> str:
    parsed = urlsplit(url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        response = session.get(
            robots_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException:
        return "unavailable"
    if response.status_code == 404:
        return "not-published"
    if response.status_code != 200:
        return f"unavailable-http-{response.status_code}"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise WebInsightError("The website's robots policy does not allow this page to be fetched.")
    return "allowed"


def _clean_text(value: str) -> str:
    return " ".join(str(value).split())


def extract_article_html(html_content: str | bytes, url: str) -> dict[str, Any]:
    """Extract a compact, attributable article preview from already-fetched HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "form", "nav", "footer", "aside"]):
        element.decompose()

    title_node = soup.select_one('meta[property="og:title"]')
    title = _clean_text(title_node.get("content", "")) if title_node else ""
    if not title:
        heading = soup.find("h1") or soup.find("title")
        title = _clean_text(heading.get_text(" ", strip=True)) if heading else "Untitled source"

    description_node = soup.select_one('meta[name="description"], meta[property="og:description"]')
    description = _clean_text(description_node.get("content", "")) if description_node else ""

    content_root = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs: list[str] = []
    seen: set[str] = set()
    characters = 0
    for node in content_root.find_all(["h2", "h3", "p", "li"]):
        text = _clean_text(node.get_text(" ", strip=True))
        if len(text) < 45 or text in seen:
            continue
        text = text[:900]
        if characters + len(text) > MAX_EXTRACTED_CHARACTERS:
            break
        seen.add(text)
        paragraphs.append(text)
        characters += len(text)
        if len(paragraphs) >= MAX_PARAGRAPHS:
            break

    if not paragraphs and description:
        paragraphs = [description]
    if not paragraphs:
        raise WebInsightError("No useful article text could be extracted from this page.")

    parsed = urlsplit(url)
    word_count = sum(len(paragraph.split()) for paragraph in paragraphs)
    return {
        "title": title[:240],
        "description": description[:600],
        "url": url,
        "domain": parsed.hostname or "",
        "paragraphs": paragraphs,
        "paragraph_count": len(paragraphs),
        "word_count": word_count,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": "Extracted source preview for research; verify the original page before applying health information.",
    }


def fetch_trusted_article(url: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    """Fetch and extract one allowlisted public page with redirect and size controls."""
    current_url = validate_source_url(url)
    timeout = (min(4.0, timeout_seconds), max(4.0, timeout_seconds))
    session = requests.Session()
    session.trust_env = True
    _assert_public_resolution(current_url)
    robots_policy = _robots_policy(session, current_url, timeout)

    for _ in range(MAX_REDIRECTS + 1):
        _assert_public_resolution(current_url)
        try:
            response = session.get(
                current_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.8",
                },
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise WebInsightError(f"The trusted source could not be reached: {exc}") from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            destination = response.headers.get("Location", "")
            response.close()
            if not destination:
                raise WebInsightError("The source returned a redirect without a destination.")
            current_url = validate_source_url(urljoin(current_url, destination))
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code in {403, 429}:
                fallback = next((source for source in TRUSTED_SOURCES if source["url"] == current_url), None)
                if fallback and fallback.get("fallback_summary"):
                    response.close()
                    paragraphs = list(fallback["fallback_summary"])
                    return {
                        "title": fallback["name"],
                        "description": fallback["description"],
                        "url": current_url,
                        "domain": urlsplit(current_url).hostname or "",
                        "paragraphs": paragraphs,
                        "paragraph_count": len(paragraphs),
                        "word_count": sum(len(item.split()) for item in paragraphs),
                        "record_count": len(paragraphs),
                        "resource_type": "curated-offline-summary",
                        "live_access": False,
                        "live_http_status": response.status_code,
                        "source_reviewed": fallback.get("reviewed", ""),
                        "robots_policy": robots_policy,
                        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "disclaimer": (
                            "The official site blocked live extraction, so NutriPulse displayed its bundled, "
                            "attributed summary. Open the original source and verify it before clinical use."
                        ),
                    }
            raise WebInsightError(f"The trusted source returned HTTP {response.status_code}.") from exc
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            response.close()
            raise WebInsightError("The source is not an HTML page.")
        payload = bytearray()
        for chunk in response.iter_content(chunk_size=32_768):
            payload.extend(chunk)
            if len(payload) > MAX_RESPONSE_BYTES:
                response.close()
                raise WebInsightError("The page exceeded the 1.5 MB safe extraction limit.")
        response.close()
        article = extract_article_html(bytes(payload), current_url)
        article["robots_policy"] = robots_policy
        return article

    raise WebInsightError("The source exceeded the safe redirect limit.")


def fetch_public_resource(
    url: str,
    *,
    request_headers: dict[str, str] | None = None,
    timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    """Fetch a public GET endpoint or page with SSRF, redirect and size controls."""
    current_url = validate_public_resource_url(url)
    timeout = (min(5.0, timeout_seconds), max(5.0, timeout_seconds))
    headers = _safe_request_headers(request_headers)
    session = requests.Session()
    session.trust_env = True

    for _ in range(MAX_REDIRECTS + 1):
        _assert_public_resolution(current_url)
        try:
            response = session.get(
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise WebInsightError(f"The public resource could not be reached: {exc}") from exc
        if response.status_code in {301, 302, 303, 307, 308}:
            destination = response.headers.get("Location", "")
            response.close()
            if not destination:
                raise WebInsightError("The public resource redirected without a destination.")
            current_url = validate_public_resource_url(urljoin(current_url, destination))
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = response.status_code
            response.close()
            raise WebInsightError(f"The public resource returned HTTP {status_code}.") from exc
        payload = bytearray()
        for chunk in response.iter_content(chunk_size=32_768):
            payload.extend(chunk)
            if len(payload) > MAX_RESPONSE_BYTES:
                response.close()
                raise WebInsightError("The public response exceeded the 1.5 MB safe extraction limit.")
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        status_code = response.status_code
        response.close()
        result = extract_public_payload(bytes(payload), current_url, content_type)
        result.setdefault("url", current_url)
        result.setdefault("domain", urlsplit(current_url).hostname or "")
        result.setdefault("paragraph_count", len(result.get("paragraphs", [])))
        result.setdefault("word_count", sum(len(str(item).split()) for item in result.get("paragraphs", [])))
        result.setdefault("record_count", result.get("paragraph_count", 0))
        result.setdefault("description", "Public resource preview")
        result["content_type"] = content_type.split(";", 1)[0].strip().lower()
        result["http_status"] = status_code
        result["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result["live_access"] = True
        result["disclaimer"] = (
            "Public data preview only. Verify the source, schema, licensing and clinical suitability before use."
        )
        return result
    raise WebInsightError("The public resource exceeded the safe redirect limit.")


def article_to_markdown(article: dict[str, Any]) -> bytes:
    lines = [
        f"# {article.get('title', 'Web insight')}",
        "",
        f"Source: {article.get('url', '')}",
        f"Fetched: {article.get('fetched_at', '')}",
        "",
    ]
    if article.get("description"):
        lines.extend([str(article["description"]), ""])
    lines.extend(str(paragraph) for paragraph in article.get("paragraphs", []))
    lines.extend(["", "---", str(article.get("disclaimer", ""))])
    return "\n\n".join(lines).encode("utf-8")
