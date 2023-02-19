#!/usr/bin/env python3

import logging
import os
import pickle
import subprocess
import sys

import tkinter as tk
from tkinter import messagebox


class OpTool:
    def __init__(self, vault):
        self.vault = vault
        self.items = self.get_items()

    def run_command(self, command):
        cache_file = f"./.op-cache/.{self.vault}.{command}.cache"
        if os.path.exists(cache_file):
            logging.info(f"pulling from cache: {cache_file}")
            with open(cache_file, "rb") as f:
                return pickle.load(f)

        op_command = f"op {command}"
        if self.vault:
            op_command += f" --vault {self.vault}"
        logging.info(f"Calling API: {op_command}")
        output = os.popen(op_command).read()
        with open(cache_file, "wb") as f:
            pickle.dump(output, f)
        return output

    def get_items(self):
        output = self.run_command("item list")
        return [line.split()[0] for line in output.split("\n")[3:-1]]

    def get_item_details(self, item):
        output = self.run_command(f"item get {item}")
        details = {}
        for line in output.split("\n"):
            if line.startswith("      "):
                items = line.strip().split(": ")
                if len(items) >= 2:
                    key, value = items[0], items[1]
                    details[key] = value
        return str(details)

    def delete_item(self, item):
        self.run_command(f"delete item {item}")
        self.items.remove(item)

    def find_duplicates(self):
        duplicates = []
        for i, item in enumerate(self.items):
            details = self.get_item_details(item)
            matching_items = [j for j in self.items[i+1:] if self.get_item_details(j) == details]
            if matching_items:
                duplicates.append([item] + matching_items)
        return duplicates

    def show_duplicate_manager(self):
        duplicates = self.find_duplicates()
        if not duplicates:
            messagebox.showinfo('No Duplicates Found', 'No duplicate items were found.')
            return

        logging.info("Found the following duplicates: {}", duplicates)

        root = tk.Tk()
        root.title('1Password Duplicate Manager')
        label = tk.Label(root, text='Select the canonical item for each set of duplicates:')
        label.pack()
        for i, duplicate in enumerate(duplicates):
            canonical_var = tk.BooleanVar()
            canonical_var.set(i == 0)
            archive_var = tk.BooleanVar()
            merge_var = tk.BooleanVar()
            frame = tk.Frame(root)
            frame.pack()
            canonical_checkbutton = tk.Checkbutton(frame, text='Canonical', variable=canonical_var)
            archive_checkbutton = tk.Checkbutton(frame, text='Archive Non-Canonical', variable=archive_var)
            merge_checkbutton = tk.Checkbutton(frame, text='Merge Fields', variable=merge_var)
            canonical_checkbutton.pack(side='left')
            archive_checkbutton.pack(side='left')
            merge_checkbutton.pack(side='left')
            label = tk.Label(root, text=duplicate[0], justify='left')
            label.pack()
        button = tk.Button(root, text='Apply Changes', command=root.quit)
        button.pack()
        root.mainloop()
        # Apply the changes
        for i, duplicate in enumerate(duplicates):
            canonical_var = root.winfo_children()[i*2].winfo_children()[0].var
            archive_var = root.winfo_children()[i*2].winfo_children()[1].var
            merge_var = root.winfo_children()[i*2].winfo_children()[2].var
            if canonical_var.get():
                continue
            for j in range(1, len(duplicate)):
                if archive_var.get():
                    logging.warn(['op', 'archive', 'item', duplicate[j]])
                if merge_var.get():
                    logging.warn(['op', 'edit', 'item', duplicate[0], 'set', 'details', self.get_item_details(duplicate[j])])
                    logging.warn(['op', 'delete', 'item', duplicate[j]])


def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(message)s', stream=sys.stderr)

    if len(sys.argv) != 2:
        print("Usage: python op-dedupe.py VAULT_NAME")
        return

    vault = sys.argv[1]
    tool = OpTool(vault)
    tool.get_items()

    duplicates = tool.find_duplicates()
    if not duplicates:
        print("No duplicate items found.")
        return

    tool.show_duplicate_manager()


if __name__ == "__main__":
    main()