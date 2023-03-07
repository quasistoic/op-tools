# op-tools
 Tools for 1Password

# Installation

You'll need to have the 1Password command line tool installed on your system,
and you'll need to have granted it permission to access your vaults from within
the 1Password desktop app.

# Usage

App will use the Kivy GUI by default if available in the evironment, otherwise
will fall back to the Tkinter GUI. I don't recommend the Tkinter GUI, and it's
not likely to get a lot of love going forward.

```
source kivy_venv/bin/activate
./op_dedupe.py
```

# Development

# Initial installation

```
python3 -m pip install --upgrade pip setuptools virtualenv
python3 -m virtualenv kivy_venv

source kivy_venv/bin/activate
```