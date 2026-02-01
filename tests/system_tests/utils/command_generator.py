"""Generate shell commands from YAML configuration.

This module provides the CommandGenerator class to generate coldfront management
commands from YAML configuration files, which can be written to shell scripts
for manual execution.
"""

from pathlib import Path
from typing import List, Dict, Any

from .yaml_loader import load_users_config


class CommandGenerator:
    """Generate coldfront commands from YAML config."""
    
    def __init__(self, config_path: str):
        """Initialize the command generator with a YAML config file.
        
        Args:
            config_path: Path to users.yaml configuration file
        """
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        # Load config using yaml_loader to get defaults applied
        self.config = load_users_config(str(self.config_path))
    
    def generate_user_commands(self) -> List[str]:
        """Generate create_user commands for all users.
        
        Returns:
            List of create_user command strings (without 'coldfront' prefix)
        """
        commands = []
        defaults = self.config.get('defaults', {})
        
        # Manager users
        for user in self.config.get('managers', []):
            cmd = self._build_create_user_cmd(user, defaults)
            commands.append(cmd)
        
        # Regular users
        for user in self.config.get('users', []):
            cmd = self._build_create_user_cmd(user, defaults)
            commands.append(cmd)
        
        return commands
    
    def generate_amf_commands(self) -> List[str]:
        """Generate set_user_amf commands for users with maintenance status.
        
        Returns:
            List of set_user_amf command strings (without 'coldfront' prefix)
        """
        commands = []
        
        for user in self.config.get('users', []):
            maint = user.get('maintenance')
            if maint and maint.get('status') != 'inactive':
                username = user['username']
                status = maint['status']
                project = maint['project']
                cmd = f"set_user_amf {username} {status} --project {project} --force --quiet"
                commands.append(cmd)
        
        return commands
    
    def _build_create_user_cmd(self, user: Dict[str, Any], defaults: Dict[str, Any]) -> str:
        """Build a single create_user command string.
        
        Args:
            user: User dictionary from config
            defaults: Default values dictionary
            
        Returns:
            Command string (without 'coldfront' prefix)
        """
        username = user['username']
        email = user.get('email', f"{username}@{defaults.get('email_domain', 'example.com')}")
        
        cmd = f"create_user {username} --email {email}"
        
        # Add to groups if specified
        for group in user.get('groups', []):
            cmd += f" --add-to-group {group}"
        
        cmd += " --force --quiet"
        return cmd
    
    def write_script(self, output_path: str, include_projects: bool = False) -> None:
        """Write all commands to a shell script.
        
        Args:
            output_path: Path where the shell script should be written
            include_projects: If True, include set_user_amf commands (requires
                            projects to exist first)
        """
        commands = []
        
        # Group setup commands
        commands.append("# Setup manager groups")
        commands.append("setup_billing_manager --create-group")
        commands.append("setup_rental_manager --create-group")
        commands.append("setup_rate_manager --create-group")
        commands.append("")
        
        # User creation commands
        commands.append("# Create users")
        commands.extend(self.generate_user_commands())
        commands.append("")
        
        # AMF commands (after projects exist)
        if include_projects:
            commands.append("# Set maintenance status (run after projects created)")
            commands.extend(self.generate_amf_commands())
        
        output_path = Path(output_path)
        with open(output_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Generated commands for Module 01: User Management\n")
            f.write("set -e\n\n")
            for cmd in commands:
                if cmd.startswith('#') or cmd == '':
                    f.write(f"{cmd}\n")
                else:
                    f.write(f"coldfront {cmd}\n")
        
        # Make script executable
        output_path.chmod(0o755)
