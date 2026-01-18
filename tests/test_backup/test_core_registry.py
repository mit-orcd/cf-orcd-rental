# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for core and plugin exporter/importer registries."""

from unittest import TestCase

from coldfront_orcd_direct_charge.backup.base import BaseExporter, BaseImporter
from coldfront_orcd_direct_charge.backup.registry import (
    CoreExporterRegistry,
    PluginExporterRegistry,
    CoreImporterRegistry,
    PluginImporterRegistry,
    CyclicDependencyError,
    COMPONENT_COLDFRONT_CORE,
    COMPONENT_ORCD_PLUGIN,
)


class TestCoreExporterRegistry(TestCase):
    """Tests for CoreExporterRegistry."""
    
    def setUp(self):
        """Clear registry before each test."""
        CoreExporterRegistry.clear()
    
    def tearDown(self):
        """Clear registry after each test."""
        CoreExporterRegistry.clear()
    
    def test_component_name(self):
        """Test that core registry has correct component name."""
        self.assertEqual(CoreExporterRegistry.component, COMPONENT_COLDFRONT_CORE)
    
    def test_register_core_exporter(self):
        """Test registering a core exporter."""
        class TestCoreExporter(BaseExporter):
            model_name = "test_core"
            dependencies = []
            
            def get_queryset(self):
                pass
            
            def serialize_record(self, instance):
                pass
        
        CoreExporterRegistry.register(TestCoreExporter)
        
        self.assertIn("test_core", CoreExporterRegistry.get_all_model_names())
        self.assertEqual(CoreExporterRegistry.get_exporter("test_core"), TestCoreExporter)
    
    def test_core_separate_from_plugin(self):
        """Test that core and plugin registries are separate."""
        class CoreExporter(BaseExporter):
            model_name = "core_model"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        class PluginExporter(BaseExporter):
            model_name = "plugin_model"
            dependencies = []
            def get_queryset(self): pass
            def serialize_record(self, i): pass
        
        CoreExporterRegistry.register(CoreExporter)
        PluginExporterRegistry.register(PluginExporter)
        
        # Core should only have core_model
        self.assertIn("core_model", CoreExporterRegistry.get_all_model_names())
        self.assertNotIn("plugin_model", CoreExporterRegistry.get_all_model_names())
        
        # Plugin should only have plugin_model
        self.assertIn("plugin_model", PluginExporterRegistry.get_all_model_names())
        self.assertNotIn("core_model", PluginExporterRegistry.get_all_model_names())
        
        # Clean up
        PluginExporterRegistry.clear()
    
    def test_get_ordered_core_exporters(self):
        """Test getting core exporters in dependency order."""
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
        
        CoreExporterRegistry.register(ExporterB)
        CoreExporterRegistry.register(ExporterA)
        
        ordered = CoreExporterRegistry.get_ordered_exporters()
        names = [e.model_name for e in ordered]
        
        self.assertLess(names.index("a"), names.index("b"))


class TestPluginExporterRegistry(TestCase):
    """Tests for PluginExporterRegistry."""
    
    def setUp(self):
        """Clear registry before each test."""
        PluginExporterRegistry.clear()
    
    def tearDown(self):
        """Clear registry after each test."""
        PluginExporterRegistry.clear()
    
    def test_component_name(self):
        """Test that plugin registry has correct component name."""
        self.assertEqual(PluginExporterRegistry.component, COMPONENT_ORCD_PLUGIN)
    
    def test_register_plugin_exporter(self):
        """Test registering a plugin exporter."""
        class TestPluginExporter(BaseExporter):
            model_name = "test_plugin"
            dependencies = []
            
            def get_queryset(self):
                pass
            
            def serialize_record(self, instance):
                pass
        
        PluginExporterRegistry.register(TestPluginExporter)
        
        self.assertIn("test_plugin", PluginExporterRegistry.get_all_model_names())


class TestCoreImporterRegistry(TestCase):
    """Tests for CoreImporterRegistry."""
    
    def setUp(self):
        """Clear registry before each test."""
        CoreImporterRegistry.clear()
    
    def tearDown(self):
        """Clear registry after each test."""
        CoreImporterRegistry.clear()
    
    def test_component_name(self):
        """Test that core importer registry has correct component name."""
        self.assertEqual(CoreImporterRegistry.component, COMPONENT_COLDFRONT_CORE)
    
    def test_register_core_importer(self):
        """Test registering a core importer."""
        class TestCoreImporter(BaseImporter):
            model_name = "test_core"
            dependencies = []
            
            def get_existing(self, key): pass
            def deserialize_record(self, data): pass
            def create_record(self, data): pass
            def update_record(self, existing, data): pass
        
        CoreImporterRegistry.register(TestCoreImporter)
        
        self.assertIn("test_core", CoreImporterRegistry.get_all_model_names())


class TestPluginImporterRegistry(TestCase):
    """Tests for PluginImporterRegistry."""
    
    def setUp(self):
        """Clear registry before each test."""
        PluginImporterRegistry.clear()
    
    def tearDown(self):
        """Clear registry after each test."""
        PluginImporterRegistry.clear()
    
    def test_component_name(self):
        """Test that plugin importer registry has correct component name."""
        self.assertEqual(PluginImporterRegistry.component, COMPONENT_ORCD_PLUGIN)
    
    def test_register_plugin_importer(self):
        """Test registering a plugin importer."""
        class TestPluginImporter(BaseImporter):
            model_name = "test_plugin"
            dependencies = []
            
            def get_existing(self, key): pass
            def deserialize_record(self, data): pass
            def create_record(self, data): pass
            def update_record(self, existing, data): pass
        
        PluginImporterRegistry.register(TestPluginImporter)
        
        self.assertIn("test_plugin", PluginImporterRegistry.get_all_model_names())
