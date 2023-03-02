#!/usr/bin/env python3

import logging
import sys
import tkinter as tk
from tkinter import messagebox

import op_api

MULTIPROFILE_TAG = "multiprofile"


class OpToolUI:
    """Controller for the Tkinter Duplicate Manager GUI."""

    def __init__(self, vault):
        self.op_api = op_api.OpApi(vault=vault)
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
        self.details_window.title(
            f"Copying fields from {duplicate_set.items[source_index].item_id}")

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
        logging.info("Target items: %s", [item.item_id for item in target_items])
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
            updated_items.append(self.op_api.get_item_details(item.item_id, force_refresh=True))
        frame.destroy()
        self.display_duplicate_set(op_api.DuplicateSet(updated_items))

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
            tk.Label(header_cell, text=item.item_id).pack(side="left", fill="both", expand=True)
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
