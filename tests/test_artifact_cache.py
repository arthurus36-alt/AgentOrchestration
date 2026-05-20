import hashlib
import json

import pytest

from src.common.artifact_cache import ArtifactCacheError, ArtifactDownloadCache


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_cache_hit_verifies_digest_before_reuse(tmp_path):
    cache = ArtifactDownloadCache(tmp_path)
    content = b"approved artifact"
    downloads = 0

    def download(path):
        nonlocal downloads
        downloads += 1
        path.write_bytes(content)

    first_path = cache.get_path("artifact.tar", sha256(content), download)
    second_path = cache.get_path("artifact.tar", sha256(content), download)

    assert first_path == second_path
    assert second_path.read_bytes() == content
    assert downloads == 1


def test_corrupt_cache_entry_is_evicted_and_redownloaded(tmp_path):
    cache = ArtifactDownloadCache(tmp_path)
    content = b"approved artifact"
    downloads = 0

    def download(path):
        nonlocal downloads
        downloads += 1
        path.write_bytes(content)

    artifact_path = cache.get_path("artifact.tar", sha256(content), download)
    artifact_path.write_bytes(b"corrupt artifact")

    repaired_path = cache.get_path("artifact.tar", sha256(content), download)

    assert repaired_path == artifact_path
    assert repaired_path.read_bytes() == content
    assert downloads == 2


def test_partial_file_is_evicted_and_redownloaded(tmp_path):
    cache = ArtifactDownloadCache(tmp_path)
    content = b"complete artifact payload"
    downloads = 0

    def download(path):
        nonlocal downloads
        downloads += 1
        path.write_bytes(content)

    artifact_path = cache.get_path("artifact.tar", sha256(content), download)
    
    # Tamper with the size by truncating without changing metadata
    with open(artifact_path, "wb") as f:
        f.write(content[:10])

    repaired_path = cache.get_path("artifact.tar", sha256(content), download)

    assert repaired_path == artifact_path
    assert repaired_path.read_bytes() == content
    assert downloads == 2

def test_downloaded_artifact_digest_mismatch_raises_error(tmp_path):
    cache = ArtifactDownloadCache(tmp_path)
    
    def download(path):
        path.write_bytes(b"bad content")
        
    with pytest.raises(ArtifactCacheError, match="digest mismatch"):
        cache.get_path("artifact.tar", sha256(b"good content"), download)
