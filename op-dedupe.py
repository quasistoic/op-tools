#!/usr/bin/env python3

import logging
import os
import pickle
import subprocess
import sys

import tkinter as tk
from tkinter import messagebox

from urllib.parse import urlparse


def get_domain_from_url(url):
    """Return the domain of a URL.

    Args:
        url (str): A string representing the URL.

    Returns:
        str: The domain of the URL.
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


class ItemDetails:

    def __init__(self, serialized):
        self.id = None
        self.serialized = serialized
        self.domains = set([])
        details = {}
        for line in serialized.split("\n"):
            items = line.strip().split(": ")
            if len(items) >= 2:
                key = items[0].strip()
                values = []
                for i in items[1:]:
                    stripped = i.strip()
                    if stripped != "http:// (primary)" and get_domain_from_url(stripped):
                        self.domains.add(get_domain_from_url(stripped))
                    values.append(stripped)
                details[key] = values
        self.fields = details
        self.id = self.fields['ID'][0]
        if self.domains:
            logging.debug(f"Domains for {self.fields['ID']} : {self.domains}")

    def __str__(self):
        return str(sorted(self.fields.items()))

    def is_duplicate(self, other):
        return bool(self.get_shared_domains(other))

    def get_shared_domains(self, other):
        return self.domains & other.domains



class OpTool:

    def __init__(self, vault):
        self.vault = vault
        self.create_root()
        self.items = self.get_items()

    def create_root(self):
        self.root = tk.Tk()
        self.root.title('1Password Duplicate Manager')

    def run_command(self, command, skip_cache=False):
        cache_file = f"./.op-cache/.{self.vault}.{command}.cache"
        if not skip_cache:
            if os.path.exists(cache_file):
                logging.debug(f"pulling from cache: {cache_file}")
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

    def get_items(self, force_refresh=False):
        output = self.run_command("item list", skip_cache=force_refresh)
        items = [line.split()[0] for line in output.split("\n")[3:-1]]
        logging.info(f"Found {len(items)} total items.")
        return items

    def get_item_details(self, item):
        output = self.run_command(f"item get {item}")
        return ItemDetails(output)

    def archive_item(self, item_id):
        logging.warning(f"Archiving item {item_id}")
        self.run_command(f"item delete {item_id} --archive")
        self.items = self.get_items(force_refresh=True)
        self.root.destroy()
        self.create_root()
        self.run()

    def find_duplicates(self):
        duplicates = []
        for i, item in enumerate(self.items):
            details = self.get_item_details(item)
            if details:
                matching_items = []
                for j in self.items[i+1:]:
                    j_details = self.get_item_details(j)
                    if j_details.is_duplicate(details) and str(j_details) != str(details):
                        matching_items.append(j_details)
                if matching_items:
                    logging.debug(f"Found duplicates: {item}\n{matching_items}")
                    duplicates.append([details] + matching_items)

        logging.info(f"Found {len(duplicates)} sets of duplicates.")
        return duplicates

    def apply_changes(self, selected_items):
        """Apply changes to the given set of duplicates."""
        for item in selected_items:
            self.archive_item(item.id)

    def display_duplicate_set(self, duplicate_set):
        """Display the selected duplicate set for management."""
        items = [self.get_item_details(item.id) for item in duplicate_set]
        field_names = sorted(set(field_name for item in items for field_name in item.fields.keys()))
        field_values = [[item.fields.get(field_name, '') for field_name in field_names] for item in items]
        archive_vars = [tk.BooleanVar(value=False) for item in items]

        top = tk.Toplevel(self.root)
        top.title('1Password Duplicate Manager')

        # Create table frame and header
        table_frame = tk.Frame(top)
        table_frame.pack(side="top", fill="both", expand=True)

        # Create header row with Archive checkboxes
        header_frame = tk.Frame(table_frame, relief=tk.RIDGE, borderwidth=1)
        header_frame.pack(side="top", fill="both", expand=True)
        tk.Label(header_frame, text="Archive").pack(side="left", fill="both", expand=True)
        for i, item in enumerate(items):
            header_cell = tk.Frame(header_frame, relief=tk.RIDGE, borderwidth=1)
            header_cell.pack(side="left", fill="both", expand=True)
            options_cell = tk.Frame(header_cell, relief=tk.RIDGE, borderwidth=1)
            options_cell.pack(side="bottom")
            tk.Label(header_cell, text=item.id).pack(side="left", fill="both", expand=True)
            archive_cb = tk.Checkbutton(options_cell, text='Archive', variable=archive_vars[i])
            archive_cb.pack(side="bottom")

        # Create table rows
        for j, field_name in enumerate(field_names):
            if field_name in ['ID', 'Version', 'Tags']:
                continue
            row_has_diff_values = any(item.fields.get(field_name) != field_values[0][j] for item in items)
            if row_has_diff_values:
                row_frame = tk.Frame(table_frame, relief=tk.RIDGE, borderwidth=1)
                row_frame.pack(side="top", fill="both", expand=True)
                tk.Label(row_frame, text=field_name).pack(side="left", fill="both", expand=True)
                for i in range(len(duplicate_set)):
                    row_cell = tk.Frame(row_frame, relief=tk.RIDGE, borderwidth=1)
                    row_cell.pack(side="left", fill="both", expand=True)
                    field_value = field_values[i][j]
                    label = tk.Label(row_cell, text=field_value)
                    label.pack(side="top", fill="both", expand=True)

        def apply():
            selected_items = [item for i, item in enumerate(items) if archive_vars[i].get()]
            top.destroy()
            self.apply_changes(selected_items)

        apply_button = tk.Button(top, text="Apply Changes", command=apply)
        apply_button.pack()

        top.mainloop()


    def run(self):
        duplicates = self.find_duplicates()
        if not duplicates:
            messagebox.showinfo('No Duplicates Found', 'No duplicate items were found.')
            return

        logging.debug("Found the following duplicates: {}", duplicates)

        for i, duplicate_set in enumerate(duplicates):
            button_text = duplicate_set[0].get_shared_domains(duplicate_set[1])
            button = tk.Button(self.root, text=button_text,
                               command=lambda i=i: self.display_duplicate_set(duplicates[i]))
            button.pack()

        self.root.mainloop()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        stream=sys.stderr)

    if len(sys.argv) != 2:
        print("Usage: python op-dedupe.py VAULT_NAME")
        return

    vault = sys.argv[1]
    tool = OpTool(vault)
    tool.run()


if __name__ == "__main__":
    main()