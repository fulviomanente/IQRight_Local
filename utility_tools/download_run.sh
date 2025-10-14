
#!/bin/bash

# FTP connection details
FTP_HOST="192.168.7.139"
FTP_PORT="5009"
FTP_DIR="mesh"
FTP_FILE="mesh_test_client_new.py"
FTP_LIB="meshstatic_new.py"
FILES_TO_DOWNLOAD=("mesh_test_client_new.py" "meshstatic_new.py")

# Local settings
DOWNLOAD_DIR="./downloaded_files"
VENV_PATH=".venv/bin/activate"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_message() {
    echo -e "${2}${1}${NC}"
}

# Create download directory if it doesn't exist
if [ ! -d "$DOWNLOAD_DIR" ]; then
    mkdir -p "$DOWNLOAD_DIR"
    print_message "Created download directory: $DOWNLOAD_DIR" "$GREEN"
fi

# Change to download directory
cd "$DOWNLOAD_DIR" || exit 1

print_message "Connecting to FTP server $FTP_HOST:$FTP_PORT..." "$YELLOW"

print_message "Using standard ftp for connection..." "$YELLOW"

# FTP commands script
FTP_SCRIPT=$(mktemp)
cat > "$FTP_SCRIPT" << EOF

user fulviomanente 1234
cd $FTP_DIR
binary
get $FTP_FILE
get $FTP_LIB
bye
EOF

# Execute FTP with custom port
ftp -n -v $FTP_HOST $FTP_PORT < "$FTP_SCRIPT"

if [ $? -eq 0 ]; then
    print_message "Files downloaded successfully using ftp!" "$GREEN"
else
    print_message "Error downloading files with ftp!" "$RED"
    exit 1
fi

# Return to original directory
cd ..

# Check if downloaded files exist
for file in "${FILES_TO_DOWNLOAD[@]}"; do
    if [ ! -f "$DOWNLOAD_DIR/$file" ]; then
        print_message "Error: $file was not downloaded!" "$RED"
        exit 1
    fi
done

print_message "All files downloaded successfully!" "$GREEN"

# Check if virtual environment exists
if [ ! -f "$VENV_PATH" ]; then
    print_message "Error: Virtual environment not found at $VENV_PATH" "$RED"
    print_message "Please create it first with: python3 -m venv .venv" "$YELLOW"
    exit 1
fi

# Activate virtual environment and run the Python script
print_message "Activating virtual environment..." "$YELLOW"
source "$VENV_PATH"

# Check if activation was successful
if [ -z "$VIRTUAL_ENV" ]; then
    print_message "Error: Failed to activate virtual environment!" "$RED"
    exit 1
fi

print_message "Virtual environment activated: $VIRTUAL_ENV" "$GREEN"

# Run the Python script
print_message "Running test.py..." "$YELLOW"
python "$DOWNLOAD_DIR/$FTP_FILE"

if [ $? -eq 0 ]; then
    print_message "Script executed successfully!" "$GREEN"
else
    print_message "Error executing Python script!" "$RED"
    exit 1
fi

print_message "All tasks completed successfully!" "$GREEN"