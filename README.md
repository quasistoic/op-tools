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

# Why does this exist?

I was one of the many, many people who switched away from LastPass to 1Password
after the huge breaches that LastPass suffered in 2022. When I made the switch,
I chose to import into 1Password not only all my old LastPass entries, but also
all the passwords I had saved in Chrome. This created a ton of duplicate entries,
many of which were not perfect duplicates, as they varied in exactly what URL was
associated with the entry, as well as sometimes varying in the stored usernames
and passwords. Trying to pare down this list of duplicates at the same time I was
trying to reset all my passwords was a huge pain, and 1Password didn't yet provide
any built-in tools to assist with these tasks.

I created the first versions of this code in the passenger seat of a car driving
down a rural Nevada highway, asking ChatGPT to draft up initial versions of the code
and then trying them out and refining them until they did more or less what I wanted
them to do. For that first version, my goal was to only use python built-ins, with
the idea that this would make it easy for other people to use the same code without
having to download a bunch of other dependencies. Unfortunately, the first time
I tried to get my wife to run this code on her computer, I learned how awful the
version of Tkinter is that is distributed by default with MacOS.

That initial version of the code using Tkinter is, as of this writing, still included
in this project, and still technically usable, if you happen to have a good version
of the Tkinter libraries running on your machine. However, I have since rewritten
all the GUI code in Kivy and have made that new GUI the default if you have Kivy
installed. I will likely remove the Tkinter version eventually, and I do highly
recommend using the Kivy version. If you happen to prefer the Tkinter version and
don't want me to kill it, I would like to know why.

The current version does a lot of on-disk caching. I initially did this because my
internet connection was not stable while driving down the highway, but I later
discovered that the 1Password API was slow enough that I really need to keep that
cache around for the app to be reasonably performant. The first time you run the app,
it's going to take a while to start up as it downloads all the necessary data.
Subsequent times, it should only take a few seconds to start, unless you've
cleared the cache manually. If you don't intend to run the app again for a while,
I do recommend clearing the cache by following the instructions under the
Known Issues section. I do hope/intend to make this process easier and clearer
in the future.