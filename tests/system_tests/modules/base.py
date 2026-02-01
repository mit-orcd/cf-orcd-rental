"""Base test class with command execution utilities."""

import subprocess
import os
from pathlib import Path

class BaseSystemTest:
    """Base class for system tests with command helpers."""
    
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
        
        result = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True
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
