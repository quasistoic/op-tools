#!/usr/bin/env python3

import json
import logging
import os
import pickle
import sys
import tkinter as tk

from functools import cached_property
from tkinter import messagebox
from urllib.parse import urlparse

MULTIPROFILE_TAG = "multiprofile"


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


class ItemList:

    def __init__(self, item_details_list):
        self.items = item_details_list

    def __iter__(self):
        for i in self.items:
            yield i

    @classmethod
    def from_json(cls, serialized_json):
        raw_items = json.loads(serialized_json)
        item_details_list = []
        for raw_item in raw_items:
            item_details_list.append(ItemDetails.from_list(raw_item))
        return cls(item_details_list)


class ItemDetails:
    SERIALIZED_SOURCE = "serialized"
    JSON_SOURCE = "json"
    JSON_LIST_SOURCE = "list_skeleton"

    def __init__(self, item_id, fields=(), source=None,
            serialized=None, domains=frozenset([])):
        self.id = item_id
        self.serialized = serialized
        self.source = source
        self.fields = fields
        self.domains = domains

    def __str__(self):
        return str(sorted(self.fields.items()))

    def is_duplicate(self, other):
        return bool(self.get_shared_domains(other))

    def get_shared_domains(self, other):
        return self.domains & other.domains

    def has_full_details(self):
        return ItemDetails.JSON_SOURCE == self.source

    @classmethod
    def from_serialized(cls, serialized):
        # There's an annoying bug here: URLs don't get a proper field name,
        # so attempting to copy URLs from one item to another just plain doesn't
        # work. Will kill this method in favor of JSON loading only.
        item_id = None
        domains = set([])
        fields = {}
        for line in serialized.split("\n"):
            line_parts = line.strip().split(": ")
            if len(line_parts) >= 2:
                key = line_parts[0].strip()
                values = []
                for i in line_parts[1:]:
                    stripped = i.strip()
                    if get_domain_from_url(stripped):
                        stripped = stripped.strip(" (primary)")
                        domains.add(get_domain_from_url(stripped))
                    values.append(stripped)
                fields[key] = values
        item_id = fields['ID'][0]
        if domains:
            logging.debug("Domains for %s : %s", item_id, domains)
        return cls(item_id, fields=fields, source=cls.SERIALIZED_SOURCE,
            serialized=serialized, domains=domains)

    @classmethod
    def from_json(cls, serialized_json):
        details = json.loads(serialized_json)
        item_id = details["id"]
        fields = {
            "title": details.get("title", "Untitled"),
            "tags": details.get("tags", []),
            "urls": [i["href"] for i in details.get("urls", [])],
            "vault": details["vault"]["name"],
            "category": details["category"],
            "updated_at": details["updated_at"]
        }
        for field in details["fields"]:
            if field.get("value"):
                if field.get("label"):
                    fields[field["label"]] = field["value"]
                else:
                    fields[field["id"]] = field["value"]
        domains = {get_domain_from_url(url) for url in fields["urls"]}
        return cls(item_id, fields=fields, source=cls.JSON_SOURCE,
            serialized=serialized_json, domains=domains)

    @classmethod
    def from_list(cls, details):
        item_id = details["id"]
        fields = {
            "title": details.get("title", "Untitled"),
            "tags": details.get("tags", []),
            "urls": [i["href"] for i in details.get("urls", [])],
            "vault": details["vault"]["name"],
            "category": details["category"],
            "updated_at": details["updated_at"]
        }
        domains = {get_domain_from_url(url) for url in fields["urls"]}
        return cls(item_id, fields=fields, source=cls.JSON_LIST_SOURCE,
            domains=domains)


class OpApi:

    def __init__(self, cache_dir="./.op-cache", vault=None):
        self.vault = vault
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        self.items = self.get_item_list()
        self.item_ids = [item.id for item in self.items]

    def _get_command_cache_file_name(self, command):
        return f"{self.cache_dir}/.{self.vault}.{command}.cache"

    def clear_details_cache(self, item_id):
        self.get_item_details(item_id, force_refresh=True)

    def run_command(self, command, skip_cache=False, cacheable=True):
        cache_file = self._get_command_cache_file_name(command)
        if cacheable and not skip_cache:
            if os.path.exists(cache_file):
                logging.debug("Pulling from cache: %s", cache_file)
                with open(cache_file, "rb") as cache:
                    return pickle.load(cache)

        op_command = f"op {command}"
        if not skip_cache:
            op_command += " --cache"
        if self.vault:
            op_command += f" --vault {self.vault}"
        logging.info("Calling API: %s", op_command)
        output = os.popen(op_command).read()
        if cacheable:
            with open(cache_file, "wb") as cache:
                pickle.dump(output, cache)
        return output

    def refresh_item_ids(self):
        self.items = self.get_item_list(force_refresh=True)
        self.item_ids = [item.id for item in self.items]

    def get_item_list(self, force_refresh=False):
        output = self.run_command("item list --format=json",
            skip_cache=force_refresh)
        item_list = ItemList.from_json(output)
        return item_list

    def get_item_details(self, item_id, force_refresh=False):
        output = self.run_command(f"item get {item_id} --format=json",
            skip_cache=force_refresh)
        try:
            item = ItemDetails.from_json(output)
        except json.decoder.JSONDecodeError:
            logging.error("Error while attempting to read: %s", item_id)
            sys.exit(1)
        return item

    def archive_item(self, item_id):
        logging.warning("Archiving item %s", item_id)
        self.run_command(f"item delete {item_id} --archive", cacheable=False)
        self.refresh_item_ids()

    def add_tag(self, item_details, tag):
        item_id = item_details.id
        all_tags = item_details.fields["tags"] + [tag]
        command = f'item edit {item_id} --tags "{all_tags[0]}"'
        for other_tag in all_tags[1:]:
            command += f',"{other_tag}"'
        self.run_command(command, cacheable=False)
        self.get_item_details(item_id, force_refresh=True)

    def update_item(self, item_details, fields):
        item_id = item_details.id
        for field_name, values in fields.items():
            if field_name == "urls":
                command = f'item edit {item_id} --url "{values[0]}"'
            elif field_name in ["tags"]:
                logging.warning("Copying %s is currently unimplemented.", field_name)
                continue
            elif values == "":
                command = f'item edit {item_id} {field_name}[delete]'
            else:
                command = f'item edit {item_id} {field_name}="{values}"'
            self.run_command(command, cacheable=False)
        self.get_item_details(item_id, force_refresh=True)
        self.refresh_item_ids()

    def copy_field_values(self, from_item, to_item, fields):
        field_values = {}
        for field_name in fields:
            if field_name in from_item.fields:
                field_values[field_name] = from_item.fields[field_name]
            else:
                # I guess we're erasing this field. TODO: Prompt to confirm.
                field_values[field_name] = ''
        if field_values:
            self.update_item(to_item, field_values)

    def archive_items(self, items_to_archive):
        for item in items_to_archive:
            self.archive_item(item.id)

    def mark_as_multiprofile(self, items):
        for item in items:
            self.add_tag(item, MULTIPROFILE_TAG)

    def find_duplicates(self):
        duplicates = []
        duplicate_ids = set()
        for i, item_id in enumerate(self.item_ids):
            if item_id in duplicate_ids:
                logging.debug("Skipping %s because we know it's a duplicate.", item_id)
                continue
            logging.debug("Looking for duplicates of %s", item_id)
            details = self.get_item_details(item_id)
            if details:
                matching_items = []
                for j in self.item_ids[i+1:]:
                    if j in duplicate_ids:
                        logging.debug(
                            "Skipping %s (inner loop) because we know it's a duplicate.", j)
                        continue
                    j_details = self.get_item_details(j)
                    if j_details.id == details.id:
                        continue
                    if not j_details.is_duplicate(details):
                        continue
                    matching_items.append(j_details)
                if matching_items:
                    duplicate_set = DuplicateSet([details] + matching_items)
                    if duplicate_set.is_intentionally_multiprofile():
                        continue
                    duplicates.append(duplicate_set)
                    duplicate_ids.update(
                        [item.id for item in duplicate_set.items])

        logging.info("Found %s sets of duplicates.", len(duplicates))
        return duplicates


class DuplicateSet:

    def __init__(self, items, op_api=None):
        self.op_api = op_api
        self.items = items

    def get_display_name(self):
        return self.items[0].get_shared_domains(self.items[1])

    def has_full_details(self):
        return all(item.has_full_details() for item in self.items)

    def force_full_details(self):
        if self.has_full_details():
            return

        for i, item in enumerate(self.items[:]):
            if i.has_full_details():
                continue
            new_item = self.op_api.get_item_details(item.id)
            self.items[i] = new_item

    @cached_property
    def field_names(self):
        self.force_full_details()
        return sorted(set(field_name for item in self.items
                          for field_name in item.fields.keys()))

    @cached_property
    def field_values(self):
        self.force_full_details()
        return [
            [item.fields.get(field_name, '') for field_name in self.field_names]
            for item in self.items
        ]

    def is_intentionally_multiprofile(self):
        return all(
            MULTIPROFILE_TAG in item.fields["tags"] for item in self.items)

    def difference_score(self):
        score = 0
        for field_name in self.field_names:
            existing_values = set()
            for i in range(len(self.items)):
                for k in range(len(self.field_values[i])):
                    item_value = self.field_values[i][k]
                    if hasattr(item_value, '__iter__') and not isinstance(item_value, str):
                        for element in item_value:
                            existing_values.add(element)
                    else:
                        existing_values.add(item_value)

            row_has_diff_values = len(existing_values) > 1
            if row_has_diff_values:
                field_score = len(existing_values)
                if '' not in existing_values:
                    field_score += 1
                if field_name.lower() == "password":
                    field_score *= 10
                elif field_name.lower() == "username":
                    field_score *= 5
                elif field_name.lower in ["vault", "updated_at"]:
                    field_score /= 2
                score += field_score
        return score


class OpToolUI:

    def __init__(self, vault):
        self.op_api = OpApi(vault=vault)
        self.create_root()
        self.infocus_duplicate_set = None
        self.copy_vars = []
        self.details_window = None


    def create_root(self):
        self.root = tk.Tk()
        self.root.title('1Password Duplicate Manager')

    def show_duplicate_details(self, duplicate_set, source_index):
        self.infocus_duplicate_set = duplicate_set
        self.details_window = tk.Toplevel(self.root)
        self.details_window.title(f"Copying fields from {duplicate_set.items[source_index].id}")

        # Create a scrollable frame for the labels, checkboxes, and button
        scroll_frame = tk.Frame(self.details_window)
        scroll_frame.pack(side="top", fill="both", expand=True)
        scrollbar = tk.Scrollbar(scroll_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        canvas = tk.Canvas(scroll_frame)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        inner_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        # Create labels
        tk.Label(inner_frame, text="Field names").grid(row=0, column=0)
        tk.Label(inner_frame, text="Values").grid(row=0, column=1)

        # Create checkboxes for selecting fields to copy
        self.copy_vars = []
        for i, field_name in enumerate(duplicate_set.field_names):
            tk.Label(inner_frame, text=field_name).grid(row=i+1, column=0)
            values = duplicate_set.field_values[source_index][i]
            if isinstance(values, list):
                values = ", ".join(values)
            tk.Label(inner_frame, text=values).grid(row=i+1, column=1)
            var = tk.BooleanVar()
            tk.Checkbutton(inner_frame, variable=var).grid(row=i+1, column=2)
            self.copy_vars.append(var)

        # Create Copy Selected Fields button
        tk.Button(inner_frame, text="Copy Selected Fields",
            command=lambda x=source_index: self.copy_selected_fields(source_index=x)
        ).grid(row=len(duplicate_set.field_names)+2, column=1)

    def copy_selected_fields(self, source_index=0):
        """Copy the selected fields from one duplicate item to another."""
        source_item = self.infocus_duplicate_set.items[source_index]
        field_names_to_copy = []
        target_items = set()
        for i, var in enumerate(self.copy_vars):
            if var.get():
                field_name = self.infocus_duplicate_set.field_names[i]
                field_names_to_copy.append(field_name)
                for cur_index, target_item in enumerate(self.infocus_duplicate_set.items):
                    if cur_index != source_index:
                        target_items.add(target_item)
        target_items = list(target_items)
        logging.info("Field names to copy: %s", field_names_to_copy)
        logging.info("Target items: %s", [item.id for item in target_items])
        if field_names_to_copy and target_items:
            for target_item in target_items:
                self.op_api.copy_field_values(source_item, target_item, field_names_to_copy)
        self.details_window.destroy()
        self.root.destroy()
        self.create_root()
        self.run()

    def refresh_duplicate_set(self, duplicate_set, frame):
        updated_items = []
        for item in duplicate_set.items:
            updated_items.append(self.op_api.get_item_details(item.id, force_refresh=True))
        frame.destroy()
        self.display_duplicate_set(DuplicateSet(updated_items))

    def display_duplicate_set(self, duplicate_set):
        """Display the selected duplicate set for management."""
        items = duplicate_set.items
        field_names = duplicate_set.field_names
        field_values = duplicate_set.field_values
        archive_vars = [tk.BooleanVar(value=False) for item in items]
        multiprofile_vars = [tk.BooleanVar(value=False) for item in items]

        top = tk.Toplevel(self.root)
        top.title(f"1Password Duplicate Manager: {duplicate_set.get_display_name()}")

        # Create table frame and header
        table_frame = tk.Frame(top)
        table_frame.pack(side="top", fill="both", expand=True)

        # Create a canvas widget and place the table frame inside it
        scrollbar_y = tk.Scrollbar(table_frame, orient="vertical")
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x = tk.Scrollbar(table_frame, orient="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")
        canvas = tk.Canvas(table_frame)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_y.config(command=canvas.yview)
        scrollbar_x.config(command=canvas.xview)

        canvas.configure(xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)
        canvas.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        inner_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        # Create header row with Archive checkboxes
        header_frame = tk.Frame(inner_frame, relief=tk.RIDGE, borderwidth=1)
        header_frame.pack(side="top", fill="both", expand=True)
        refresh_button = tk.Button(header_frame, text="Force Refresh",
            command=lambda frame=top,dup_set=duplicate_set: self.refresh_duplicate_set(dup_set,
                                                                                       frame))
        refresh_button.pack(side="left")
        for i, item in enumerate(items):
            header_cell = tk.Frame(header_frame, relief=tk.RIDGE, borderwidth=1)
            header_cell.pack(side="left", fill="both", expand=True)
            options_cell = tk.Frame(header_cell, relief=tk.RIDGE, borderwidth=1)
            options_cell.pack(side="bottom")
            tk.Label(header_cell, text=item.id).pack(side="left", fill="both", expand=True)
            archive_cb = tk.Checkbutton(options_cell, text='Archive', variable=archive_vars[i])
            archive_cb.pack(side="left")
            multiprofile_cb = tk.Checkbutton(
                options_cell, text='Mark as multiprofile', variable=multiprofile_vars[i])
            multiprofile_cb.pack(side="left")
            copy_button = tk.Button(
                options_cell, text="Use as copy source",
                command=lambda x=i,dup_set=duplicate_set: self.show_duplicate_details(dup_set, x))
            copy_button.pack(side="left")

        # Create table rows
        for j, field_name in enumerate(field_names):
            if field_name in ["updated_at"]:
                continue
            row_has_diff_values = any(item.fields.get(field_name) != field_values[0][j]
                                      for item in items)
            if row_has_diff_values:
                row_frame = tk.Frame(inner_frame, relief=tk.RIDGE, borderwidth=1)
                row_frame.pack(side="top", fill="both", expand=True)
                tk.Label(row_frame, text=field_name).pack(side="left", fill="both", expand=True)
                for i in range(len(duplicate_set.items)):
                    row_cell = tk.Frame(row_frame, relief=tk.RIDGE, borderwidth=1)
                    row_cell.pack(side="left", fill="both", expand=True)
                    field_value = field_values[i][j]
                    label = tk.Label(row_cell, text=field_value)
                    label.pack(side="top", fill="both", expand=True)

        def apply():
            items_to_archive = [item for i, item in enumerate(items) if archive_vars[i].get()]
            items_to_mark_multi = [item for i, item in enumerate(items)
                                   if multiprofile_vars[i].get()]
            top.destroy()
            if items_to_mark_multi:
                self.op_api.mark_as_multiprofile(items_to_mark_multi)
            if items_to_archive:
                self.op_api.archive_items(items_to_archive)
            self.root.destroy()
            self.create_root()
            self.run()

        apply_button = tk.Button(top, text="Apply Changes", command=apply)
        apply_button.pack()

        top.mainloop()

    def run(self):
        duplicates = self.op_api.find_duplicates()
        if not duplicates:
            messagebox.showinfo('No Duplicates Found', 'No duplicate items were found.')
            return

        for duplicate_set in sorted(duplicates, key=lambda x: x.difference_score()):
            button_text = f"{duplicate_set.difference_score()}: {duplicate_set.get_display_name()}"
            button = tk.Button(
                self.root, text=button_text,
                command=lambda dup_set=duplicate_set: self.display_duplicate_set(dup_set))
            button.pack()

        self.root.mainloop()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        stream=sys.stderr)

    vault = None
    if len(sys.argv) >= 2:
        vault = sys.argv[1]
    tool = OpToolUI(vault)
    tool.run()


if __name__ == "__main__":
    main()
