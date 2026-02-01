"""YAML configuration loader for system tests.

This module provides functions to load and parse YAML configuration files
for users and projects, with support for defaults and variable substitution.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


# Module-level cache for loaded configurations
_users_config: Optional[Dict[str, Any]] = None
_projects_config: Optional[Dict[str, Any]] = None


def _substitute_variables(text: str, variables: Dict[str, Any]) -> str:
    """Substitute variables in a string using ${key} syntax.
    
    Args:
        text: String that may contain variable references like ${defaults.email_domain}
        variables: Dictionary of variables for substitution
        
    Returns:
        String with variables substituted
    """
    if not isinstance(text, str):
        return text
    
    def replace_var(match):
        var_path = match.group(1)
        keys = var_path.split('.')
        value = variables
        try:
            for key in keys:
                value = value[key]
            return str(value)
        except (KeyError, TypeError):
            return match.group(0)  # Return original if not found
    
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, text)


def _apply_defaults(user: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default values to a user dictionary.
    
    Args:
        user: User dictionary
        defaults: Default values dictionary
        
    Returns:
        User dictionary with defaults applied
    """
    user = user.copy()
    
    # Apply defaults for missing fields
    if 'email' not in user and 'username' in user:
        email_domain = defaults.get('email_domain', 'mit.edu')
        user['email'] = f"{user['username']}@{email_domain}"
    
    if 'password' not in user:
        user['password'] = defaults.get('password', 'TestPass123!')
    
    # Substitute variables in string fields
    for key, value in user.items():
        if isinstance(value, str):
            # Create a variables dict with defaults for substitution
            vars_dict = {'defaults': defaults}
            user[key] = _substitute_variables(value, vars_dict)
    
    return user


def load_users_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and parse users configuration from YAML file.
    
    Args:
        config_path: Path to users.yaml file. If None, uses default path
                     relative to this file.
        
    Returns:
        Dictionary containing parsed users configuration with defaults applied
    """
    global _users_config
    
    if _users_config is not None:
        return _users_config
    
    if config_path is None:
        # Default path relative to this file
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / 'config' / 'users.yaml'
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        # Check if example file exists
        example_path = config_path.with_suffix('.yaml.example')
        if example_path.exists():
            raise FileNotFoundError(
                f"Users config file not found: {config_path}\n"
                f"An example file exists at: {example_path}\n"
                f"Copy it to {config_path} and customize for your environment."
            )
        raise FileNotFoundError(f"Users config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config:
        raise ValueError(f"Empty or invalid YAML file: {config_path}")
    
    defaults = config.get('defaults', {})
    
    # Apply defaults to managers
    managers = []
    for manager in config.get('managers', []):
        managers.append(_apply_defaults(manager, defaults))
    
    # Apply defaults to users
    users = []
    for user in config.get('users', []):
        users.append(_apply_defaults(user, defaults))
    
    _users_config = {
        'version': config.get('version'),
        'defaults': defaults,
        'managers': managers,
        'users': users
    }
    
    return _users_config


def load_projects_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and parse projects configuration from YAML file.
    
    Args:
        config_path: Path to projects.yaml file. If None, uses default path
                     relative to this file.
        
    Returns:
        Dictionary containing parsed projects configuration
    """
    global _projects_config
    
    if _projects_config is not None:
        return _projects_config
    
    if config_path is None:
        # Default path relative to this file
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / 'config' / 'projects.yaml'
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        # Check if example file exists
        example_path = config_path.with_suffix('.yaml.example')
        if example_path.exists():
            raise FileNotFoundError(
                f"Projects config file not found: {config_path}\n"
                f"An example file exists at: {example_path}\n"
                f"Copy it to {config_path} and customize for your environment."
            )
        raise FileNotFoundError(f"Projects config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config:
        raise ValueError(f"Empty or invalid YAML file: {config_path}")
    
    _projects_config = {
        'version': config.get('version'),
        'projects': config.get('projects', [])
    }
    
    return _projects_config


def get_all_users() -> List[Dict[str, Any]]:
    """Return combined list of managers and users.
    
    Returns:
        List of all user dictionaries (managers + users)
    """
    config = load_users_config()
    return config['managers'] + config['users']


def get_users_by_project(project_id: str) -> List[Dict[str, Any]]:
    """Return users associated with a specific project.
    
    A user is associated with a project if:
    - They are the owner of the project
    - They are a member of the project
    - They have maintenance status for the project
    
    Args:
        project_id: Project identifier
        
    Returns:
        List of user dictionaries associated with the project
    """
    projects_config = load_projects_config()
    users_config = load_users_config()
    
    # Find the project
    project = None
    for p in projects_config['projects']:
        if p.get('id') == project_id:
            project = p
            break
    
    if not project:
        return []
    
    # Collect user IDs associated with this project
    user_ids = set()
    
    # Add owner
    owner_id = project.get('owner')
    if owner_id:
        user_ids.add(owner_id)
    
    # Add members
    for member in project.get('members', []):
        member_id = member.get('user_id')
        if member_id:
            user_ids.add(member_id)
    
    # Add users with maintenance status for this project
    for user in users_config['users']:
        maintenance = user.get('maintenance')
        if maintenance and maintenance.get('project') == project_id:
            user_ids.add(user.get('id'))
    
    # Build list of user dictionaries
    all_users = get_all_users()
    project_users = [user for user in all_users if user.get('id') in user_ids]
    
    return project_users


def get_users_with_maintenance() -> List[Dict[str, Any]]:
    """Return users that have maintenance status set.
    
    Returns:
        List of user dictionaries that have a maintenance field
    """
    config = load_users_config()
    
    users_with_maintenance = []
    for user in config['users']:
        if 'maintenance' in user:
            users_with_maintenance.append(user)
    
    return users_with_maintenance
