# op-tools
 Tools for 1Password

# Installation

You'll need to have the [1Password command line tool](https://1password.com/downloads/command-line/)
installed on your system, and you'll need to have [granted it permission to
access your vaults](https://developer.1password.com/docs/cli/get-started/#sign-in) from within
the 1Password desktop app.

Once that's installed, you'll need to install Kivy, which is the GUI library on
which we rely. The simplest way to do that is via `pip` with the following set of commands:

```
python3 -m pip install --upgrade pip setuptools virtualenv
python3 -m virtualenv kivy_venv

source kivy_venv/bin/activate
python3 -m pip install "kivy[base]"
```

# Usage

App will use the Kivy GUI by default if available in the evironment, otherwise
will fall back to the Tkinter GUI. I don't recommend the Tkinter GUI, and it's
not likely to get a lot of love going forward.

```
source kivy_venv/bin/activate
./op_dedupe.py
```

# Problems?

So far I've only tested any of this on a couple MacBooks running MacOS Ventura and Python 3.9.

If you run into any problems while using this tool, please do report them to me by filing a bug.
Make sure to include your operating system version, what version of python you're using
(get this by running `python3 --version`), the contents of any error messages that are printed
to the terminal, and descriptions of what you did to get there, what you were expecting to happen,
and what actually happened.

The more detail you can give me, the better, but don't include any password or username data, please.

# Known Issues

You can see the [full list of KIs here](https://github.com/quasistoic/op-tools/issues), but most importantly:

  * [Issue #6](https://github.com/quasistoic/op-tools/issues/6): If you try to copy a list of URLs
    from one item to the others in a duplicate set, only the first URL in that list will be copied.
    This is a relative edge case, but be aware it exists. If this is blocking your workflow, let me
    know more about how and why in [this bug](https://github.com/quasistoic/op-tools/issues/6).
  * [Issue #5](https://github.com/quasistoic/op-tools/issues/5): A lot of your 1Password data ends
    up in an on-disk cache when you use this tool. I'll be building functionality into the app
    itself to delete the cache, but in the meantime, you can delete it yourself by
    running `rm ./.op-cache/*` from the same directory where you've been running the tool.