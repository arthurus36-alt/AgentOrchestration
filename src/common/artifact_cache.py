"""Local artifact download cache with digest validation."""

import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Optional, Union


class ArtifactCacheError(ValueError):
    """Raised when cached or downloaded artifact content is invalid."""


class ArtifactDownloadCache:
    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get_path(
        self,
        artifact_id: str,
        expected_digest: str,
        download: Callable[[Path], None],
    ) -> Path:
        digest = _normalize_sha256(expected_digest)
        artifact_path = self._artifact_path(artifact_id)
        metadata_path = self._metadata_path(artifact_id)

        if self._is_valid_hit(artifact_path, metadata_path, digest):
            return artifact_path

        self._evict(artifact_path, metadata_path)
        tmp_path = artifact_path.with_suffix(artifact_path.suffix + ".tmp")
        self._evict(tmp_path, None)

        try:
            download(tmp_path)
            actual_digest = _sha256_file(tmp_path)
        except Exception:
            self._evict(tmp_path, None)
            raise

        if actual_digest != digest:
            self._evict(tmp_path, None)
            raise ArtifactCacheError(
                "downloaded artifact digest mismatch: "
                f"expected sha256:{digest}, got sha256:{actual_digest}"
            )

        os.replace(tmp_path, artifact_path)
        tmp_metadata_path = metadata_path.with_suffix(
            metadata_path.suffix + ".tmp"
        )
        tmp_metadata_path.write_text(
            json.dumps(
                {
                    "algorithm": "sha256",
                    "digest": digest,
                    "size": artifact_path.stat().st_size,
                }
            )
        )
        os.replace(tmp_metadata_path, metadata_path)
        return artifact_path

    def _artifact_path(self, artifact_id: str) -> Path:
        return self.root / f"{artifact_id}.bin"

    def _metadata_path(self, artifact_id: str) -> Path:
        return self.root / f"{artifact_id}.meta.json"

    def _is_valid_hit(
        self,
        artifact_path: Path,
        metadata_path: Path,
        expected_digest: str,
    ) -> bool:
        if not artifact_path.is_file() or not metadata_path.is_file():
            return False

        try:
            metadata = json.loads(metadata_path.read_text())
        except (json.JSONDecodeError, OSError):
            return False

        if metadata.get("algorithm") != "sha256":
            return False
        if metadata.get("digest") != expected_digest:
            return False
        if metadata.get("size") != artifact_path.stat().st_size:
            return False

        actual_digest = _sha256_file(artifact_path)
        return actual_digest == expected_digest

    def _evict(self, artifact_path: Path, metadata_path: Optional[Path]) -> None:
        try:
            artifact_path.unlink()
        except FileNotFoundError:
            pass
        if metadata_path:
            try:
                metadata_path.unlink()
            except FileNotFoundError:
                pass


def _normalize_sha256(digest: str) -> str:
    if digest.startswith("sha256:"):
        return digest[7:]
    return digest


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
