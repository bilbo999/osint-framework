"""Collector plugin system: contract (base), discovery (registry) and resilience policy."""

from app.collectors.base import Collector, CollectorDependencies, CollectorMetadata
from app.collectors.registry import CollectorRegistry, create_registry

__all__ = [
    "Collector",
    "CollectorDependencies",
    "CollectorMetadata",
    "CollectorRegistry",
    "create_registry",
]
