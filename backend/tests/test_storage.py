"""Storage adapter contracts for local files and Supabase Storage."""

from __future__ import annotations

import pandas as pd

from services import storage


class _FakeBucket:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    def upload(self, path: str, file: bytes, file_options: dict[str, str]) -> None:
        assert file_options == {"content-type": "text/csv", "upsert": "false"}
        if path in self.uploaded:
            raise RuntimeError("object already exists")
        self.uploaded[path] = file

    def download(self, path: str) -> bytes:
        return self.uploaded[path]

    def remove(self, paths: list[str]) -> None:
        for path in paths:
            self.uploaded.pop(path, None)


class _FakeStorageApi:
    def __init__(self, bucket: _FakeBucket) -> None:
        self._bucket = bucket

    def from_(self, bucket_name: str) -> _FakeBucket:
        assert bucket_name == "datasets"
        return self._bucket


class _FakeSupabaseClient:
    def __init__(self) -> None:
        self.bucket = _FakeBucket()
        self.storage = _FakeStorageApi(self.bucket)


def test_local_storage_keeps_duplicate_filenames_as_distinct_datasets(tmp_path) -> None:
    """A second upload must not overwrite an earlier same-named dataset."""
    local = storage.LocalDatasetStorage(tmp_path)

    first_key, _, _ = local.save_csv_bytes(7, "sales.csv", b"amount\n10\n")
    second_key, _, _ = local.save_csv_bytes(7, "sales.csv", b"amount\n20\n")

    assert first_key != second_key
    assert local.load_dataframe(first_key)["amount"].tolist() == [10]
    assert local.load_dataframe(second_key)["amount"].tolist() == [20]


def test_supabase_storage_uses_opaque_unique_keys() -> None:
    """Cloud storage must keep duplicate names and never expose a public URL."""
    client = _FakeSupabaseClient()
    remote = storage.SupabaseDatasetStorage(client, "datasets")

    first_key, _, _ = remote.save_csv_bytes(7, "sales.csv", b"amount\n10\n")
    second_key, _, _ = remote.save_csv_bytes(7, "sales.csv", b"amount\n20\n")

    assert first_key.startswith("projects/7/")
    assert second_key.startswith("projects/7/")
    assert first_key != second_key
    assert client.bucket.uploaded[first_key] == b"amount\n10\n"
    assert client.bucket.uploaded[second_key] == b"amount\n20\n"
    assert remote.load_dataframe(first_key).equals(pd.DataFrame({"amount": [10]}))
