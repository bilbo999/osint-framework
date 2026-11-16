"""Collector ABC: metadata validation, helpers and output contract."""

from typing import ClassVar
from uuid import uuid4

import pytest

from app.collectors.base import Collector, CollectorDependencies
from app.collectors.errors import CollectorContractError
from app.core.config import CollectorConfig
from app.domain import (
    FindingType,
    ProvenanceKind,
    RateLimit,
    Source,
    SourceKind,
    Target,
    TargetType,
)
from tests.conftest import FIXED_NOW
from tests.fixtures.fakes import FAKE_SOURCE, EchoCollector


def test_cannot_instantiate_abstract(collector_config: CollectorConfig) -> None:
    with pytest.raises(TypeError):
        Collector(collector_config)  # type: ignore[abstract]


def test_metadata_is_complete() -> None:
    meta = EchoCollector.metadata()
    assert meta.name == "echo"
    assert meta.supported_targets == {TargetType.DOMAIN}
    assert meta.source == FAKE_SOURCE
    assert meta.requires_api_key is False
    assert meta.rate_limit.capacity == 10
    assert meta.data_types == {FindingType.DOMAIN}
    assert meta.model_dump(mode="json")["source"]["name"] == "fake_source"


def test_missing_metadata_detected() -> None:
    class Incomplete(Collector):
        name: ClassVar[str] = "incomplete"

        async def collect(self, target: Target) -> list:  # type: ignore[type-arg]
            return []

    with pytest.raises(CollectorContractError, match="missing metadata"):
        Incomplete.metadata()


def test_api_key_flags_must_agree() -> None:
    class KeyMismatch(EchoCollector):
        name: ClassVar[str] = "key_mismatch"
        requires_api_key: ClassVar[bool] = True

    with pytest.raises(CollectorContractError, match="api_key_env"):
        KeyMismatch.metadata()


def test_invalid_name_rejected() -> None:
    class BadName(EchoCollector):
        name: ClassVar[str] = "Bad Name"

    with pytest.raises(CollectorContractError, match="invalid metadata"):
        BadName.metadata()


async def test_collect_produces_traceable_findings(
    collector_config: CollectorConfig, fixed_deps: CollectorDependencies, domain_target: Target
) -> None:
    collector = EchoCollector(collector_config, fixed_deps)
    findings = collector.validate_output(domain_target, await collector.collect(domain_target))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.provenance_kind is ProvenanceKind.OBSERVED
    assert finding.evidence is not None
    assert finding.evidence_id == finding.evidence.id
    assert finding.timestamp == FIXED_NOW
    assert finding.target_id == domain_target.id
    assert finding.confidence == collector_config.provisional_confidence
    assert finding.is_synthetic is True  # inherited from the synthetic source
    assert finding.evidence.is_synthetic is True


async def test_validate_output_rejects_contract_violations(
    collector_config: CollectorConfig, domain_target: Target
) -> None:
    collector = EchoCollector(collector_config)
    good = (await collector.collect(domain_target))[0]
    bad_cases = [
        good.model_copy(update={"collector": "other"}),
        good.model_copy(update={"source": "undeclared"}),
        good.model_copy(update={"type": FindingType.EMAIL}),
        good.model_copy(update={"target_id": uuid4()}),
        good.model_copy(
            update={"provenance_kind": ProvenanceKind.INFERRED, "derived_from": [uuid4()]}
        ),
    ]
    for bad in bad_cases:
        with pytest.raises(CollectorContractError):
            collector.validate_output(domain_target, [bad])


def test_supports_and_rate_limit_override(
    collector_config: CollectorConfig, investigation_id: object
) -> None:
    override = collector_config.model_copy(
        update={"rate_limit": RateLimit(requests=1, per_seconds=60)}
    )
    collector = EchoCollector(override)
    assert collector.effective_rate_limit.per_seconds == 60
    assert EchoCollector(collector_config).effective_rate_limit == EchoCollector.rate_limit
    email = Target(investigation_id=uuid4(), type=TargetType.EMAIL, value="a@example.org")
    assert not collector.supports(email)


def test_additional_sources_are_allowed() -> None:
    extra = Source(name="extra_src", display_name="Extra", kind=SourceKind.DNS)

    class Multi(EchoCollector):
        name: ClassVar[str] = "multi"
        additional_sources: ClassVar[tuple[Source, ...]] = (extra,)

    assert Multi.metadata().source_names() == {"fake_source", "extra_src"}


async def test_demo_deps_flag_everything_synthetic(
    collector_config: CollectorConfig, domain_target: Target
) -> None:
    real_source = Source(name="dns", display_name="DNS", kind=SourceKind.DNS)

    class RealSourceEcho(EchoCollector):
        name: ClassVar[str] = "real_echo"
        source: ClassVar[Source] = real_source

    plain = (await RealSourceEcho(collector_config).collect(domain_target))[0]
    assert plain.is_synthetic is False
    demo_deps = CollectorDependencies(synthetic=True)
    demo = (await RealSourceEcho(collector_config, demo_deps).collect(domain_target))[0]
    assert demo.is_synthetic is True
    assert demo.evidence is not None
    assert demo.evidence.is_synthetic is True
