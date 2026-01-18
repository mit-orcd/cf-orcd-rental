# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Registry for exporter and importer classes.

The registry maintains the collection of available exporters/importers
and handles dependency ordering for export/import operations.

Components:
    - coldfront_core: ColdFront core models (User, Project, Allocation, etc.)
    - orcd_plugin: ORCD plugin models (NodeType, Reservation, etc.)

Usage:
    # Register a plugin exporter
    @PluginExporterRegistry.register
    class NodeTypeExporter(BaseExporter):
        model_name = "node_types"
        ...
    
    # Register a core exporter
    @CoreExporterRegistry.register
    class UserExporter(BaseExporter):
        model_name = "users"
        ...

Dependency Resolution:
    Exporters/importers declare dependencies via the `dependencies` attribute.
    The registry uses topological sorting to ensure dependent models are
    processed first.
"""

from typing import Dict, List, Type
import logging

from .base import BaseExporter, BaseImporter

logger = logging.getLogger(__name__)

# Component names
COMPONENT_COLDFRONT_CORE = "coldfront_core"
COMPONENT_ORCD_PLUGIN = "orcd_plugin"


class RegistryError(Exception):
    """Exception raised for registry errors."""
    pass


class CyclicDependencyError(RegistryError):
    """Exception raised when circular dependencies are detected."""
    pass


class BaseRegistry:
    """Base class for exporter/importer registries with common functionality."""
    
    _items: Dict = {}
    component: str = ""
    
    @classmethod
    def validate_dependencies(cls, items_dict: Dict) -> List[str]:
        """Validate all dependencies are registered.
        
        Args:
            items_dict: Dict of registered items
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for name, item in items_dict.items():
            for dep in item.dependencies:
                if dep not in items_dict:
                    errors.append(f"{name} depends on unregistered '{dep}'")
        return errors
    
    @classmethod
    def _topological_sort(cls, model_names: set, items_dict: Dict) -> List:
        """Perform topological sort on items.
        
        Args:
            model_names: Set of model names to sort
            items_dict: Dict of registered items
            
        Returns:
            List of item classes in dependency order
        """
        visited = set()
        in_progress = set()
        result = []
        
        def visit(name: str):
            if name in in_progress:
                raise CyclicDependencyError(
                    f"Circular dependency detected involving {name}"
                )
            if name in visited:
                return
            
            in_progress.add(name)
            
            item = items_dict.get(name)
            if item:
                for dep in item.dependencies:
                    if dep in model_names:
                        visit(dep)
            
            in_progress.remove(name)
            visited.add(name)
            
            if name in items_dict:
                result.append(items_dict[name])
        
        for name in model_names:
            visit(name)
        
        return result


class CoreExporterRegistry(BaseRegistry):
    """Registry for ColdFront core exporters.
    
    Exports Django auth models, ColdFront core Project, Resource, Allocation models.
    """
    
    _exporters: Dict[str, Type[BaseExporter]] = {}
    component = COMPONENT_COLDFRONT_CORE
    
    @classmethod
    def register(cls, exporter_class: Type[BaseExporter]) -> Type[BaseExporter]:
        """Decorator to register a core exporter class."""
        if not exporter_class.model_name:
            raise ValueError(
                f"Exporter class {exporter_class.__name__} must define model_name"
            )
        
        cls._exporters[exporter_class.model_name] = exporter_class
        logger.debug(f"Registered core exporter: {exporter_class.model_name}")
        return exporter_class
    
    @classmethod
    def get_ordered_exporters(
        cls,
        include: List[str] = None,
        exclude: List[str] = None,
    ) -> List[Type[BaseExporter]]:
        """Return core exporters in dependency order."""
        # Validate dependencies first
        errors = cls.validate_dependencies(cls._exporters)
        if errors:
            raise RegistryError("Dependency validation failed:\n" + "\n".join(errors))
        
        if include:
            for name in include:
                if name not in cls._exporters:
                    raise KeyError(f"Unknown core exporter: {name}")
            model_names = set(include)
        else:
            model_names = set(cls._exporters.keys())
        
        if exclude:
            model_names -= set(exclude)
        
        return cls._topological_sort(model_names, cls._exporters)
    
    @classmethod
    def get_exporter(cls, model_name: str) -> Type[BaseExporter]:
        """Get core exporter by model name."""
        if model_name not in cls._exporters:
            raise KeyError(f"No core exporter registered for: {model_name}")
        return cls._exporters[model_name]
    
    @classmethod
    def get_all_model_names(cls) -> List[str]:
        """List all registered core model names."""
        return list(cls._exporters.keys())
    
    @classmethod
    def clear(cls):
        """Clear all registered core exporters (for testing)."""
        cls._exporters = {}


class PluginExporterRegistry(BaseRegistry):
    """Registry for ORCD plugin exporters.
    
    Exports plugin-specific models like NodeType, Reservation, RentalSKU, etc.
    """
    
    _exporters: Dict[str, Type[BaseExporter]] = {}
    component = COMPONENT_ORCD_PLUGIN
    
    @classmethod
    def register(cls, exporter_class: Type[BaseExporter]) -> Type[BaseExporter]:
        """Decorator to register a plugin exporter class."""
        if not exporter_class.model_name:
            raise ValueError(
                f"Exporter class {exporter_class.__name__} must define model_name"
            )
        
        cls._exporters[exporter_class.model_name] = exporter_class
        logger.debug(f"Registered plugin exporter: {exporter_class.model_name}")
        return exporter_class
    
    @classmethod
    def get_ordered_exporters(
        cls,
        include: List[str] = None,
        exclude: List[str] = None,
    ) -> List[Type[BaseExporter]]:
        """Return plugin exporters in dependency order."""
        # Validate dependencies first
        errors = cls.validate_dependencies(cls._exporters)
        if errors:
            raise RegistryError("Dependency validation failed:\n" + "\n".join(errors))
        
        if include:
            for name in include:
                if name not in cls._exporters:
                    raise KeyError(f"Unknown plugin exporter: {name}")
            model_names = set(include)
        else:
            model_names = set(cls._exporters.keys())
        
        if exclude:
            model_names -= set(exclude)
        
        return cls._topological_sort(model_names, cls._exporters)
    
    @classmethod
    def get_exporter(cls, model_name: str) -> Type[BaseExporter]:
        """Get plugin exporter by model name."""
        if model_name not in cls._exporters:
            raise KeyError(f"No plugin exporter registered for: {model_name}")
        return cls._exporters[model_name]
    
    @classmethod
    def get_all_model_names(cls) -> List[str]:
        """List all registered plugin model names."""
        return list(cls._exporters.keys())
    
    @classmethod
    def clear(cls):
        """Clear all registered plugin exporters (for testing)."""
        cls._exporters = {}


class CoreImporterRegistry(BaseRegistry):
    """Registry for ColdFront core importers."""
    
    _importers: Dict[str, Type[BaseImporter]] = {}
    component = COMPONENT_COLDFRONT_CORE
    
    @classmethod
    def register(cls, importer_class: Type[BaseImporter]) -> Type[BaseImporter]:
        """Decorator to register a core importer class."""
        if not importer_class.model_name:
            raise ValueError(
                f"Importer class {importer_class.__name__} must define model_name"
            )
        
        cls._importers[importer_class.model_name] = importer_class
        logger.debug(f"Registered core importer: {importer_class.model_name}")
        return importer_class
    
    @classmethod
    def get_ordered_importers(
        cls,
        include: List[str] = None,
        exclude: List[str] = None,
    ) -> List[Type[BaseImporter]]:
        """Return core importers in dependency order."""
        # Validate dependencies first
        errors = cls.validate_dependencies(cls._importers)
        if errors:
            raise RegistryError("Dependency validation failed:\n" + "\n".join(errors))
        
        if include:
            for name in include:
                if name not in cls._importers:
                    raise KeyError(f"Unknown core importer: {name}")
            model_names = set(include)
        else:
            model_names = set(cls._importers.keys())
        
        if exclude:
            model_names -= set(exclude)
        
        return cls._topological_sort(model_names, cls._importers)
    
    @classmethod
    def get_importer(cls, model_name: str) -> Type[BaseImporter]:
        """Get core importer by model name."""
        if model_name not in cls._importers:
            raise KeyError(f"No core importer registered for: {model_name}")
        return cls._importers[model_name]
    
    @classmethod
    def get_all_model_names(cls) -> List[str]:
        """List all registered core model names."""
        return list(cls._importers.keys())
    
    @classmethod
    def clear(cls):
        """Clear all registered core importers (for testing)."""
        cls._importers = {}


class PluginImporterRegistry(BaseRegistry):
    """Registry for ORCD plugin importers."""
    
    _importers: Dict[str, Type[BaseImporter]] = {}
    component = COMPONENT_ORCD_PLUGIN
    
    @classmethod
    def register(cls, importer_class: Type[BaseImporter]) -> Type[BaseImporter]:
        """Decorator to register a plugin importer class."""
        if not importer_class.model_name:
            raise ValueError(
                f"Importer class {importer_class.__name__} must define model_name"
            )
        
        cls._importers[importer_class.model_name] = importer_class
        logger.debug(f"Registered plugin importer: {importer_class.model_name}")
        return importer_class
    
    @classmethod
    def get_ordered_importers(
        cls,
        include: List[str] = None,
        exclude: List[str] = None,
    ) -> List[Type[BaseImporter]]:
        """Return plugin importers in dependency order."""
        # Validate dependencies first
        errors = cls.validate_dependencies(cls._importers)
        if errors:
            raise RegistryError("Dependency validation failed:\n" + "\n".join(errors))
        
        if include:
            for name in include:
                if name not in cls._importers:
                    raise KeyError(f"Unknown plugin importer: {name}")
            model_names = set(include)
        else:
            model_names = set(cls._importers.keys())
        
        if exclude:
            model_names -= set(exclude)
        
        return cls._topological_sort(model_names, cls._importers)
    
    @classmethod
    def get_importer(cls, model_name: str) -> Type[BaseImporter]:
        """Get plugin importer by model name."""
        if model_name not in cls._importers:
            raise KeyError(f"No plugin importer registered for: {model_name}")
        return cls._importers[model_name]
    
    @classmethod
    def get_all_model_names(cls) -> List[str]:
        """List all registered plugin model names."""
        return list(cls._importers.keys())
    
    @classmethod
    def clear(cls):
        """Clear all registered plugin importers (for testing)."""
        cls._importers = {}


# Backward compatibility aliases
ExporterRegistry = PluginExporterRegistry
ImporterRegistry = PluginImporterRegistry
