# op-tools
 Tools for 1Password

# Installation

You'll need to have the 1Password command line tool installed on your system,
and you'll need to have granted it permission to access your vaults from within
the 1Password desktop app.

# Usage

Examples:
  * `./op_dedupe.py`
  * `./op_dedupe.py -- --use_kivy`

# Development

## Initial installation

  python3 -m pip install --upgrade pip setuptools virtualenv
  python3 -m virtualenv kivy_venv

  source kivy_venv/bin/activate
  python3 -m pip install "kivy[base]" kivy_examples