"""Base test class with command execution utilities."""

import subprocess
import os
from pathlib import Path


class BaseSystemTest:
    """Base class for system tests with command helpers."""
    
    # Class-level configuration (can be set by setup or environment)
    # COLDFRONT_DIR is set by activate_env.sh as ORCD_PLUGIN_DIR's parent
    coldfront_dir = os.environ.get('COLDFRONT_DIR', os.environ.get('ORCD_PLUGIN_DIR', ''))
    
    @classmethod
    def run_command(cls, command, dry_run=False, capture=True):
        """Execute a coldfront management command.
        
        Args:
            command: Command string (without 'coldfront' prefix)
            dry_run: If True, append --dry-run flag
            capture: If True, capture and return output
            
        Returns:
            tuple: (return_code, stdout, stderr)
        """
        cmd = f"coldfront {command}"
        if dry_run:
            cmd += " --dry-run"
        
        # Build environment with all required variables
        env = os.environ.copy()
        env.setdefault('DJANGO_SETTINGS_MODULE', 'coldfront.config.settings')
        
        # Determine ColdFront directory from environment or class attribute
        coldfront_dir = cls.coldfront_dir
        if not coldfront_dir:
            # Try to find it relative to workspace
            workspace = os.environ.get('WORKSPACE', os.environ.get('GITHUB_WORKSPACE', ''))
            if workspace:
                potential_dir = os.path.join(workspace, 'coldfront')
                if os.path.isdir(potential_dir):
                    coldfront_dir = potential_dir
        
        # Ensure PYTHONPATH includes ColdFront directory if set
        if coldfront_dir:
            pythonpath = env.get('PYTHONPATH', '')
            if coldfront_dir not in pythonpath:
                env['PYTHONPATH'] = f"{coldfront_dir}:{pythonpath}" if pythonpath else coldfront_dir
        
        # Determine working directory (prefer ColdFront dir if available)
        cwd = coldfront_dir if coldfront_dir and os.path.isdir(coldfront_dir) else None
        
        result = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True, env=env, cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    
    @classmethod
    def generate_command_script(cls, commands, output_path):
        """Generate a shell script with runnable commands.
        
        Args:
            commands: List of command strings
            output_path: Path to write the script
        """
        with open(output_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Auto-generated commands for manual execution\n")
            f.write("set -e\n\n")
            for cmd in commands:
                f.write(f"coldfront {cmd}\n")
        os.chmod(output_path, 0o755)
