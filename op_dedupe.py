#!/usr/bin/env python3

import logging
import sys

import gui_tkinter


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        stream=sys.stderr)

    vault = None
    if len(sys.argv) >= 2:
        vault = sys.argv[1]
    tool = gui_tkinter.TkinterGUI(vault)
    tool.run()


if __name__ == "__main__":
    main()
