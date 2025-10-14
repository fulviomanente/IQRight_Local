#!/bin/bash

# IQRight LoRa Setup Script
# Handles virtual environment creation/activation and runs Python setup

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Print functions
print_header() {
    echo -e "\n${BOLD}${BLUE}============================================================${NC}"
    echo -e "${BOLD}${BLUE}$1${NC}"
    echo -e "${BOLD}${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Check for Python
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python 3 is not installed. Please install Python 3.7 or later."
        exit 1
    fi

    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_success "Found Python $PYTHON_VERSION"
}

# Check for virtual environment
check_venv() {
    if [ -d ".venv" ]; then
        VENV_DIR=".venv"
        print_info "Found virtual environment: .venv/"
        return 0
    elif [ -d "venv" ]; then
        VENV_DIR="venv"
        print_info "Found virtual environment: venv/"
        return 0
    else
        return 1
    fi
}

# Create virtual environment
create_venv() {
    print_info "Creating virtual environment..."

    if $PYTHON_CMD -m venv .venv; then
        VENV_DIR=".venv"
        print_success "Virtual environment created: .venv/"
    else
        print_error "Failed to create virtual environment"
        print_info "Try installing python3-venv: sudo apt-get install python3-venv"
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    print_info "Activating virtual environment..."

    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        print_success "Virtual environment activated"
    else
        print_error "Cannot find activation script in $VENV_DIR"
        exit 1
    fi
}

# Install base requirements for setup
install_setup_requirements() {
    print_info "Installing base requirements for setup..."

    # Only install what's needed for the setup script itself (basically nothing extra)
    # The setup script will install node-specific requirements after node type is selected

    print_success "Base requirements ready"
}

# Main execution
main() {
    print_header "IQRight Environment Setup"

    # Check Python
    check_python

    # Check for existing venv
    if check_venv; then
        # Virtual environment exists
        activate_venv
    else
        # No virtual environment found
        print_warning "No virtual environment found"
        create_venv
        activate_venv
        install_setup_requirements
    fi

    # Verify we're in venv
    if [ -z "$VIRTUAL_ENV" ]; then
        print_error "Failed to activate virtual environment"
        exit 1
    fi

    print_success "Using virtual environment: $VIRTUAL_ENV"

    # Run Python setup script
    print_header "Running IQRight Setup"
    $PYTHON_CMD setup.py

    # Check if setup was successful
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Setup completed successfully!"
        echo ""
        print_info "Virtual environment is activated. You can now run:"
        echo -e "  ${CYAN}python CaptureLora.py${NC}    (Server)"
        echo -e "  ${CYAN}python scanner_queue.py${NC}   (Scanner)"
        echo -e "  ${CYAN}python repeater.py${NC}        (Repeater)"
        echo ""
        print_warning "Remember to activate the virtual environment before running:"
        echo -e "  ${YELLOW}source $VENV_DIR/bin/activate${NC}"
        echo ""
    else
        print_error "Setup failed"
        exit 1
    fi
}

# Run main function
main
