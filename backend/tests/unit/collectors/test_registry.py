"""Registry: discovery by package/module/path/entry point and config-driven enablement."""

from pathlib import Path
from typing import ClassVar

import pytest

from app.collectors.base import Collector, CollectorDependencies
from app.collectors.errors import CollectorContractError
from app.collectors.registry import CollectorRegistry, create_registry
from app.core.config import AppConfig, CollectorOverride, CollectorsConfig, DiscoveryConfig
from app.core.settings import REPO_ROOT
from app.domain import TargetType
from tests.conftest import FIXTURES_DIR
from tests.fixtures.fakes import EchoCollector


def _config(app_config: AppConfig, **overrides: CollectorOverride) -> CollectorsConfig:
    return app_config.collectors.model_copy(update={"collectors": overrides})


def test_register_and_query() -> None:
    registry = CollectorRegistry()
    registry.register(EchoCollector)
    registry.register(EchoCollector)  # idempotent
    assert registry.names() == ["echo"]
    assert "echo" in registry
    assert len(registry) == 1
    assert registry.get("echo") is EchoCollector
    assert registry.for_target_type(TargetType.DOMAIN) == [EchoCollector]
    assert registry.for_target_type(TargetType.EMAIL) == []
    assert registry.metadata()[0].name == "echo"
    with pytest.raises(KeyError):
        registry.get("missing")


def test_duplicate_names_rejected() -> None:
    class Impostor(EchoCollector):
        name: ClassVar[str] = "echo"

    registry = CollectorRegistry()
    registry.register(EchoCollector)
    with pytest.raises(CollectorContractError, match="duplicate"):
        registry.register(Impostor)


def test_abstract_and_non_collectors_rejected() -> None:
    registry = CollectorRegistry()
    with pytest.raises(CollectorContractError):
        registry.register(Collector)  # type: ignore[type-abstract]
    with pytest.raises(CollectorContractError):
        registry.register(int)  # type: ignore[arg-type]


def test_discover_package_walks_subpackages() -> None:
    registry = CollectorRegistry()
    assert registry.discover_package("tests.fixtures.collector_pkg") == 2
    # EchoCollector is imported by alpha.py but defined elsewhere => not registered there.
    assert registry.names() == ["alpha", "beta"]


def test_discover_module() -> None:
    registry = CollectorRegistry()
    assert registry.discover_module("tests.fixtures.fakes") == 1
    assert registry.names() == ["echo"]


def test_discover_path_loads_files_and_packages() -> None:
    registry = CollectorRegistry()
    assert registry.discover_path(FIXTURES_DIR / "plugin_dir") == 2
    assert registry.names() == ["file_plugin", "pkg_plugin"]
    # Loading twice is harmless (cached modules, idempotent registration).
    registry.discover_path(FIXTURES_DIR / "plugin_dir")
    assert len(registry) == 2


def test_missing_plugin_path_is_not_fatal(tmp_path: Path) -> None:
    assert CollectorRegistry().discover_path(tmp_path / "nope") == 0


def test_load_from_config(app_config: AppConfig) -> None:
    config = app_config.collectors.model_copy(
        update={
            "discovery": DiscoveryConfig(
                packages=["tests.fixtures.collector_pkg"],
                modules=["tests.fixtures.fakes"],
                plugin_paths=[str(FIXTURES_DIR / "plugin_dir")],
                entry_points=True,
            )
        }
    )
    registry = create_registry(config, REPO_ROOT)
    assert {"alpha", "beta", "echo", "file_plugin", "pkg_plugin"} <= set(registry.names())


def test_repository_config_discovers_without_errors(app_config: AppConfig) -> None:
    """The real collectors.yaml must load even before built-in collectors exist (Phase 4)."""
    registry = create_registry(app_config.collectors, REPO_ROOT)
    assert isinstance(registry.names(), list)


def test_build_enabled_respects_config(app_config: AppConfig) -> None:
    registry = CollectorRegistry()
    registry.discover_package("tests.fixtures.collector_pkg")
    registry.register(EchoCollector)

    config = _config(
        app_config,
        beta=CollectorOverride(enabled=False),
        echo=CollectorOverride(timeout_seconds=3, retry={"max_attempts": 1}),
    )
    built = {c.name: c for c in registry.build_enabled(config)}
    assert set(built) == {"alpha", "echo"}
    assert built["echo"].config.timeout_seconds == 3
    assert built["echo"].config.retry.max_attempts == 1
    # Partial nested overrides keep the remaining defaults.
    defaults = config.defaults.retry
    assert built["echo"].config.retry.backoff_base_seconds == defaults.backoff_base_seconds
    assert built["alpha"].config == config.defaults


def test_build_enabled_only_and_deps_factory(app_config: AppConfig) -> None:
    registry = CollectorRegistry()
    registry.register(EchoCollector)
    seen: list[str] = []

    def factory(cls: type[Collector]) -> CollectorDependencies:
        seen.append(cls.name)
        return CollectorDependencies()

    built = registry.build_enabled(app_config.collectors, factory, only=["echo"])
    assert [c.name for c in built] == ["echo"]
    assert seen == ["echo"]
    with pytest.raises(KeyError, match="unknown collectors"):
        registry.build_enabled(app_config.collectors, only=["ghost"])
