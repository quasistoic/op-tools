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
        self.items = self.get_items()

    def run_command(self, command):
        cache_file = f"./.op-cache/.{self.vault}.{command}.cache"
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

    def get_items(self):
        output = self.run_command("item list")
        return [line.split()[0] for line in output.split("\n")[3:-1]]

    def get_item_details(self, item):
        output = self.run_command(f"item get {item}")
        return ItemDetails(output)

    def delete_item(self, item):
        self.run_command(f"delete item {item}")
        self.items.remove(item)

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

    def show_duplicate_manager(self):
        duplicates = self.find_duplicates()
        if not duplicates:
            messagebox.showinfo('No Duplicates Found', 'No duplicate items were found.')
            return

        logging.debug("Found the following duplicates: {}", duplicates)

        def apply_changes():
            for i, duplicate_set in enumerate(duplicates):
                canonical_var = root.winfo_children()[i*2].winfo_children()[0].var
                archive_var = root.winfo_children()[i*2].winfo_children()[1].var
                merge_var = root.winfo_children()[i*2].winfo_children()[2].var
                if canonical_var.get():
                    continue
                for j in range(1, len(duplicate_set)):
                    if archive_var.get():
                        logging.warning(['op', 'archive', 'item', duplicate_set[j].id], file=sys.stderr)
                    if merge_var.get():
                        logging.warning(['op', 'edit', 'item', duplicate_set[0].id, 'set', 'details',
                            self.get_item_details(duplicate_set[j].id)], file=sys.stderr)
                        logging.warning(['op', 'delete', 'item', duplicate_set[j].id], file=sys.stderr)

        def display_duplicate_set(i, root):
            nonlocal duplicates
            root.destroy()
            root = tk.Tk()
            root.title('1Password Duplicate Manager')
            label = tk.Label(root, text='Select the canonical item for this set of duplicates:')
            label.pack()

            duplicate = duplicates[i]
            items = [self.get_item_details(item.id) for item in duplicate]

            listbox = tk.Listbox(root, height=len(duplicate), selectmode='single')
            listbox.pack(fill='both', expand=True)
            for j, item_details in enumerate(items):
                listbox.insert(j, item_details.serialized)

            def on_select(event):
                selection = listbox.curselection()
                if selection:
                    index = selection[0]
                    canonical_item = duplicate[index]
                    for j, item in enumerate(duplicate):
                        if j != index:
                            logging.info(f"Editing item {item}")
                            logging.warning(['op', 'edit', 'item', item, 'set', 'details', self.get_item_details(canonical_item.id)])
                            logging.warning(['op', 'delete', 'item', item])

            listbox.bind('<<ListboxSelect>>', on_select)

            button = tk.Button(root, text='Apply Changes', command=root.destroy)
            button.pack()
            root.mainloop()

        root = tk.Tk()
        root.title('1Password Duplicate Manager')
        label = tk.Label(root, text='Select a set of duplicates to manage:')
        label.pack()
        for i, duplicate in enumerate(duplicates):
            button = tk.Button(root, text=duplicate[0].get_shared_domains(duplicate[1]), command=lambda i=i: display_duplicate_set(i, root))
            button.pack()
        root.mainloop()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s', stream=sys.stderr)

    if len(sys.argv) != 2:
        print("Usage: python op-dedupe.py VAULT_NAME")
        return

    vault = sys.argv[1]
    tool = OpTool(vault)
    tool.get_items()
    tool.show_duplicate_manager()


if __name__ == "__main__":
    main()