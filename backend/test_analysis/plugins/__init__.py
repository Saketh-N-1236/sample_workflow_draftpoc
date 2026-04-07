"""Language plugin registry for the unified analysis pipeline."""

from .base_plugin import LanguagePlugin, PluginRegistry, get_plugin_registry

__all__ = ["LanguagePlugin", "PluginRegistry", "get_plugin_registry"]
