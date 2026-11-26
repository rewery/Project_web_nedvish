"""Conservative importer for user-supplied property listing URLs.

No CAPTCHA/proxy/stealth bypass. Fetch only pages whose automated access is permitted.
Extracts JSON-LD, OpenGraph, and visible text into the existing listing schema.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "HomerPropertyResearchBot/0.1 (+listing-import; respectful)"
TIMEOUT = (5, 15)
MAX_BYTES = 2_000_000


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.jsonld = []
        self._jsonld = False
        self._script_parts = []
        self._title = False
        self._title_parts = []
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content"):
                self.meta[key] = attrs["content"].strip()
        elif tag.lower() == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._jsonld = True
            self._script_parts = []
        elif tag.lower() == "title":
            self._title = True

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._jsonld:
            raw = "".join(self._script_parts).strip()
            if raw:
                try:
                    self.jsonld.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            self._jsonld = False
        elif tag.lower() == "title":
            self._title = False

    def handle_data(self, data):
        if self._jsonld:
            self._script_parts.append(data)
        if self._title:
            self._title_parts.append(data)
        stripped = data.strip()
        if stripped:
            self._text_parts.append(stripped)

    @property
    def title(self):
        return " ".join(self._title_parts).strip()


def _safe_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL должен быть http/https и содержать имя хоста.")
    if parsed.username or parsed.password:
        raise ValueError("URL с логином/паролем запрещён.")
    host = parsed.hostname.lower()
    if host in ("localhost",) or host.endswith(".local"):
        raise ValueError("Локальные адреса запрещены.")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("Не удалось определить адрес сайта.") from exc
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise ValueError("Запросы к локальным/служебным IP запрещены.")
    return url


def _robots_allows(url: str, session: requests.Session) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = session.get(robots_url, timeout=TIMEOUT, allow_redirects=False)
    except requests.RequestException:
        # Fail closed when permission rules cannot be checked.
        return False
    if response.status_code == 404:
        return True
    if response.status_code != 200:
        return False
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(response.text.splitlines())
    return rp.can_fetch(USER_AGENT, url) and rp.can_fetch("*", url)


def _walk_jsonld(value):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            yield from _walk_jsonld(graph)
        for key, child in value.items():
            if key not in ("@graph",):
                yield from _walk_jsonld(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_jsonld(child)


def _first(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _flatten_address(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [value.get(k) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")]
        return ", ".join(str(p) for p in parts if p)
    return None


def _extract_offer(obj):
    offer = obj.get("offers")
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    return offer if isinstance(offer, dict) else {}


def extract_listing_from_html(html: str, url: str, city: str | None = None) -> dict:
    parser = PageParser()
    parser.feed(html)
    objects = [o for root in parser.jsonld for o in _walk_jsonld(root)]
    # Prefer real-estate/product/offer objects, but tolerate generic JSON-LD.
    objects.sort(key=lambda o: 0 if any(t in str(o.get("@type", "")).lower()
                                      for t in ("realestate", "apartment", "product", "offer")) else 1)
    obj = objects[0] if objects else {}
    offer = _extract_offer(obj)
    address = _flatten_address(_first(obj.get("address"), offer.get("address")))
    geo = obj.get("geo") if isinstance(obj.get("geo"), dict) else {}
    title = _first(obj.get("name"), parser.meta.get("og:title"), parser.meta.get("twitter:title"), parser.title)
    description = _first(obj.get("description"), parser.meta.get("og:description"), parser.meta.get("description"))
    image = _first(obj.get("image"), parser.meta.get("og:image"))
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")

    price = _first(obj.get("price"), offer.get("price"), offer.get("lowPrice"),
                    parser.meta.get("product:price:amount"))
    currency = _first(obj.get("priceCurrency"), offer.get("priceCurrency"),
                      parser.meta.get("product:price:currency"))
    area = _first(obj.get("floorSize"), obj.get("area"), obj.get("size"))
    if isinstance(area, dict):
        area = _first(area.get("value"), area.get("size"))
    rooms = _first(obj.get("numberOfRooms"), obj.get("rooms"))
    floor = _first(obj.get("floorLevel"), obj.get("floor"))
    raw_text = " ".join(parser._text_parts)
    # Conservative fallback: only explicit labels in page text.
    if price is None:
        match = re.search(r"(?:цена|стоимость)\s*[:—-]?\s*([\d\s\xa0]+)\s*(?:₽|руб)", raw_text, re.I)
        if match:
            price = re.sub(r"\D", "", match.group(1))
    if area is None:
        match = re.search(r"(?:площадь|общая площадь)\s*[:—-]?\s*(\d+(?:[.,]\d+)?)\s*(?:м²|м2|кв\.?\s*м)", raw_text, re.I)
        if match:
            area = match.group(1).replace(",", ".")
    if rooms is None:
        match = re.search(r"(\d+)\s*[- ]?комнатн", raw_text, re.I)
        if match:
            rooms = match.group(1)
    if floor is None:
        match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*(?:этаж|эт\.?|$)", raw_text, re.I)
        if match:
            floor, total_floors = match.group(1), match.group(2)
        else:
            total_floors = None
    else:
        total_floors = _first(obj.get("numberOfFloors"), obj.get("floorCount"))
    try:
        price = float(re.sub(r"[^\d.]", "", str(price).replace(",", "."))) if price is not None else None
    except ValueError:
        price = None
    try:
        area = float(re.sub(r"[^\d.]", "", str(area).replace(",", "."))) if area is not None else None
    except ValueError:
        area = None
    try:
        rooms = int(float(rooms)) if rooms is not None else None
    except (ValueError, TypeError):
        rooms = None
    try:
        floor = int(floor) if floor is not None else None
    except (ValueError, TypeError):
        floor = None
    try:
        total_floors = int(total_floors) if total_floors is not None else None
    except (ValueError, TypeError):
        total_floors = None
    return {
        "id": url,
        "title": title,
        "city": city or _first(obj.get("addressLocality"), (obj.get("address") or {}).get("addressLocality") if isinstance(obj.get("address"), dict) else None),
        "price": price,
        "price_currency": currency or "RUB",
        "area": area,
        "rooms": rooms,
        "floor": floor,
        "total_floors": total_floors,
        "address": address,
        "description": description,
        "image_url": image,
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "source_url": url,
        "source_domain": urlparse(url).netloc,
        "raw_data": {"extraction": "json-ld/opengraph/text-fallback", "title": parser.title},
    }


def fetch_listing_url(url: str, city: str | None = None) -> dict:
    _safe_public_url(url)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    if not _robots_allows(url, session):
        raise PermissionError("robots.txt не разрешает сбор либо его правила не удалось проверить.")
    try:
        response = session.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
        _safe_public_url(response.url)  # validate redirect destination, too
        if response.status_code != 200:
            raise ValueError(f"Сайт вернул HTTP {response.status_code}.")
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            raise ValueError("URL не вернул HTML.")
        body = response.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(body) > MAX_BYTES:
            raise ValueError("Страница превышает допустимые 2 МБ.")
        html = body.decode(response.encoding or "utf-8", errors="replace")
    except requests.RequestException as exc:
        raise ValueError(f"Ошибка загрузки страницы: {exc.__class__.__name__}") from exc
    return extract_listing_from_html(html, response.url, city)
