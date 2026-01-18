# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for exporter and importer registries."""

from unittest import TestCase

from coldfront_orcd_direct_charge.backup.base import BaseExporter, BaseImporter
from coldfront_orcd_direct_charge.backup.registry import (
    ExporterRegistry,
    ImporterRegistry,
    CyclicDependencyError,
)


class TestExporterRegistry(TestCase):
    """Tests for ExporterRegistry."""
    
    def setUp(self):
        """Clear registry before each test."""
        ExporterRegistry.clear()
    
    def tearDown(self):
        """Clear registry after each test."""
        ExporterRegistry.clear()
    
    def test_register_exporter(self):
        """Test registering an exporter."""
        class TestExporter(BaseExporter):
            model_name = "test"
            dependencies = []
            
            def get_queryset(self):
                pass
            
            def serialize_record(self, instance):
                pass
        
        ExporterRegistry.register(TestExporter)
        
        self.assertIn("test", ExporterRegistry.get_all_model_names())
        self.assertEqual(ExporterRegistry.get_exporter("test"), TestExporter)
    
    def test_register_decorator(self):
        """Test using register as decorator."""
        @ExporterRegistry.register
        class DecoratedExporter(BaseExporter):
            model_name = "decorated"
            dependencies = []
            
            def get_queryset(self):
                pass
            
            def serialize_record(self, instance):
                pass
        
        self.assertIn("decorated", ExporterRegistry.get_all_model_names())
    
    def test_register_without_model_name(self):
        """Test that registering without model_name raises error."""
        class BadExporter(BaseExporter):
            model_name = ""
            dependencies = []
            
            def get_queryset(self):
                pass
            
            def serialize_record(self, instance):
                pass
        
        with self.assertRaises(ValueError):
            ExporterRegistry.register(BadExporter)
    
    def test_get_ordered_exporters(self):
        """Test getting exporters in dependency order."""
        class ExporterA(BaseExporter):
            model_name = "a"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        class ExporterB(BaseExporter):
            model_name = "b"
            dependencies = ["a"]
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        class ExporterC(BaseExporter):
            model_name = "c"
            dependencies = ["b"]
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        ExporterRegistry.register(ExporterC)
        ExporterRegistry.register(ExporterA)
        ExporterRegistry.register(ExporterB)
        
        ordered = ExporterRegistry.get_ordered_exporters()
        names = [e.model_name for e in ordered]
        
        # A must come before B, B must come before C
        self.assertLess(names.index("a"), names.index("b"))
        self.assertLess(names.index("b"), names.index("c"))
    
    def test_get_ordered_with_include(self):
        """Test filtering with include list."""
        class ExporterA(BaseExporter):
            model_name = "a"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        class ExporterB(BaseExporter):
            model_name = "b"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        ExporterRegistry.register(ExporterA)
        ExporterRegistry.register(ExporterB)
        
        ordered = ExporterRegistry.get_ordered_exporters(include=["a"])
        names = [e.model_name for e in ordered]
        
        self.assertEqual(names, ["a"])
    
    def test_get_ordered_with_exclude(self):
        """Test filtering with exclude list."""
        class ExporterA(BaseExporter):
            model_name = "a"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        class ExporterB(BaseExporter):
            model_name = "b"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        ExporterRegistry.register(ExporterA)
        ExporterRegistry.register(ExporterB)
        
        ordered = ExporterRegistry.get_ordered_exporters(exclude=["a"])
        names = [e.model_name for e in ordered]
        
        self.assertEqual(names, ["b"])
    
    def test_cyclic_dependency_detection(self):
        """Test that cyclic dependencies are detected."""
        class ExporterA(BaseExporter):
            model_name = "a"
            dependencies = ["b"]
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        class ExporterB(BaseExporter):
            model_name = "b"
            dependencies = ["a"]
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        ExporterRegistry.register(ExporterA)
        ExporterRegistry.register(ExporterB)
        
        with self.assertRaises(CyclicDependencyError):
            ExporterRegistry.get_ordered_exporters()
    
    def test_unknown_model_in_include(self):
        """Test that unknown model in include raises error."""
        with self.assertRaises(KeyError):
            ExporterRegistry.get_ordered_exporters(include=["unknown"])


class TestImporterRegistry(TestCase):
    """Tests for ImporterRegistry."""
    
    def setUp(self):
        """Clear registry before each test."""
        ImporterRegistry.clear()
    
    def tearDown(self):
        """Clear registry after each test."""
        ImporterRegistry.clear()
    
    def test_register_importer(self):
        """Test registering an importer."""
        class TestImporter(BaseImporter):
            model_name = "test"
            dependencies = []
            
            def get_existing(self, key): pass
            def deserialize_record(self, data): pass
            def create_record(self, data): pass
            def update_record(self, existing, data): pass
        
        ImporterRegistry.register(TestImporter)
        
        self.assertIn("test", ImporterRegistry.get_all_model_names())
        self.assertEqual(ImporterRegistry.get_importer("test"), TestImporter)
    
    def test_get_ordered_importers(self):
        """Test getting importers in dependency order."""
        class ImporterA(BaseImporter):
            model_name = "a"
            dependencies = []
            def get_existing(self, key): pass
            def deserialize_record(self, data): pass
            def create_record(self, data): pass
            def update_record(self, existing, data): pass
        
        class ImporterB(BaseImporter):
            model_name = "b"
            dependencies = ["a"]
            def get_existing(self, key): pass
            def deserialize_record(self, data): pass
            def create_record(self, data): pass
            def update_record(self, existing, data): pass
        
        ImporterRegistry.register(ImporterB)
        ImporterRegistry.register(ImporterA)
        
        ordered = ImporterRegistry.get_ordered_importers()
        names = [i.model_name for i in ordered]
        
        self.assertLess(names.index("a"), names.index("b"))
