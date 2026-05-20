"""Digest-gated container image signing and promotion helpers."""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set, Tuple


class ImagePublishError(ValueError):
    """Raised when a container image cannot be safely signed or promoted."""


@dataclass(frozen=True)
class ContainerImageReference:
    repository: str
    digest: str
    tag: Optional[str] = None

    @classmethod
    def parse(cls, reference: str) -> "ContainerImageReference":
        if "@" not in reference:
            raise ImagePublishError(
                "image reference must include an immutable digest"
            )

        repository_part, digest = reference.rsplit("@", 1)
        if not repository_part:
            raise ImagePublishError(
                "image reference must include a repository"
            )
        if not digest or ":" not in digest:
            raise ImagePublishError("image digest must include an algorithm")

        algorithm, encoded = digest.split(":", 1)
        if not algorithm or not encoded:
            raise ImagePublishError(
                "image digest must include an algorithm and value"
            )

        repository, tag = _split_repository_tag(repository_part)
        if not repository:
            raise ImagePublishError(
                "image reference must include a repository"
            )
        return cls(repository=repository, tag=tag, digest=digest)

    @property
    def digest_reference(self) -> str:
        return f"{self.repository}@{self.digest}"


@dataclass(frozen=True)
class ImageSignature:
    digest_reference: str
    signature: str


class ScanApprovalRegistry:
    def __init__(self):
        self._approved_digests: Set[str] = set()

    def approve(self, image_reference: str) -> str:
        digest_reference = ContainerImageReference.parse(
            image_reference
        ).digest_reference
        self._approved_digests.add(digest_reference)
        return digest_reference

    def is_approved(self, image_reference: str) -> bool:
        digest_reference = ContainerImageReference.parse(
            image_reference
        ).digest_reference
        return digest_reference in self._approved_digests


class DigestPublishGate:
    def __init__(
        self,
        approvals: ScanApprovalRegistry,
        signer: Callable[[str], str],
        promoter: Optional[Callable[[str, str], None]] = None,
    ):
        self._approvals = approvals
        self._signer = signer
        self._promoter = promoter or (
            lambda digest_reference, target_tag: None
        )
        self._signatures: Dict[str, ImageSignature] = {}

    def sign(self, image_reference: str) -> ImageSignature:
        image = ContainerImageReference.parse(image_reference)
        digest_reference = image.digest_reference
        if not self._approvals.is_approved(digest_reference):
            raise ImagePublishError(
                "image digest has not passed vulnerability scan"
            )

        signature = self._signer(digest_reference)
        record = ImageSignature(
            digest_reference=digest_reference,
            signature=signature,
        )
        self._signatures[digest_reference] = record
        return record

    def promote(self, image_reference: str, target_tag: str) -> str:
        image = ContainerImageReference.parse(image_reference)
        digest_reference = image.digest_reference
        if not self._approvals.is_approved(digest_reference):
            raise ImagePublishError(
                "cannot promote digest without scan approval"
            )
        if not target_tag or "@" in target_tag:
            raise ImagePublishError(
                "target tag must be a mutable tag name only"
            )

        if digest_reference not in self._signatures:
            self.sign(digest_reference)

        self._promoter(digest_reference, target_tag)
        return digest_reference


def _split_repository_tag(repository_part: str) -> Tuple[str, Optional[str]]:
    last_slash = repository_part.rfind("/")
    last_colon = repository_part.rfind(":")
    if last_colon > last_slash:
        repository = repository_part[:last_colon]
        tag = repository_part[last_colon + 1:]
        if not tag:
            raise ImagePublishError("image tag must not be empty")
        return repository, tag
    return repository_part, None
