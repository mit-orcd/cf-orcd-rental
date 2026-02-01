#!/usr/bin/env python
"""Main test runner for system tests with multiple execution modes.

This script provides three execution modes:
1. CI/CD mode (default): Run tests via pytest
2. Command generation mode: Generate shell script from YAML configuration
3. Dry-run mode: Run tests with --dry-run flag

Usage:
    # Run tests normally (CI/CD mode)
    python run_tests.py

    # Run specific test module
    python run_tests.py --module test_01_users

    # Generate command script only
    python run_tests.py --generate-commands-only --output commands.sh

    # Run tests in dry-run mode
    python run_tests.py --dry-run

    # Verbose output
    python run_tests.py --verbose
"""

import argparse
import sys
import subprocess
from pathlib import Path


# Default paths
DEFAULT_CONFIG_PATH = Path(__file__).parent / 'config' / 'users.yaml'
DEFAULT_OUTPUT_SCRIPT = Path(__file__).parent / 'generated_commands.sh'
DEFAULT_TEST_MODULE = 'modules.test_01_users'


def parse_arguments():
    """Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Run system tests with multiple execution modes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Execution mode flags
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run all commands in dry-run mode (no actual changes made)'
    )
    
    parser.add_argument(
        '--generate-commands-only',
        action='store_true',
        help='Generate shell script from YAML without running tests'
    )
    
    # Configuration options
    parser.add_argument(
        '--output',
        type=str,
        default=str(DEFAULT_OUTPUT_SCRIPT),
        help=f'Output path for generated script (default: {DEFAULT_OUTPUT_SCRIPT})'
    )
    
    parser.add_argument(
        '--module',
        type=str,
        default=DEFAULT_TEST_MODULE,
        help=f'Specific test module to run (default: {DEFAULT_TEST_MODULE})'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=str(DEFAULT_CONFIG_PATH),
        help=f'Path to users.yaml config file (default: {DEFAULT_CONFIG_PATH})'
    )
    
    # Output options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()


def run_pytest_tests(module_path, dry_run=False, verbose=False):
    """Run tests using pytest.
    
    Args:
        module_path: Path to test module (e.g., 'modules.test_01_users' or 'modules/test_01_users')
        dry_run: If True, pass --dry-run flag to tests
        verbose: If True, enable verbose pytest output
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # Build pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Convert module path to file path if needed
    # Handle both 'modules.test_01_users' and 'modules/test_01_users' formats
    if '.' in module_path and not module_path.startswith('tests/'):
        # Convert dot notation to file path
        module_file = module_path.replace('.', '/') + '.py'
        test_file = Path(__file__).parent / module_file
    else:
        # Assume it's already a file path
        test_file = Path(__file__).parent / module_path
    
    # If file doesn't exist, try as pytest module path
    if not test_file.exists():
        # Try as pytest module path (e.g., tests.system_tests.modules.test_01_users)
        pytest_module = f'tests.system_tests.{module_path.replace("/", ".").replace(".py", "")}'
        cmd.append(pytest_module)
    else:
        # Use file path (relative to project root for pytest)
        rel_path = test_file.relative_to(Path(__file__).parent.parent.parent)
        cmd.append(str(rel_path))
    
    # Add pytest options
    if verbose:
        cmd.append('-v')
    else:
        cmd.append('-q')
    
    # Add dry-run flag if needed (tests should handle this via environment or args)
    if dry_run:
        cmd.extend(['--dry-run'])
    
    if verbose:
        print(f"Running pytest: {' '.join(cmd)}")
    
    # Run pytest from project root
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)
    return result.returncode


def generate_command_script(config_path, output_path, verbose=False):
    """Generate shell script from YAML configuration.
    
    Args:
        config_path: Path to users.yaml configuration file
        output_path: Path where shell script should be written
        verbose: If True, print additional information
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    try:
        from utils.command_generator import CommandGenerator
        
        config_path = Path(config_path)
        output_path = Path(output_path)
        
        if not config_path.exists():
            # Check if example file exists
            example_path = config_path.with_suffix('.yaml.example')
            if example_path.exists():
                print(f"Error: Config file not found: {config_path}", file=sys.stderr)
                print(f"       An example file exists at: {example_path}", file=sys.stderr)
                print(f"       Copy it to {config_path} and customize for your environment.", file=sys.stderr)
            else:
                print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            return 1
        
        if verbose:
            print(f"Loading configuration from: {config_path}")
            print(f"Generating script to: {output_path}")
        
        # Generate script
        generator = CommandGenerator(str(config_path))
        generator.write_script(str(output_path), include_projects=True)
        
        if verbose:
            print(f"Successfully generated script: {output_path}")
            print(f"Script is executable: {output_path.is_file() and (output_path.stat().st_mode & 0o111)}")
        
        print(f"Generated command script: {output_path}")
        return 0
        
    except ImportError as e:
        print(f"Error: Failed to import command generator: {e}", file=sys.stderr)
        print("Make sure you're running from the correct directory and dependencies are installed.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating command script: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def run_dry_run_tests(module_path, verbose=False):
    """Run tests in dry-run mode.
    
    This mode runs the tests but passes --dry-run flag to all commands,
    ensuring no actual changes are made to the system.
    
    Args:
        module_path: Path to test module
        verbose: If True, enable verbose output
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    if verbose:
        print("Running tests in DRY-RUN mode (no changes will be made)")
    
    # Set environment variable to indicate dry-run mode
    # Tests can check this via BaseSystemTest.run_command(dry_run=True)
    import os
    os.environ['SYSTEM_TEST_DRY_RUN'] = '1'
    
    # Run pytest with dry-run flag
    return run_pytest_tests(module_path, dry_run=True, verbose=verbose)


def determine_execution_mode(args):
    """Determine which execution mode to use based on arguments.
    
    Args:
        args: Parsed arguments
        
    Returns:
        str: Execution mode ('generate', 'dry-run', or 'ci-cd')
    """
    if args.generate_commands_only:
        return 'generate'
    elif args.dry_run:
        return 'dry-run'
    else:
        return 'ci-cd'


def main():
    """Main entry point for the test runner.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    args = parse_arguments()
    mode = determine_execution_mode(args)
    
    if args.verbose:
        print(f"Execution mode: {mode}")
        print(f"Test module: {args.module}")
        if mode == 'generate':
            print(f"Config: {args.config}")
            print(f"Output: {args.output}")
    
    # Execute based on mode
    if mode == 'generate':
        return generate_command_script(
            config_path=args.config,
            output_path=args.output,
            verbose=args.verbose
        )
    elif mode == 'dry-run':
        return run_dry_run_tests(
            module_path=args.module,
            verbose=args.verbose
        )
    else:  # ci-cd mode
        return run_pytest_tests(
            module_path=args.module,
            dry_run=False,
            verbose=args.verbose
        )


if __name__ == '__main__':
    sys.exit(main())
