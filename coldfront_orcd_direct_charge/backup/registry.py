# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Registry for exporter and importer classes.

The registry maintains the collection of available exporters/importers
and handles dependency ordering for export/import operations.

Usage:
    # Register an exporter
    @ExporterRegistry.register
    class NodeTypeExporter(BaseExporter):
        model_name = "node_types"
        ...
    
    # Get ordered exporters for export operation
    for exporter_class in ExporterRegistry.get_ordered_exporters():
        exporter = exporter_class()
        result = exporter.export(output_dir)

Dependency Resolution:
    Exporters/importers declare dependencies via the `dependencies` attribute.
    The registry uses topological sorting to ensure dependent models are
    processed first.
"""

from typing import Dict, List, Type
import logging

from .base import BaseExporter, BaseImporter

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Exception raised for registry errors."""
    pass


class CyclicDependencyError(RegistryError):
    """Exception raised when circular dependencies are detected."""
    pass


class ExporterRegistry:
    """Registry of available exporters with dependency resolution.
    
    Exporters register themselves using the @register decorator.
    The registry maintains the collection and provides ordered access
    based on dependencies.
    
    Class Attributes:
        _exporters: Dict mapping model_name to exporter class
    
    Methods:
        register: Decorator to register an exporter class
        get_ordered_exporters: Return exporters in dependency order
        get_exporter: Get exporter by model name
        get_all_model_names: List all registered model names
    """
    
    _exporters: Dict[str, Type[BaseExporter]] = {}
    
    @classmethod
    def register(cls, exporter_class: Type[BaseExporter]) -> Type[BaseExporter]:
        """Decorator to register an exporter class.
        
        Example:
            @ExporterRegistry.register
            class NodeTypeExporter(BaseExporter):
                model_name = "node_types"
                ...
        
        Args:
            exporter_class: The exporter class to register
            
        Returns:
            The same class (allows use as decorator)
            
        Raises:
            ValueError: If model_name is not set
        """
        if not exporter_class.model_name:
            raise ValueError(
                f"Exporter class {exporter_class.__name__} must define model_name"
            )
        
        cls._exporters[exporter_class.model_name] = exporter_class
        logger.debug(f"Registered exporter: {exporter_class.model_name}")
        return exporter_class
    
    @classmethod
    def get_ordered_exporters(
        cls,
        include: List[str] = None,
        exclude: List[str] = None,
    ) -> List[Type[BaseExporter]]:
        """Return exporters in dependency order.
        
        Uses topological sort to ensure dependencies are exported first.
        
        Args:
            include: If provided, only include these model names
            exclude: If provided, exclude these model names
            
        Returns:
            List of exporter classes in safe export order
            
        Raises:
            CyclicDependencyError: If circular dependencies exist
            KeyError: If an unknown model name is in include list
        """
        # Determine which exporters to include
        if include:
            for name in include:
                if name not in cls._exporters:
                    raise KeyError(f"Unknown exporter: {name}")
            model_names = set(include)
        else:
            model_names = set(cls._exporters.keys())
        
        if exclude:
            model_names -= set(exclude)
        
        # Build dependency graph
        return cls._topological_sort(model_names)
    
    @classmethod
    def _topological_sort(cls, model_names: set) -> List[Type[BaseExporter]]:
        """Perform topological sort on exporters.
        
        Args:
            model_names: Set of model names to sort
            
        Returns:
            List of exporter classes in dependency order
        """
        # Track visited and in-progress for cycle detection
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
            
            exporter = cls._exporters.get(name)
            if exporter:
                for dep in exporter.dependencies:
                    if dep in model_names:
                        visit(dep)
            
            in_progress.remove(name)
            visited.add(name)
            
            if name in cls._exporters:
                result.append(cls._exporters[name])
        
        for name in model_names:
            visit(name)
        
        return result
    
    @classmethod
    def get_exporter(cls, model_name: str) -> Type[BaseExporter]:
        """Get exporter by model name.
        
        Args:
            model_name: The model name to look up
            
        Returns:
            The exporter class
            
        Raises:
            KeyError: If model_name is not registered
        """
        if model_name not in cls._exporters:
            raise KeyError(f"No exporter registered for: {model_name}")
        return cls._exporters[model_name]
    
    @classmethod
    def get_all_model_names(cls) -> List[str]:
        """List all registered model names.
        
        Returns:
            List of model names
        """
        return list(cls._exporters.keys())
    
    @classmethod
    def clear(cls):
        """Clear all registered exporters (for testing)."""
        cls._exporters = {}


class ImporterRegistry:
    """Registry of available importers with dependency resolution.
    
    Importers register themselves using the @register decorator.
    The registry maintains the collection and provides ordered access
    based on dependencies.
    
    Class Attributes:
        _importers: Dict mapping model_name to importer class
    """
    
    _importers: Dict[str, Type[BaseImporter]] = {}
    
    @classmethod
    def register(cls, importer_class: Type[BaseImporter]) -> Type[BaseImporter]:
        """Decorator to register an importer class.
        
        Example:
            @ImporterRegistry.register
            class NodeTypeImporter(BaseImporter):
                model_name = "node_types"
                ...
        
        Args:
            importer_class: The importer class to register
            
        Returns:
            The same class (allows use as decorator)
            
        Raises:
            ValueError: If model_name is not set
        """
        if not importer_class.model_name:
            raise ValueError(
                f"Importer class {importer_class.__name__} must define model_name"
            )
        
        cls._importers[importer_class.model_name] = importer_class
        logger.debug(f"Registered importer: {importer_class.model_name}")
        return importer_class
    
    @classmethod
    def get_ordered_importers(
        cls,
        include: List[str] = None,
        exclude: List[str] = None,
    ) -> List[Type[BaseImporter]]:
        """Return importers in dependency order.
        
        Uses topological sort to ensure dependencies are imported first.
        
        Args:
            include: If provided, only include these model names
            exclude: If provided, exclude these model names
            
        Returns:
            List of importer classes in safe import order
            
        Raises:
            CyclicDependencyError: If circular dependencies exist
            KeyError: If an unknown model name is in include list
        """
        # Determine which importers to include
        if include:
            for name in include:
                if name not in cls._importers:
                    raise KeyError(f"Unknown importer: {name}")
            model_names = set(include)
        else:
            model_names = set(cls._importers.keys())
        
        if exclude:
            model_names -= set(exclude)
        
        # Build dependency graph
        return cls._topological_sort(model_names)
    
    @classmethod
    def _topological_sort(cls, model_names: set) -> List[Type[BaseImporter]]:
        """Perform topological sort on importers.
        
        Args:
            model_names: Set of model names to sort
            
        Returns:
            List of importer classes in dependency order
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
            
            importer = cls._importers.get(name)
            if importer:
                for dep in importer.dependencies:
                    if dep in model_names:
                        visit(dep)
            
            in_progress.remove(name)
            visited.add(name)
            
            if name in cls._importers:
                result.append(cls._importers[name])
        
        for name in model_names:
            visit(name)
        
        return result
    
    @classmethod
    def get_importer(cls, model_name: str) -> Type[BaseImporter]:
        """Get importer by model name.
        
        Args:
            model_name: The model name to look up
            
        Returns:
            The importer class
            
        Raises:
            KeyError: If model_name is not registered
        """
        if model_name not in cls._importers:
            raise KeyError(f"No importer registered for: {model_name}")
        return cls._importers[model_name]
    
    @classmethod
    def get_all_model_names(cls) -> List[str]:
        """List all registered model names.
        
        Returns:
            List of model names
        """
        return list(cls._importers.keys())
    
    @classmethod
    def clear(cls):
        """Clear all registered importers (for testing)."""
        cls._importers = {}
