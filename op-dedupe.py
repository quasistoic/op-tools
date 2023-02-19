import subprocess
import tkinter as tk

# Function to get a list of all 1Password items
def get_items():
    result = subprocess.run(['op', 'list', 'items'], capture_output=True)
    items = result.stdout.decode('utf-8').strip().split('\n')
    return items

# Function to get the details of a 1Password item
def get_item_details(uuid):
    result = subprocess.run(['op', 'get', 'item', uuid], capture_output=True)
    details = result.stdout.decode('utf-8')
    return details

# Function to search for duplicate items
def find_duplicates():
    items = get_items()
    duplicates = []
    for item in items:
        details = get_item_details(item)
        if details in duplicates:
            continue
        matching_items = [i for i in items if i != item and get_item_details(i) == details]
        if matching_items:
            duplicates.append(details)
            duplicates.extend(matching_items)
    return duplicates

# Function to display the GUI for managing duplicates
def show_duplicate_manager():
    duplicates = find_duplicates()
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
        label = tk.Label(root, text=duplicate, justify='left')
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
                subprocess.run(['op', 'archive', 'item', duplicate[j]])
            if merge_var.get():
                subprocess.run(['op', 'edit', 'item', duplicate[0], 'set', 'details', get_item_details(duplicate[j])])
                subprocess.run(['op', 'delete', 'item', duplicate[j]])

# Example usage
show_duplicate_manager()