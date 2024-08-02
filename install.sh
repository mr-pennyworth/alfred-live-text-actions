#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Print commands and their arguments as they are executed.
set -x

NAME="alfred-live-text-actions"
ZIP_FOLDER_NAME="$NAME-main"
REPO="https://github.com/mr-pennyworth/$NAME"
WORKFLOW_ZIP="$REPO/archive/refs/heads/main.zip"

EXTRA_PANE_APP="/Applications/AlfredExtraPane.app"
EXTRA_PANE_INSTALL_SCRIPT="https://raw.githubusercontent.com/mr-pennyworth/alfred-extra-pane/main/install.sh"

# If extra pane app is not installed, install it
if [ ! -d "$EXTRA_PANE_APP" ]; then
  curl -sL "$EXTRA_PANE_INSTALL_SCRIPT" | sh
fi

# Download the workflow code
curl -sL "$WORKFLOW_ZIP" -o "/tmp/$NAME.zip"

# Unzip the workflow code
if [ -d "/tmp/$ZIP_FOLDER_NAME" ]; then
  rm -r "/tmp/$ZIP_FOLDER_NAME"
fi
unzip -q "/tmp/$NAME.zip" -d "/tmp"

# Package the workflow
cd "/tmp/$ZIP_FOLDER_NAME"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt >&2
zip -qr "$NAME.alfredworkflow" *

# Install the workflow
open "$NAME.alfredworkflow"
