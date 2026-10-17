import asyncio
import io

import pytest
from fastapi import HTTPException, UploadFile

from rewind.config import Settings
from rewind.uploads import ingest


def test_rejected_media_names_only_the_safe_basename_and_removes_staged_bytes(tmp_path):
    upload = UploadFile(
        filename="/private/source/broken\n.mp4", file=io.BytesIO(b"not video")
    )
    settings = Settings(_env_file=None, data_dir=tmp_path)
    with pytest.raises(HTTPException) as captured:
        asyncio.run(ingest(upload, tmp_path, settings))
    assert captured.value.status_code == 415
    assert captured.value.detail.startswith("broken.mp4: Unsupported media content.")
    assert "/private/source" not in captured.value.detail
    assert "\n" not in captured.value.detail
    assert list(tmp_path.iterdir()) == []


def test_per_file_error_names_are_bounded_and_keep_the_original_status(tmp_path):
    upload = UploadFile(
        filename="C:\\source\\" + "x" * 250, file=io.BytesIO(b"too large")
    )
    settings = Settings(_env_file=None, data_dir=tmp_path, max_file_bytes=2)
    with pytest.raises(HTTPException) as captured:
        asyncio.run(ingest(upload, tmp_path, settings))
    assert captured.value.status_code == 413
    assert captured.value.detail == "x" * 180 + ": A file exceeds the upload limit."
    assert list(tmp_path.iterdir()) == []
