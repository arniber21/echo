#!/usr/bin/env python3
"""Upload prepared incident clips as separate cases without requesting analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from prepare_local_incident import digest


def request_json(url: str, *, data: bytes | None = None, boundary: str = "") -> object:
    headers = (
        {"Content-Type": f"multipart/form-data; boundary={boundary}"} if data else {}
    )
    with urlopen(Request(url, data=data, headers=headers), timeout=120) as response:
        return json.load(response)


def upload(base_url: str, title: str, metadata: dict, path: Path) -> dict:
    boundary = f"rewind-{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in (("title", title), ("metadata", json.dumps([metadata]))):
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{path.name}"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
    )
    chunks.extend((path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()))
    result = request_json(
        f"{base_url}/api/cases", data=b"".join(chunks), boundary=boundary
    )
    if not isinstance(result, dict) or not isinstance(result.get("case_id"), str):
        raise TypeError("Upload response did not contain a case ID")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    directory = args.directory.expanduser().resolve(strict=True)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    existing = request_json(f"{args.base_url}/api/cases")
    if not isinstance(existing, list):
        parser.error("Case list response was invalid")
    # Recover an interrupted run by matching the unique title AND exact video hash.
    for clip in manifest["clips"]:
        path = directory / clip["filename"]
        if path.parent != directory or digest(path) != clip["sha256"]:
            parser.error(
                "A prepared clip path or SHA-256 no longer matches the manifest"
            )
        title = f"Additional footage · {clip['clip_id'].replace('-', ' ')}"
        case = next(
            (
                item
                for item in existing
                if item["title"] == title
                and any(
                    media["sha256"] == clip["sha256"] for media in item["media_files"]
                )
            ),
            None,
        )
        if case is None:
            # Do not automatically retry POST: after an ambiguous network failure,
            # rerun and recover from GET before deciding whether to create a case.
            case = upload(args.base_url, title, clip["source_metadata"], path)
            existing.append(case)
        clip["ingested_case_id"] = case["case_id"]
        clip["case_url"] = f"http://127.0.0.1:3000/?case={case['case_id']}"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Ready for analysis: {clip['filename']} → {case['case_id']}", flush=True)


if __name__ == "__main__":
    main()
