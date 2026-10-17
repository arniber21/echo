"""Explicit, cached place searches against a configurable Photon instance."""

import asyncio
import hashlib
import json
import math
import time
from collections import OrderedDict
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


class Place(BaseModel):
    label: str
    latitude: float
    longitude: float


def fetch_places(base_url: str, query: str) -> list[Place]:
    request = Request(
        base_url.rstrip("/")
        + "/api/?"
        + urlencode({"q": query, "limit": 5, "lang": "en"}),
        headers={
            "User-Agent": "Rewind/0.1 (+https://github.com/arniber21/echo)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=8) as response:
        raw = response.read(131073)
    if len(raw) > 131072:
        raise ValueError("Oversized geocoder response")
    payload = json.loads(raw)
    places = []
    for feature in payload.get("features", [])[:5]:
        try:
            longitude, latitude = feature["geometry"]["coordinates"][:2]
            longitude, latitude = float(longitude), float(latitude)
            if not (
                math.isfinite(latitude)
                and math.isfinite(longitude)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                continue
            properties = feature["properties"]
            parts = [
                properties.get(key)
                for key in ("name", "street", "city", "state", "country")
            ]
            label = ", ".join(
                dict.fromkeys(
                    part for part in parts if isinstance(part, str) and part.strip()
                )
            )
            if label:
                places.append(
                    Place(label=label[:200], latitude=latitude, longitude=longitude)
                )
        except (KeyError, TypeError, ValueError):
            continue
    return places


class PlaceSearch:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.lock = asyncio.Lock()
        self.last_request: float | None = None
        self.cache: OrderedDict[str, tuple[float, list[Place]]] = OrderedDict()

    async def search(self, query: str) -> list[Place]:
        if not self.base_url:
            raise HTTPException(
                503, "Map search is unavailable. You can enter a location manually."
            )
        key = hashlib.sha256(query.casefold().encode()).hexdigest()
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < 21600:
            self.cache.move_to_end(key)
            return cached[1]
        if self.lock.locked():
            raise HTTPException(429, "Wait a moment before searching again.")
        async with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < 21600:
                self.cache.move_to_end(key)
                return cached[1]
            # Reject bursts instead of creating an unbounded queue of public requests.
            if (
                self.last_request is not None
                and time.monotonic() - self.last_request < 1
            ):
                raise HTTPException(429, "Wait a moment before searching again.")
            self.last_request = time.monotonic()
            try:
                places = await asyncio.to_thread(fetch_places, self.base_url, query)
            except (
                URLError,
                TimeoutError,
                OSError,
                ValueError,
                TypeError,
                AttributeError,
            ):
                raise HTTPException(
                    503, "Map search is unavailable. You can enter a location manually."
                ) from None
            self.cache[key] = (time.monotonic(), places)
            self.cache.move_to_end(key)
            while len(self.cache) > 256:
                self.cache.popitem(last=False)
            return places


def location_router(base_url: str) -> APIRouter:
    router = APIRouter()
    service = PlaceSearch(base_url)

    @router.get("/api/locations/search", response_model=list[Place])
    async def search(q: str = Query(min_length=3, max_length=240)):
        query = " ".join(q.split())
        if len(query) < 3:
            raise HTTPException(422, "Enter at least three characters to search.")
        return await service.search(query)

    return router
