import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from rewind import locations
from rewind.config import Settings
from rewind.locations import Place, PlaceSearch, fetch_places
from rewind.main import create_app


def test_search_is_explicit_validated_cached_and_rate_limited(tmp_path, monkeypatch):
    requests = []
    clock = [10.0]
    monkeypatch.setattr(locations, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    def fetch(base_url, query):
        requests.append((base_url, query))
        return [
            Place(label="Market St, San Francisco", latitude=37.77, longitude=-122.42)
        ]

    monkeypatch.setattr(locations, "fetch_places", fetch)
    config = Settings(
        _env_file=None, data_dir=tmp_path, photon_base_url="https://example.test"
    )
    with TestClient(create_app(config)) as client:
        assert (
            client.get("/api/locations/search", params={"q": "  "}).status_code == 422
        )
        first = client.get("/api/locations/search", params={"q": "Market   St"})
        assert first.status_code == 200
        assert first.json()[0]["latitude"] == 37.77
        assert (
            client.get("/api/locations/search", params={"q": "market st"}).json()
            == first.json()
        )
        assert requests == [("https://example.test", "Market St")]
        assert (
            client.get("/api/locations/search", params={"q": "Other place"}).status_code
            == 429
        )
        clock[0] += 1
        assert (
            client.get("/api/locations/search", params={"q": "Other place"}).status_code
            == 200
        )


def test_disabled_and_failed_provider_leave_manual_location_available(monkeypatch):
    with pytest.raises(HTTPException) as disabled:
        asyncio.run(PlaceSearch("").search("Market St"))
    assert disabled.value.status_code == 503

    def fail(*args):
        raise OSError("private-provider-diagnostic")

    monkeypatch.setattr(locations, "fetch_places", fail)
    with pytest.raises(HTTPException) as failed:
        asyncio.run(PlaceSearch("https://example.test").search("Market St"))
    assert failed.value.status_code == 503
    assert "private-provider-diagnostic" not in failed.value.detail


def test_photon_adapter_bounds_and_validates_untrusted_coordinates(monkeypatch):
    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            assert limit == 131073
            return json.dumps(
                {
                    "features": [
                        {
                            "properties": {
                                "name": "Market St",
                                "street": "Market St",
                                "city": "San Francisco",
                            },
                            "geometry": {"coordinates": [-122.42, 37.77]},
                        },
                        {
                            "properties": {"name": "Invalid"},
                            "geometry": {"coordinates": [0, 91]},
                        },
                        {"geometry": {}},
                    ]
                }
            ).encode()

    def open_request(request, timeout):
        captured.append(request)
        assert timeout == 8
        return Response()

    monkeypatch.setattr(locations, "urlopen", open_request)
    assert fetch_places("https://example.test", "Market & 3rd") == [
        Place(label="Market St, San Francisco", latitude=37.77, longitude=-122.42)
    ]
    assert (
        captured[0].full_url
        == "https://example.test/api/?q=Market+%26+3rd&limit=5&lang=en"
    )
    assert "Rewind" in captured[0].get_header("User-agent")
