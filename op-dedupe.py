#!/usr/bin/env python3

import subprocess
import tkinter as tk


class OnePasswordTool:
    def __init__(self):
        self.items = self.get_items()

    def get_items(self):
        result = subprocess.run(['op', 'list', 'items'], capture_output=True)
        items = result.stdout.decode('utf-8').strip().split('\n')
        return items

    def get_item_details(self, uuid):
        result = subprocess.run(['op', 'get', 'item', uuid], capture_output=True)
        details = result.stdout.decode('utf-8')
        return details

    def find_duplicates(self):
        duplicates = []
        for i, item in enumerate(self.items):
            details = self.get_item_details(item)
            if details in duplicates:
                continue
            matching_items = [i for i in self.items[i+1:] if self.get_item_details(i) == details]
            if matching_items:
                duplicates.append(details)
                duplicates.append([item] + matching_items)
        return duplicates

    def show_duplicate_manager(self):
        duplicates = self.find_duplicates()
        if not duplicates:
            tk.messagebox.showinfo('No Duplicates Found', 'No duplicate items were found.')
            return
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
                    print(['op', 'archive', 'item', duplicate[j]])
                    #subprocess.run(['op', 'archive', 'item', duplicate[j]])
                if merge_var.get():
                    print(['op', 'edit', 'item', duplicate[0], 'set', 'details', self.get_item_details(duplicate[j])])
                    print(['op', 'delete', 'item', duplicate[j]])
                    #subprocess.run(['op', 'edit', 'item', duplicate[0], 'set', 'details', self.get_item_details(duplicate[j])])
                    #subprocess.run(['op', 'delete', 'item', duplicate[j]])


if __name__ == "__main__":
    tool = OnePasswordTool()
    tool.show_duplicate_manager()