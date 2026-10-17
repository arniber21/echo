"""Import local evidence through the same API as the browser, optionally analyze it."""

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--title", default="Local evidence case")
    parser.add_argument("--analyze", choices=("auto", "mock", "live"))
    parser.add_argument(
        "--default", action="store_true", help="Open this case on the home page"
    )
    options = parser.parse_args()
    port = int(os.environ.get("REWIND_API_PORT", "8000"))
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120) as client:
        with ExitStack() as stack:
            files = [
                ("files", (path.name, stack.enter_context(path.open("rb"))))
                for path in options.files
            ]
            response = client.post(
                "/api/cases", data={"title": options.title}, files=files
            )
        response.raise_for_status()
        case = response.json()
        case_id = case["case_id"]
        print(f"Created case {case_id}", flush=True)
        if options.analyze:
            response = client.post(
                f"/api/cases/{case_id}/analyze", json={"mode": options.analyze}
            )
            response.raise_for_status()
            job = response.json()
            deadline = time.monotonic() + 1800
            previous = None
            while job["status"] not in ("completed", "failed"):
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        "Analysis is still running; inspect the case in the browser"
                    )
                state = (job["stage"], job["progress"])
                if state != previous:
                    print(f"{job['progress']:3d}% {job['stage']}", flush=True)
                    previous = state
                time.sleep(1)
                response = client.get(f"/api/jobs/{job['job_id']}")
                response.raise_for_status()
                job = response.json()
            if job["status"] == "failed":
                raise RuntimeError(job["error"] or "Analysis failed")
            case = client.get(f"/api/cases/{case_id}").raise_for_status().json()
            print(
                f"Completed: {len(case['analysis']['events'])} events, {len(case['analysis']['missing_evidence'])} evidence gaps",
                flush=True,
            )
        if options.default:
            target = ROOT / "data/workspace.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps({"case_id": case_id}) + "\n")
            temporary.replace(target)
        web_port = os.environ.get("REWIND_WEB_PORT", "3000")
        print(f"http://127.0.0.1:{web_port}/?case={case_id}", flush=True)


if __name__ == "__main__":
    main()
