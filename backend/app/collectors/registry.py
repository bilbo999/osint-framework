"""Collector registry: automatic discovery + configuration-driven enablement.

Sources of collectors (all configured in config/collectors.yaml `discovery`):
  1. `packages`      every concrete Collector subclass defined in any module of the package
  2. `modules`       explicit importable modules
  3. `plugin_paths`  directories with *.py files or packages, imported by file path
  4. `entry_points`  installed distributions exposing the `osint_framework.collectors` group

Adding a collector therefore never requires editing the core: create the class in a
discovered location and, optionally, tune it under `collectors:` in collectors.yaml.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
import sys
from collections.abc import Callable, Iterable
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType

import structlog

from app.collectors.base import Collector, CollectorDependencies, CollectorMetadata
from app.collectors.errors import CollectorContractError
from app.core.config import CollectorsConfig
from app.domain.enums import TargetType

logger = structlog.get_logger(__name__)

PLUGIN_MODULE_PREFIX = "osint_plugins"

DependencyFactory = Callable[[type[Collector]], CollectorDependencies]


class CollectorRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type[Collector]] = {}

    # ----------------------------------------------------------------- registration
    def register(self, cls: type[Collector]) -> type[Collector]:
        """Register a collector class. Usable as a decorator. Idempotent per class."""
        if not (inspect.isclass(cls) and issubclass(cls, Collector)) or inspect.isabstract(cls):
            raise CollectorContractError(f"{cls!r} is not a concrete Collector subclass")
        meta = cls.metadata()
        existing = self._classes.get(meta.name)
        if existing is not None and existing is not cls:
            raise CollectorContractError(
                f"duplicate collector name {meta.name!r}: "
                f"{existing.__module__}.{existing.__qualname__} vs {cls.__module__}.{cls.__qualname__}"
            )
        self._classes[meta.name] = cls
        return cls

    def register_module(self, module: ModuleType) -> int:
        """Register every concrete Collector subclass *defined* in `module`."""
        count = 0
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, Collector)
                and obj is not Collector
                and not inspect.isabstract(obj)
                and obj.__module__ == module.__name__
            ):
                self.register(obj)
                count += 1
        return count

    # -------------------------------------------------------------------- discovery
    def discover_package(self, package_name: str) -> int:
        package = importlib.import_module(package_name)
        count = self.register_module(package)
        search_path = getattr(package, "__path__", None)
        if search_path is None:
            return count
        for info in pkgutil.walk_packages(search_path, prefix=f"{package_name}."):
            count += self.register_module(importlib.import_module(info.name))
        return count

    def discover_module(self, module_name: str) -> int:
        return self.register_module(importlib.import_module(module_name))

    def discover_path(self, directory: Path) -> int:
        """Import plugins from a directory (files `*.py` or packages with `__init__.py`)."""
        if not directory.is_dir():
            logger.warning("collector_plugin_path_missing", path=str(directory))
            return 0
        count = 0
        for entry in sorted(directory.iterdir()):
            if entry.name.startswith(("_", ".")):
                continue
            if entry.is_file() and entry.suffix == ".py":
                count += self.register_module(self._import_file(entry, entry.stem))
            elif entry.is_dir() and (entry / "__init__.py").is_file():
                package = self._import_file(entry / "__init__.py", entry.name)
                count += self.register_module(package)
                for info in pkgutil.walk_packages(package.__path__, prefix=f"{package.__name__}."):
                    count += self.register_module(importlib.import_module(info.name))
        return count

    def discover_entry_points(self, group: str) -> int:
        count = 0
        for ep in entry_points(group=group):
            loaded = ep.load()
            if inspect.ismodule(loaded):
                count += self.register_module(loaded)
            else:
                self.register(loaded)
                count += 1
        return count

    def load_from_config(self, config: CollectorsConfig, base_dir: Path) -> int:
        """Run every discovery mechanism configured in collectors.yaml."""
        discovery = config.discovery
        count = sum(self.discover_package(p) for p in discovery.packages)
        count += sum(self.discover_module(m) for m in discovery.modules)
        for raw_path in discovery.plugin_paths:
            path = Path(raw_path)
            count += self.discover_path(path if path.is_absolute() else base_dir / path)
        if discovery.entry_points:
            count += self.discover_entry_points(discovery.entry_point_group)
        unknown = sorted(set(config.collectors) - set(self._classes))
        if unknown:
            logger.warning("collector_config_for_unknown_collectors", names=unknown)
        return count

    # ----------------------------------------------------------------------- queries
    def get(self, name: str) -> type[Collector]:
        try:
            return self._classes[name]
        except KeyError:
            raise KeyError(f"unknown collector {name!r}") from None

    def names(self) -> list[str]:
        return sorted(self._classes)

    def classes(self) -> list[type[Collector]]:
        return [self._classes[n] for n in self.names()]

    def metadata(self) -> list[CollectorMetadata]:
        return [cls.metadata() for cls in self.classes()]

    def for_target_type(self, target_type: TargetType) -> list[type[Collector]]:
        return [c for c in self.classes() if target_type in c.supported_targets]

    def __contains__(self, name: object) -> bool:
        return name in self._classes

    def __len__(self) -> int:
        return len(self._classes)

    # ------------------------------------------------------------------ instantiation
    def build_enabled(
        self,
        config: CollectorsConfig,
        deps_factory: DependencyFactory | None = None,
        only: Iterable[str] | None = None,
    ) -> list[Collector]:
        """Instantiate enabled collectors (optionally restricted to `only`).

        API-key availability is NOT checked here: the executor (Phase 3) marks
        collectors without their key as SKIPPED so the UI can explain why.
        """
        wanted = set(only) if only is not None else None
        if wanted is not None and (unknown := wanted - set(self._classes)):
            raise KeyError(f"unknown collectors requested: {sorted(unknown)}")
        instances: list[Collector] = []
        for cls in self.classes():
            if wanted is not None and cls.name not in wanted:
                continue
            resolved = config.resolve(cls.name)
            if not resolved.enabled:
                continue
            deps = deps_factory(cls) if deps_factory else None
            instances.append(cls(resolved, deps))
        return instances

    # ---------------------------------------------------------------------- internal
    @staticmethod
    def _import_file(file_path: Path, module_name: str) -> ModuleType:
        qualified = f"{PLUGIN_MODULE_PREFIX}.{module_name}"
        if qualified in sys.modules:
            return sys.modules[qualified]
        spec = importlib.util.spec_from_file_location(
            qualified,
            file_path,
            submodule_search_locations=(
                [str(file_path.parent)] if file_path.name == "__init__.py" else None
            ),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load collector plugin from {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            del sys.modules[qualified]
            raise
        return module


def create_registry(config: CollectorsConfig, base_dir: Path) -> CollectorRegistry:
    """Convenience factory used by the API, CLI and workers."""
    registry = CollectorRegistry()
    registry.load_from_config(config, base_dir)
    return registry
