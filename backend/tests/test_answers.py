"""Reported case responses are versioned evidence, never media observations."""

import asyncio
import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from rewind.analysis.mock import mock_analysis
from rewind.config import Settings
from rewind.main import create_app
from rewind.memory import project_memory
from rewind.models import Analysis, CaseAnswer, Claim, Finding, validate_analysis


def config(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, seed_demo=False)


def photo():
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(output, "JPEG")
    return output.getvalue()


def complete(client, app, url):
    response = client.post(url + "/analyze", json={"mode": "mock"})
    assert response.status_code == 202

    async def wait():
        for _ in range(100):
            job = app.state.store.get_job(response.json()["job_id"])
            if job.status in ("completed", "failed"):
                return job
            await asyncio.sleep(0.01)
        pytest.fail("Analysis did not complete")

    assert client.portal.call(wait).status == "completed"
    return client.get(url).json()


def test_answer_create_edit_restart_and_exact_analysis_snapshots(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        case = client.post(
            "/api/cases", files=[("files", ("view.jpg", photo()))]
        ).json()
        url = "/api/cases/" + case["case_id"]
        case = complete(client, app, url)
        original_analysis, original_memory = case["analysis"], case["memory"]
        request = {
            "question_id": "mock-analysis-required",
            "question_revision": 1,
            "text": "  I recorded this from the opposite corner.  ",
            "respondent": " Witness A ",
            "expected_evidence_revision": 1,
        }
        saved = client.post(url + "/answers", json=request)
        assert saved.status_code == 200
        case = saved.json()
        assert case["evidence_revision"] == 2
        answer = case["answers"][0]
        assert answer["text"] == request["text"].strip()
        assert answer["respondent"] == "Witness A"
        assert answer["question_title"] == "Evidence analysis is required"
        assert case["analysis"] == original_analysis
        assert case["memory"] == original_memory
        assert case["analyzed_answers"] == []
        assert client.post(url + "/answers", json=request).json() == case
        assert (
            client.post(
                url + "/answers", json={**request, "text": "different"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                url + "/answers",
                json={
                    **request,
                    "question_id": "fabricated",
                    "expected_evidence_revision": 2,
                },
            ).status_code
            == 409
        )
        assert (
            client.post(
                url + "/answers",
                json={
                    **request,
                    "question_revision": 2,
                    "expected_evidence_revision": 2,
                },
            ).status_code
            == 409
        )
        assert (
            client.post(url + "/answers", json={**request, "text": "   "}).status_code
            == 422
        )
        analyzed = complete(client, app, url)
        assert analyzed["analyzed_answers"] == [answer]
        assert analyzed["analysis_history"][0]["answers"] == []
        claim = analyzed["analysis"]["summary"][-1]
        assert claim["answer_refs"] == [answer["answer_id"]]
        assert claim["source_refs"] == []
        assert "User-reported" in claim["text"]
        edit = {
            "text": "I was a passenger, not the recorder.",
            "respondent": "Witness A",
            "expected_evidence_revision": 2,
        }
        endpoint = url + "/answers/" + answer["answer_id"]
        edited = client.patch(endpoint, json=edit).json()
        assert edited["evidence_revision"] == 3
        assert edited["answers"][0]["created_at"] == answer["created_at"]
        assert edited["answers"][0]["question_text"] == answer["question_text"]
        assert edited["analyzed_answers"] == [answer]
        assert edited["memory"] == analyzed["memory"]
        assert client.patch(endpoint, json=edit).json() == edited
        assert client.patch(endpoint, json={**edit, "text": "stale"}).status_code == 409
        assert client.patch(url + "/answers/missing", json=edit).status_code == 404
        final = complete(client, app, url)
        assert final["analysis_history"][-1]["answers"] == [answer]
        assert final["analyzed_answers"] == final["answers"]
    with TestClient(create_app(config(tmp_path))) as client:
        assert client.get(url).json() == final


def test_cannot_answer_before_analysis_or_modify_during_analysis(tmp_path):
    gate = asyncio.Event()

    async def paused(case, paths, progress):
        await gate.wait()
        return mock_analysis(case)

    app = create_app(config(tmp_path), paused)
    with TestClient(app) as client:
        case = client.post(
            "/api/cases", files=[("files", ("view.jpg", photo()))]
        ).json()
        url = "/api/cases/" + case["case_id"]
        request = {
            "question_id": "gap",
            "question_revision": 1,
            "text": "context",
            "expected_evidence_revision": 1,
        }
        assert client.post(url + "/answers", json=request).status_code == 409
        stored = app.state.store.get_case(case["case_id"])
        stored.analysis = Analysis(
            events=[],
            summary=[],
            missing_evidence=[
                Finding(
                    id="gap", title="Location", description="Where was this recorded?"
                )
            ],
        )
        stored.analyzed_revision = 1
        app.state.store.save_case(stored)
        saved = client.post(url + "/answers", json=request).json()
        assert client.post(url + "/analyze", json={"mode": "mock"}).status_code == 202
        assert (
            client.post(
                url + "/answers", json={**request, "expected_evidence_revision": 2}
            ).status_code
            == 409
        )
        assert (
            client.patch(
                url + "/answers/" + saved["answers"][0]["answer_id"],
                json={"text": "edit", "expected_evidence_revision": 2},
            ).status_code
            == 409
        )
        client.portal.call(gate.set)


def test_answer_refs_are_validated_and_remain_distinct_in_memory():
    now = datetime.now(UTC)
    answer = CaseAnswer(
        answer_id="answer-1",
        question_id="where",
        question_title="Location",
        question_text="Where?",
        question_revision=1,
        text="At the junction",
        created_at=now,
        updated_at=now,
    )
    value = Analysis(
        events=[],
        summary=[
            Claim(text="The user reports a junction.", answer_refs=[answer.answer_id])
        ],
    )
    with pytest.raises(ValueError, match="Unknown case-answer"):
        validate_analysis(value, [])
    assert validate_analysis(value, [], [answer]) == value
    memory = project_memory(None, value, 2, now)
    assert memory.entries[0].answer_refs == [answer.answer_id]
    value.summary[0].answer_refs = ["answer-2"]
    updated = project_memory(memory, value, 3, now)
    assert len(updated.entries) == 2
    assert updated.entries[0].status == "superseded"
    with pytest.raises(ValueError, match="require"):
        Claim(text="Unsupported assertion")
