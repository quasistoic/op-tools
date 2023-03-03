import logging
from functools import partial

from kivy.app import App
from kivy.core.window import Window
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.screenmanager import ScreenManager, Screen

import op_api


class DedupeManager(ScreenManager):
    pass


class EmptySetList(Screen):
    pass

class DuplicateSetList(Screen):

    sets = ObjectProperty(None)

    def release_callback(self, unused_event, this_set):
        details_screen = self.manager.get_screen("duplicate_set_details")
        details_screen.selected_set = this_set
        self.manager.switch_to(details_screen)

    def on_pre_enter(self):
        for this_set in self.sets:
            b = Button(text=f"{this_set.difference_score()}: {this_set.get_display_name()}")
            b.bind(on_release=partial(self.release_callback, this_set=this_set))
            self.ids.set_list_box.add_widget(b);


class DuplicateSetDetails(Screen):

    selected_set = ObjectProperty(None)

    def on_pre_enter(self):
        items = self.selected_set.items
        logging.info("Looking for %s columns", len(items)+1)
        logging.info("Item ids: %s", [item.item_id for item in items])
        header_row = GridLayout(cols=len(items)+1)
        header_row.add_widget(Label(text=""))
        for i, item in enumerate(items):
            column_header = DuplicateSetDetailsColumnHeader()
            column_header.item_id = item.item_id
            header_row.add_widget(column_header)
        self.ids.set_details_box.add_widget(header_row)


class IndividualItemDetails(Screen):
    pass

class DuplicateSetDetailsColumnHeader(BoxLayout):
    item_id = StringProperty('')


class LabeledCheckbox(BoxLayout):
    label_text = StringProperty('')


class BackButton(Button):

    def on_release(self):
        app = App.get_running_app()
        previous_screen = app.root.get_screen(app.previous_screen)
        app.root.switch_to(previous_screen)


class KivyGUI(App):
    """Controller for the Kivy Duplicate Manager GUI."""

    def __init__(self, vault):
        super().__init__()
        self.op_api = op_api.OpApi(vault=vault)
        self.infocus_duplicate_set = None
        self.copy_vars = []
        self.details_window = None
        self.sm = DedupeManager()


    def build(self):
        Builder.load_file('op_dedupe.kv')

        duplicates = self.op_api.find_duplicates()
        if not duplicates:
            self.sm.add_widget(EmptySetList())
            return self.sm

        set_list = DuplicateSetList(name="duplicate_set_list")
        set_list.sets = sorted(duplicates, key=lambda x: x.difference_score())
        self.sm.add_widget(set_list)
        set_details = DuplicateSetDetails(name="duplicate_set_details")
        self.sm.add_widget(set_details)
        return self.sm

    def show_item_details(self, duplicate_set, source_index):
        self.infocus_duplicate_set = duplicate_set

        # Create a scrollable frame for the labels, checkboxes, and button
        scroll_frame = ScrollView()
        inner_frame = GridLayout(cols=3)
        inner_frame.bind(minimum_height=inner_frame.setter('height'))
        for i, field_name in enumerate(duplicate_set.field_names):
            inner_frame.add_widget(Label(text=field_name))
            values = duplicate_set.field_values[source_index][i]
            if isinstance(values, list):
                values = ", ".join(values)
            inner_frame.add_widget(Label(text=values))
            var = CheckBox()
            inner_frame.add_widget(var)
            self.copy_vars.append(var)
        copy_button = Button(text="Copy Selected Fields")
        copy_button.bind(on_press=lambda x: self.copy_selected_fields(source_index=source_index))
        inner_frame.add_widget(copy_button)

        # Add the inner frame to the scroll view
        scroll_frame.add_widget(inner_frame)

        # Create a popup to show the details window
        content = BoxLayout(orientation='vertical')
        popup = Popup(title=f"Copying fields from {duplicate_set.items[source_index].item_id}",
                      content=content, size_hint=(None, None), size=(600, 400))
        content.add_widget(scroll_frame)
        popup.open()

    def copy_selected_fields(self, source_index=0):
        pass

    def refresh_duplicate_set(self, duplicate_set, frame):
        pass

    def show_set_details(self, duplicate_set):
        """Display the selected duplicate set for management."""
        items = duplicate_set.items
        field_names = duplicate_set.field_names
        field_values = duplicate_set.field_values
        archive_vars = [False for item in items]
        multiprofile_vars = [False for item in items]

        # Create the main layout
        layout = GridLayout(cols=1)

        # Create the header row with Archive checkboxes
        header_row = GridLayout(cols=len(items)+1)
        header_row.add_widget(Label(text=""))
        for i, item in enumerate(items):
            item_id = item.item_id
            header_row.add_widget(Label(text=item_id))
            archive_cb = CheckBox()
            archive_vars[i] = archive_cb.active
            header_row.add_widget(archive_cb)
            multiprofile_cb = CheckBox()
            multiprofile_vars[i] = multiprofile_cb.active
            header_row.add_widget(multiprofile_cb)
            copy_button = Button(text="Use as copy source")
            header_row.add_widget(copy_button)

        layout.add_widget(header_row)

        # Create the table rows
        for j, field_name in enumerate(field_names):
            if field_name in ["updated_at"]:
                continue
            row_has_diff_values = any(item.fields.get(field_name) != field_values[0][j]
                                      for item in items)
            if row_has_diff_values:
                row = GridLayout(cols=len(items)+1, spacing=10, size_hint_y=None, height=40)
                row.add_widget(Label(text=field_name))
                for i in range(len(duplicate_set.items)):
                    field_value = field_values[i][j]
                    row.add_widget(Label(text=str(field_value)))
                layout.add_widget(row)

        # Create the Apply Changes button
        apply_button = Button(text="Apply Changes")
        layout.add_widget(apply_button)

        # Create the ScrollView widget and add the main layout to it
        scroll_view = ScrollView(size_hint=(1, None), size=(Window.width, Window.height))
        scroll_view.add_widget(layout)

        # Create the top-level window
        top = App.get_running_app().root_window
        top.title = f"1Password Duplicate Manager: {duplicate_set.get_display_name()}"
        top.content = scroll_view

        def apply_changes(*args):
            items_to_archive = [item for i, item in enumerate(items) if archive_vars[i]]
            items_to_mark_multi = [item for i, item in enumerate(items)
                                   if multiprofile_vars[i]]
            top.dismiss()
            if items_to_mark_multi:
                self.op_api.mark_as_multiprofile(items_to_mark_multi)
            if items_to_archive:
                self.op_api.archive_items(items_to_archive)
            self.parent.parent.current = "home"

        apply_button.bind(on_press=apply_changes)



