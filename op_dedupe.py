#!/usr/bin/env python3

import argparse
import logging
import sys

import gui_kivy
import gui_tkinter

GUI_TYPE = "kivy"


def init_argparse():
    parser = argparse.ArgumentParser(
        description='Find and manage duplicate items in 1Password.')
    parser.add_argument('--vault', type=str, help='Act only on this vault.')
    parser.add_argument('--use_kivy', action='store_true', default=False,
        help='Use the alpha Kivy GUI library instead of Tkinter')
    return parser

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        stream=sys.stderr)

    parser = init_argparse()
    args = parser.parse_args()

    vault = None
    if args.vault:
        vault = args.vault

    if args.use_kivy:
        tool = gui_kivy.KivyGUI(vault)
    else:
        tool = gui_tkinter.TkinterGUI(vault)
    tool.run()


if __name__ == "__main__":
    main()
