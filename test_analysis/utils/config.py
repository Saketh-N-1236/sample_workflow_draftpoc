"""
Configuration utilities for test analysis.

Provides functions to get configuration values from environment variables,
config files, or defaults.
"""

import os
from pathlib import Path
from typing import Optional


def get_test_repo_path() -> Path:
    """
    Get test repository path from configuration.
    
    Priority:
    1. TEST_REPO_PATH environment variable
    2. Config file setting (future enhancement)
    3. Default: test_repository directory
    
    Returns:
        Path to test repository (absolute path)
    
    Example:
        >>> repo_path = get_test_repo_path()
        >>> print(repo_path)
        /path/to/project/test_repository
    """
    # Check environment variable (highest priority)
    env_path = os.getenv('TEST_REPO_PATH')
    if env_path:
        path = Path(env_path)
        if path.is_absolute():
            return path
        else:
            # Relative to project root
            project_root = Path(__file__).parent.parent.parent
            return (project_root / path).resolve()
    
    # TODO: Check config file (future enhancement)
    # config_path = get_config_file_path()
    # if config_path and config_path.exists():
    #     config = load_config(config_path)
    #     repo_path = config.get('repository', {}).get('test_repo_path')
    #     if repo_path:
    #         return Path(repo_path).resolve()
    
    # Default: test_repository in project root
    project_root = Path(__file__).parent.parent.parent
    default_path = project_root / "test_repository"
    return default_path.resolve()


def get_project_root() -> Path:
    """
    Get project root directory.
    
    Returns:
        Path to project root (absolute path)
    """
    # Check environment variable
    env_root = os.getenv('PROJECT_ROOT')
    if env_root:
        return Path(env_root).resolve()
    
    # Default: parent of test_analysis directory
    project_root = Path(__file__).parent.parent.parent
    return project_root.resolve()


def get_language_config_path() -> Optional[Path]:
    """
    Get path to language configuration file.
    
    Returns:
        Path to language_configs.yaml, or None if not found
    """
    # Check environment variable
    env_config = os.getenv('LANGUAGE_CONFIG_PATH')
    if env_config:
        config_path = Path(env_config)
        if config_path.exists():
            return config_path.resolve()
    
    # Default: config/language_configs.yaml in project root
    project_root = get_project_root()
    default_config = project_root / "config" / "language_configs.yaml"
    if default_config.exists():
        return default_config.resolve()
    
    return None
