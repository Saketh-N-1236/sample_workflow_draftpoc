"""
Configuration loader for language-specific settings.

Loads and validates language configurations from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_language_configs(config_path: Path = None) -> Dict[str, Any]:
    """
    Load language configurations from YAML file.
    
    Args:
        config_path: Path to language_configs.yaml file.
                    If None, uses default location: config/language_configs.yaml
    
    Returns:
        Dictionary containing language configurations
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    if config_path is None:
        # Default location: config/language_configs.yaml relative to project root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config" / "language_configs.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Language config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Validate structure
    if not isinstance(config, dict) or 'languages' not in config:
        raise ValueError(f"Invalid config structure in {config_path}")
    
    return config


def get_language_config(config: Dict[str, Any], language: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific language.
    
    Args:
        config: Full configuration dictionary
        language: Language name (e.g., 'python', 'java')
    
    Returns:
        Language-specific configuration, or None if not found
    """
    languages = config.get('languages', {})
    return languages.get(language)


def get_test_patterns(config: Dict[str, Any], language: str) -> list:
    """
    Get test file patterns for a language.
    
    Args:
        config: Full configuration dictionary
        language: Language name
    
    Returns:
        List of test file patterns
    """
    lang_config = get_language_config(config, language)
    if lang_config:
        return lang_config.get('test_patterns', [])
    return []


def get_file_extensions(config: Dict[str, Any], language: str) -> list:
    """
    Get file extensions for a language.
    
    Args:
        config: Full configuration dictionary
        language: Language name
    
    Returns:
        List of file extensions (with leading dot)
    """
    lang_config = get_language_config(config, language)
    if lang_config:
        return lang_config.get('extensions', [])
    return []
