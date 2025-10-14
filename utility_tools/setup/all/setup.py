#!/usr/bin/env python3
"""
IQRight LoRa Setup Script

Interactive setup for configuring a device as Server, Scanner, or Repeater.
Creates necessary directories, copies data files, and configures node settings.
"""

import os
import shutil
import sys
from pathlib import Path

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def get_node_type():
    """Prompt user to select node type"""
    print(f"{Colors.BOLD}Select Node Type:{Colors.ENDC}")
    print(f"  {Colors.OKBLUE}1{Colors.ENDC} - Server   (Node ID: 1)")
    print(f"  {Colors.OKBLUE}2{Colors.ENDC} - Scanner  (Node ID: 100-199)")
    print(f"  {Colors.OKBLUE}3{Colors.ENDC} - Repeater (Node ID: 200-256)")

    while True:
        try:
            choice = input(f"\n{Colors.BOLD}Enter choice (1-3): {Colors.ENDC}").strip()
            if choice in ['1', '2', '3']:
                return int(choice)
            else:
                print_error("Invalid choice. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\n\nSetup cancelled by user.")
            sys.exit(0)


def get_node_id(node_type):
    """Prompt user for node ID based on node type"""
    if node_type == 1:  # Server
        print_info("Server always uses Node ID: 1")
        return 1

    if node_type == 2:  # Scanner
        min_id, max_id = 100, 199
        default_id = 102
        node_name = "Scanner"
    else:  # Repeater
        min_id, max_id = 200, 256
        default_id = 200
        node_name = "Repeater"

    print(f"\n{Colors.BOLD}{node_name} Node ID must be between {min_id} and {max_id}{Colors.ENDC}")

    while True:
        try:
            user_input = input(f"Enter Node ID (or press Enter for {default_id}): ").strip()

            if user_input == "":
                return default_id

            node_id = int(user_input)
            if min_id <= node_id <= max_id:
                return node_id
            else:
                print_error(f"Node ID must be between {min_id} and {max_id}")
        except ValueError:
            print_error("Please enter a valid number")
        except KeyboardInterrupt:
            print("\n\nSetup cancelled by user.")
            sys.exit(0)


def create_directories(base_path):
    """Create necessary directories"""
    print_info("Creating directories...")

    directories = ['log', 'data']

    for dir_name in directories:
        dir_path = base_path / dir_name
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created directory: {dir_name}/")
        except Exception as e:
            print_error(f"Failed to create {dir_name}/: {e}")
            return False

    return True


def copy_data_files(base_path):
    """Copy all .iqr files to data directory"""
    print_info("Copying data files...")

    data_dir = base_path / 'data'
    iqr_files_found = False

    # Search for .iqr files in current directory
    for iqr_file in base_path.glob('*.iqr'):
        iqr_files_found = True
        try:
            dest_file = data_dir / iqr_file.name
            shutil.copy2(iqr_file, dest_file)
            print_success(f"Copied {iqr_file.name} to data/")
        except Exception as e:
            print_error(f"Failed to copy {iqr_file.name}: {e}")

    # Also copy offline.key if it exists
    key_file = base_path / 'offline.key'
    if key_file.exists():
        try:
            shutil.copy2(key_file, data_dir / 'offline.key')
            print_success(f"Copied offline.key to data/")
        except Exception as e:
            print_error(f"Failed to copy offline.key: {e}")

    if not iqr_files_found:
        print_warning("No .iqr files found in current directory")

    return True


def copy_config_file(base_path, node_type):
    """Copy appropriate config file to utils/config.py"""
    print_info("Configuring node type...")

    config_files = {
        1: 'config.server.py',
        2: 'config.scanner.py',
        3: 'config.repeater.py'
    }

    source_config = base_path / 'configs' / config_files[node_type]
    dest_config = base_path / 'utils' / 'config.py'

    if not source_config.exists():
        print_error(f"Config file not found: {source_config}")
        return False

    try:
        # Backup existing config
        if dest_config.exists():
            backup_config = dest_config.with_suffix('.py.backup')
            shutil.copy2(dest_config, backup_config)
            print_info(f"Backed up existing config to config.py.backup")

        # Copy new config
        shutil.copy2(source_config, dest_config)
        print_success(f"Installed {config_files[node_type]} as utils/config.py")
        return True
    except Exception as e:
        print_error(f"Failed to copy config file: {e}")
        return False


def create_env_file(base_path, node_id, node_type):
    """Create or update .env file with node ID and node-specific variables"""
    print_info("Creating .env file...")

    env_file = base_path / '.env'

    try:
        with open(env_file, 'w') as f:
            f.write(f"# IQRight LoRa Configuration\n\n")

            # Common LoRa settings
            f.write(f"# LoRa Settings\n")
            f.write(f"LORA_NODE_ID={node_id}\n")
            f.write(f"LORA_FREQUENCY=915.23\n")
            f.write(f"LORA_TX_POWER=23\n")
            f.write(f"LORA_ENABLE_CA=TRUE\n\n")

            # Server-specific settings
            if node_type == 1:  # Server
                f.write(f"# Server Settings\n")
                f.write(f"# DO NOT forget to setup DEBUG = false before going live\n")
                f.write(f"DEBUG=TRUE\n")
                f.write(f"env=prod\n")
                f.write(f"FACILITY=1\n")
                f.write(f"FLASK_RUN_PORT=5001\n")
                f.write(f"PROJECT_ID=iqright\n\n")

                f.write(f"# Google Cloud (optional)\n")
                f.write(f"# GOOGLE_APPLICATION_CREDENTIALS=iqright-credentials.json\n")
                f.write(f"# GOOGLE_CLOUD_PROJECT=iqright\n\n")

            # Development/Testing flag
            f.write(f"# Set LOCAL=TRUE for development/testing without hardware\n")
            f.write(f"# LOCAL=FALSE\n")

        print_success(f"Created .env with NODE_ID={node_id}")
        return True
    except Exception as e:
        print_error(f"Failed to create .env file: {e}")
        return False


def install_requirements(base_path, node_type):
    """Install node-specific requirements"""
    print_info("Installing Python dependencies...")

    requirements_files = {
        1: 'requirements.server.txt',
        2: 'requirements.scanner.txt',
        3: 'requirements.repeater.txt'
    }

    requirements_file = base_path / 'configs' / requirements_files[node_type]

    if not requirements_file.exists():
        print_error(f"Requirements file not found: {requirements_file}")
        return False

    try:
        import subprocess
        print_info(f"Installing from {requirements_files[node_type]}...")
        print_info("This may take a few minutes...")

        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print_success("Dependencies installed successfully")
            return True
        else:
            print_error("Failed to install dependencies")
            print_error(result.stderr)
            return False
    except Exception as e:
        print_error(f"Error installing dependencies: {e}")
        return False


def main():
    """Main setup function"""
    print_header("IQRight LoRa Setup")

    base_path = Path(__file__).parent.absolute()

    # Get node type
    node_type = get_node_type()
    node_names = {1: 'Server', 2: 'Scanner', 3: 'Repeater'}
    print_success(f"Selected: {node_names[node_type]}")

    # Get node ID
    node_id = get_node_id(node_type)
    print_success(f"Node ID: {node_id}")

    # Confirm settings
    print(f"\n{Colors.BOLD}Configuration Summary:{Colors.ENDC}")
    print(f"  Node Type: {Colors.OKBLUE}{node_names[node_type]}{Colors.ENDC}")
    print(f"  Node ID:   {Colors.OKBLUE}{node_id}{Colors.ENDC}")

    confirm = input(f"\n{Colors.BOLD}Proceed with setup? (y/n): {Colors.ENDC}").strip().lower()
    if confirm != 'y':
        print("\nSetup cancelled.")
        sys.exit(0)

    print()

    # Create directories
    if not create_directories(base_path):
        print_error("Setup failed: Could not create directories")
        sys.exit(1)

    # Copy data files
    copy_data_files(base_path)

    # Copy config file
    if not copy_config_file(base_path, node_type):
        print_error("Setup failed: Could not configure node")
        sys.exit(1)

    # Create .env file
    if not create_env_file(base_path, node_id, node_type):
        print_error("Setup failed: Could not create .env file")
        sys.exit(1)

    # Install requirements
    if not install_requirements(base_path, node_type):
        print_warning("Failed to install some dependencies")
        print_warning("You may need to install them manually:")
        print_warning(f"  pip install -r configs/{['requirements.server.txt', 'requirements.scanner.txt', 'requirements.repeater.txt'][node_type-1]}")

    # Success!
    print_header("Setup Complete!")

    print(f"{Colors.OKGREEN}Your {node_names[node_type]} (Node ID: {node_id}) is configured!{Colors.ENDC}\n")

    # Show next steps
    print(f"{Colors.BOLD}Next Steps:{Colors.ENDC}")
    if node_type == 1:  # Server
        print(f"  1. Start the server:")
        print(f"     {Colors.OKCYAN}python CaptureLora.py{Colors.ENDC}")
    elif node_type == 2:  # Scanner
        print(f"  1. Make sure data files are in data/ directory")
        print(f"  2. Start the scanner:")
        print(f"     {Colors.OKCYAN}python scanner_queue.py{Colors.ENDC}")
    else:  # Repeater
        print(f"  1. Start the repeater:")
        print(f"     {Colors.OKCYAN}python repeater.py{Colors.ENDC}")

    print(f"\n{Colors.BOLD}Configuration Files:{Colors.ENDC}")
    print(f"  Config: {Colors.OKCYAN}utils/config.py{Colors.ENDC}")
    print(f"  Env:    {Colors.OKCYAN}.env{Colors.ENDC}")
    print(f"  Logs:   {Colors.OKCYAN}log/{Colors.ENDC}")
    print(f"  Data:   {Colors.OKCYAN}data/{Colors.ENDC}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
