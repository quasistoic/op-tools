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
from kivy.properties import ListProperty, ObjectProperty, StringProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen

import op_api


NODISPLAY_FIELDS = frozenset(["updated_at"])
LIST_SCREEN_ID = "duplicate_set_list"
SET_DETAILS_SCREEN_ID = "duplicate_set_details"
ITEM_DETAILS_SCREEN_ID = "individual_item_details"



class DedupeManager(ScreenManager):
    pass


class EmptySetList(Screen):
    pass


class ViewSetDetailsButton(Button):
    selected_set = ObjectProperty(None)

    def on_release(self):
        screenmanager = App.get_running_app().sm
        details_screen = screenmanager.get_screen(SET_DETAILS_SCREEN_ID)
        details_screen.selected_set = self.selected_set
        screenmanager.transition.direction = 'left'
        screenmanager.current = SET_DETAILS_SCREEN_ID

    def get_display_text(self):
        return f"{self.selected_set.get_display_name()} (Score: {self.selected_set.difference_score()})"


class DuplicateSetList(Screen):
    sets = ObjectProperty(None)
    initialized = BooleanProperty(defaultvalue=False)

    def on_pre_enter(self):
        if self.initialized:
            return

        for this_set in self.sets:
            b = ViewSetDetailsButton()
            b.selected_set = this_set
            b.text = b.get_display_text()
            self.ids.set_list_box.add_widget(b)
        self.initialized = True


class DuplicateSetDetails(Screen):
    # TODO: Make the buttons work.

    selected_set = ObjectProperty(None)
    populated_details = StringProperty()

    def clear_set_details(self):
        self.ids.set_details_box.clear_widgets(children=self.ids.set_details_box.children)
        self.populated_details = ''

    def populate_set_details(self):
        items = self.selected_set.items
        column_count = len(items) + 1
        logging.info("Looking for %s columns", column_count)
        logging.info("Item ids: %s", [item.item_id for item in items])

        # Add a header row with buttons/checkboxes
        header_row = HeaderRow(cols=column_count)
        header_row.add_widget(RowHeaderCell(text=""))
        for i, item in enumerate(items):
            column_header = DuplicateSetDetailsColumnHeader()
            column_header.selected_set = self.selected_set
            column_header.selected_item = item
            column_header.item_id = item.item_id
            header_row.add_widget(column_header)
        self.ids.set_details_box.add_widget(header_row)

        # Add the data rows with field values
        field_names = self.selected_set.field_names
        field_values = self.selected_set.field_values
        for j, field_name in enumerate(field_names):
            if field_name in NODISPLAY_FIELDS:
                continue
            row_values_vary = any(item.fields.get(field_name) != field_values[0][j]
                                      for item in items)
            if not row_values_vary:
                continue
            row = GridLayout(cols=column_count)
            row.add_widget(RowHeaderCell(text=field_name))
            row_values = [str(field_values[i][j]) for i in range(len(self.selected_set.items))]
            for value in row_values:
                row.add_widget(DataCell(text=value))
            self.ids.set_details_box.add_widget(row)
        self.populated_details = self.selected_set.get_display_name()

    def on_pre_enter(self):
        App.get_running_app().title = f"Viewing Duplicate Set {self.selected_set.get_display_name()}"
        if self.populated_details == self.selected_set.get_display_name():
            return
        self.clear_set_details()
        self.populate_set_details()


class IndividualItemDetails(Screen):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    populated_details = StringProperty()


    def clear_item_details(self):
        self.ids.item_details_box.clear_widgets(children=self.ids.item_details_box.children)
        self.populated_details = ''

    def populate_item_details(self):
        box = self.ids.item_details_box
        for i, field_name in enumerate(self.selected_set.field_names):
            box.add_widget(Label(text=field_name))
            values = self.selected_item.fields.get(field_name, '')
            if isinstance(values, list):
                values = ", ".join(values)
            box.add_widget(Label(text=values))
            var = CheckBox()
            box.add_widget(var)
        self.populated_details = self.selected_item.item_id

    def on_pre_enter(self):
        App.get_running_app().title = f"Item details for {self.selected_item.item_id}"
        if self.populated_details == self.selected_item.item_id:
            return
        self.clear_item_details()
        self.populate_item_details()


class DuplicateSetDetailsColumnHeader(BoxLayout):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    item_id = StringProperty('')


class LabeledCheckbox(BoxLayout):
    label_text = StringProperty('')


class ArchiveCheckbox(LabeledCheckbox):
    selected_item = ObjectProperty(None)


class MultiprofileCheckbox(LabeledCheckbox):
    selected_item = ObjectProperty(None)


class HeaderRow(GridLayout):
    pass


class RowHeaderCell(Label):
    pass


class DataCell(Label):
    pass


class ApplyButton(Button):
    pass


class ConfirmCopyButton(Button):
    pass


class BackToSetButton(Button):

    def on_release(self):
        screenmanager = App.get_running_app().sm
        screenmanager.transition.direction = 'right'
        screenmanager.current = SET_DETAILS_SCREEN_ID


class BackToListButton(Button):

    def on_release(self):
        screenmanager = App.get_running_app().sm
        screenmanager.transition.direction = 'right'
        screenmanager.current = LIST_SCREEN_ID


class CopyButton(Button):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)

    def on_release(self):
        screenmanager = App.get_running_app().sm
        details_screen = screenmanager.get_screen(ITEM_DETAILS_SCREEN_ID)
        details_screen.selected_set = self.selected_set
        details_screen.selected_item = self.selected_item
        screenmanager.transition.direction = 'left'
        screenmanager.current = ITEM_DETAILS_SCREEN_ID


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
        self.title = "1Password Duplicate Manager"
        Builder.load_file('op_dedupe.kv')
        duplicates = self.op_api.find_duplicates()
        if not duplicates:
            self.sm.add_widget(EmptySetList())
            return self.sm

        set_list = DuplicateSetList(name=LIST_SCREEN_ID)
        set_list.sets = sorted(duplicates, key=lambda x: x.difference_score())
        self.sm.add_widget(set_list)
        set_details = DuplicateSetDetails(name=SET_DETAILS_SCREEN_ID)
        self.sm.add_widget(set_details)
        item_details = IndividualItemDetails(name=ITEM_DETAILS_SCREEN_ID)
        self.sm.add_widget(item_details)
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

        # STILL NEEDS IMPLEMENTATION AFTER HERE

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



