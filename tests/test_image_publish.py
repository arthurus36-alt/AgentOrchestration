import pytest
from src.common.image_publish import (
    ContainerImageReference,
    DigestPublishGate,
    ImagePublishError,
    ScanApprovalRegistry,
)

def test_rejects_tag_only_references_before_signing():
    approvals = ScanApprovalRegistry()
    signed = []
    gate = DigestPublishGate(approvals, signer=signed.append)

    with pytest.raises(ImagePublishError):
        gate.sign("registry.example.com/team/agent:latest")

    assert signed == []

def test_refuses_to_sign_unapproved_digest():
    approvals = ScanApprovalRegistry()
    signed = []
    gate = DigestPublishGate(approvals, signer=signed.append)

    with pytest.raises(ImagePublishError):
        gate.sign("registry.example.com/team/agent@sha256:abc123")

    assert signed == []

def test_signs_only_digest_reference_after_scan_approval():
    approvals = ScanApprovalRegistry()
    approvals.approve("registry.example.com/team/agent@sha256:abc123")
    
    signed = []
    def dummy_signer(digest):
        signed.append(digest)
        return "dummy_sig"
        
    gate = DigestPublishGate(approvals, signer=dummy_signer)
    record = gate.sign("registry.example.com/team/agent:latest@sha256:abc123")
    
    assert record.digest_reference == "registry.example.com/team/agent@sha256:abc123"
    assert record.signature == "dummy_sig"
    assert signed == ["registry.example.com/team/agent@sha256:abc123"]
    
def test_promote_fails_without_approval():
    approvals = ScanApprovalRegistry()
    gate = DigestPublishGate(approvals, signer=lambda d: "sig")
    
    with pytest.raises(ImagePublishError, match="cannot promote digest without scan approval"):
        gate.promote("registry.example.com/team/agent@sha256:abc123", "prod")
