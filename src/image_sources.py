from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from PIL import Image, UnidentifiedImageError


MAX_REMOTE_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REMOTE_IMAGE_PIXELS = 30_000_000
MAX_REMOTE_REDIRECTS = 3
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_USER_AGENT = "NutriPulseVision/3.2 (+public-image nutrition analyzer)"


class RemoteImageError(ValueError):
    """Raised when a public image cannot be retrieved safely."""


def validate_public_image_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if not cleaned:
        raise RemoteImageError("Paste a direct public image URL.")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteImageError("Only http:// and https:// image URLs are supported.")
    if parsed.username or parsed.password:
        raise RemoteImageError("Credentials are not allowed in an image URL.")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise RemoteImageError("The image URL does not contain a valid hostname.")
    if parsed.port not in {None, 80, 443}:
        raise RemoteImageError("Only standard web ports 80 and 443 are allowed.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _assert_public_resolution(url: str) -> None:
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RemoteImageError(f"The image hostname could not be resolved: {exc}") from exc
    if not addresses:
        raise RemoteImageError("The image hostname did not resolve to an address.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast,
                ip.is_reserved, ip.is_unspecified)):
            raise RemoteImageError("Private, local and reserved network addresses are blocked.")


def _validate_image(payload: bytes, content_type: str) -> dict[str, Any]:
    if not payload:
        raise RemoteImageError("The downloaded image was empty.")
    try:
        with Image.open(BytesIO(payload)) as image:
            detected_format = str(image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise RemoteImageError("The URL did not return a valid JPG, PNG or WebP image.") from exc
    if detected_format not in {"JPEG", "PNG", "WEBP"}:
        raise RemoteImageError("Only JPG, PNG and WebP image data is supported.")
    if width <= 0 or height <= 0 or width * height > MAX_REMOTE_IMAGE_PIXELS:
        raise RemoteImageError("The image dimensions exceed the safe 30-megapixel limit.")
    return {
        "content_type": content_type,
        "detected_format": detected_format,
        "width": width,
        "height": height,
        "size_bytes": len(payload),
    }


def fetch_public_image(url: str, timeout_seconds: float = 12.0) -> tuple[bytes, dict[str, Any]]:
    """Download one direct public image with SSRF, redirect and size safeguards."""
    current_url = validate_public_image_url(url)
    timeout = (min(4.0, timeout_seconds), max(4.0, timeout_seconds))
    session = requests.Session()
    session.trust_env = True

    for _ in range(MAX_REMOTE_REDIRECTS + 1):
        _assert_public_resolution(current_url)
        try:
            response = session.get(
                current_url,
                headers={
                    "User-Agent": IMAGE_USER_AGENT,
                    "Accept": "image/jpeg,image/png,image/webp;q=0.9",
                },
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise RemoteImageError(f"The public image could not be reached: {exc}") from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            destination = response.headers.get("Location", "")
            response.close()
            if not destination:
                raise RemoteImageError("The image server redirected without a destination.")
            current_url = validate_public_image_url(urljoin(current_url, destination))
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            response.close()
            raise RemoteImageError(f"The image server returned HTTP {response.status_code}.") from exc

        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in SUPPORTED_IMAGE_TYPES:
            response.close()
            raise RemoteImageError("The URL must point directly to a JPG, PNG or WebP image.")
        try:
            declared_size = int(response.headers.get("Content-Length", "0") or 0)
        except ValueError:
            declared_size = 0
        if declared_size > MAX_REMOTE_IMAGE_BYTES:
            response.close()
            raise RemoteImageError("The remote image exceeds the 10 MB limit.")

        payload = bytearray()
        for chunk in response.iter_content(chunk_size=64_000):
            payload.extend(chunk)
            if len(payload) > MAX_REMOTE_IMAGE_BYTES:
                response.close()
                raise RemoteImageError("The remote image exceeds the 10 MB limit.")
        response.close()
        metadata = _validate_image(bytes(payload), content_type)
        metadata.update({"url": current_url, "domain": urlsplit(current_url).hostname or ""})
        return bytes(payload), metadata

    raise RemoteImageError("The image URL exceeded the safe redirect limit.")
