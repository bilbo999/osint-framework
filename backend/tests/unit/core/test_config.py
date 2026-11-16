"""The shipped config/*.yaml files are valid and the validators catch broken weights."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.core.config import AppConfig, ScoringConfig, SettingsConfig, load_config
from app.core.settings import REPO_ROOT
from app.domain import FindingType, ProvenanceKind

CONFIG_DIR = REPO_ROOT / "config"
ALL_CATEGORIES = {
    "identity",
    "contact",
    "credential",
    "social",
    "infrastructure",
    "historical",
    "correlation",
}


def _yaml(name: str) -> dict[str, Any]:
    data = yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_repository_config_loads(app_config: AppConfig) -> None:
    assert app_config.settings.app.api_prefix == "/api/v1"
    assert len(app_config.scoring_hash) == 64
    assert app_config.settings.demo.banner == "DEMO / SYNTHETIC DATA"


def test_exposure_categories_sum_to_100(app_config: AppConfig) -> None:
    categories = app_config.scoring.exposure.categories
    assert set(categories) == ALL_CATEGORIES
    assert sum(c.max_points for c in categories.values()) == 100


def test_confidence_weights_sum_to_one(app_config: AppConfig) -> None:
    assert sum(app_config.scoring.confidence.weights.values()) == pytest.approx(1.0)
    caps = app_config.scoring.confidence.provenance_caps
    assert caps[ProvenanceKind.OBSERVED] >= caps[ProvenanceKind.DERIVED]
    assert caps[ProvenanceKind.DERIVED] > caps[ProvenanceKind.CORRELATED]
    assert caps[ProvenanceKind.CORRELATED] > caps[ProvenanceKind.INFERRED]


def test_pivot_types_are_valid(app_config: AppConfig) -> None:
    assert FindingType.DOMAIN in app_config.settings.execution.pivot_finding_types


def test_broken_category_weights_rejected() -> None:
    data = _yaml("scoring.yaml")
    data["exposure"]["categories"]["identity"]["max_points"] = 50
    with pytest.raises(ValidationError, match="expected 100"):
        ScoringConfig.model_validate(data)


def test_broken_confidence_weights_rejected() -> None:
    data = _yaml("scoring.yaml")
    data["confidence"]["weights"]["freshness"] = 0.5
    with pytest.raises(ValidationError, match=r"sum to 1\.0"):
        ScoringConfig.model_validate(data)


def test_unknown_finding_type_in_rule_rejected() -> None:
    data = _yaml("scoring.yaml")
    data["exposure"]["categories"]["contact"]["rules"][0]["finding_types"] = ["nonexistent"]
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(data)


def test_rule_prefix_enforced() -> None:
    data = _yaml("scoring.yaml")
    data["exposure"]["categories"]["contact"]["rules"][0]["id"] = "identity.email_dup"
    with pytest.raises(ValidationError, match="must start with"):
        ScoringConfig.model_validate(data)


def test_er_thresholds_ordered() -> None:
    data = _yaml("settings.yaml")
    data["entity_resolution"]["review_threshold"] = 0.9
    with pytest.raises(ValidationError, match="review_threshold"):
        SettingsConfig.model_validate(data)


def test_unknown_keys_rejected() -> None:
    data = _yaml("settings.yaml")
    data["execution"]["typo_key"] = 1
    with pytest.raises(ValidationError):
        SettingsConfig.model_validate(data)


def test_load_config_from_custom_dir(tmp_path: Path) -> None:
    for name in ("settings.yaml", "collectors.yaml", "scoring.yaml"):
        (tmp_path / name).write_bytes((CONFIG_DIR / name).read_bytes())
    assert load_config(tmp_path).config_dir == tmp_path
    (tmp_path / "settings.yaml").write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_config(tmp_path)


def test_collector_resolve_merges_defaults(app_config: AppConfig) -> None:
    collectors = app_config.collectors
    crtsh = collectors.resolve("crtsh")
    assert crtsh.timeout_seconds == 30
    assert crtsh.retry.max_attempts == 2
    assert crtsh.retry.backoff_max_seconds == collectors.defaults.retry.backoff_max_seconds
    assert collectors.resolve("unknown") == collectors.defaults
    assert collectors.resolve("geoip_maxmind").enabled is False
