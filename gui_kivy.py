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
        self.populate_list()

    def populate_list(self):
        if self.initialized:
            return
        self.ids.set_list_box.clear_widgets(children=self.ids.set_list_box.children)

        app = App.get_running_app()
        self.sets = app.get_duplicates()
        for this_set in self.sets:
            b = ViewSetDetailsButton()
            b.selected_set = this_set
            b.text = b.get_display_text()
            self.ids.set_list_box.add_widget(b)
        self.initialized = True

    def refresh(self):
        app = App.get_running_app()
        app.op_api.refresh_item_ids()
        self.initialized = False


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
        header_row.add_widget(SetDetailsOriginCell(text="Item id"))
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
            row = DataRow(cols=column_count)
            row.add_widget(RowHeaderCell(text=field_name))
            row_values = [str(field_values[i][j]) for i in range(len(self.selected_set.items))]
            for i, value in enumerate(row_values):
                datacell = FieldDataCell(field_name=field_name, field_data=value,
                    selected_set=self.selected_set, selected_item=self.selected_set.items[i])
                row.add_widget(datacell)
            self.ids.set_details_box.add_widget(row)
        self.populated_details = self.selected_set.get_display_name()

    def on_pre_enter(self):
        if self.populated_details == self.selected_set.get_display_name():
            return
        self.clear_set_details()
        self.populate_set_details()

    def refresh(self):
        app = App.get_running_app()
        updated_items = []
        for item in self.selected_set.items:
            updated_items.append(app.op_api.get_item_details(item.item_id, force_refresh=True))
        self.selected_set = op_api.DuplicateSet(updated_items, op_api=app.op_api)
        self.clear_set_details()
        self.populate_set_details()


class DuplicateSetDetailsColumnHeader(BoxLayout):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    item_id = StringProperty('')


class IconButton(Button):
    pass


class ArchiveButton(IconButton):
    selected_item = ObjectProperty(None)

    def on_release(self):
        app = App.get_running_app()
        app.op_api.archive_item(self.selected_item.item_id)

        screenmanager = app.sm
        list_screen = screenmanager.get_screen(LIST_SCREEN_ID)
        list_screen.refresh()
        screenmanager.current = LIST_SCREEN_ID


class IgnoreSetButton(IconButton):
    selected_set = ObjectProperty(None)

    def on_release(self):
        app = App.get_running_app()
        app.op_api.mark_as_multiprofile(self.selected_set.items)

        screenmanager = app.sm
        list_screen = screenmanager.get_screen(LIST_SCREEN_ID)
        list_screen.refresh()
        screenmanager.current = LIST_SCREEN_ID


class RefreshButton(IconButton):
    pass


class RefreshListButton(RefreshButton):

    def on_release(self):
        screenmanager = App.get_running_app().sm
        list_screen = screenmanager.get_screen(LIST_SCREEN_ID)
        list_screen.refresh()
        list_screen.populate_list()
        screenmanager.current = LIST_SCREEN_ID


class RefreshSetButton(RefreshButton):
    selected_set = ObjectProperty(None)

    def on_release(self):
        screenmanager = App.get_running_app().sm
        details_screen = screenmanager.get_screen(SET_DETAILS_SCREEN_ID)
        details_screen.refresh()
        screenmanager.current = SET_DETAILS_SCREEN_ID


class BackToListButton(IconButton):

    def on_release(self):
        screenmanager = App.get_running_app().sm
        screenmanager.transition.direction = 'right'
        screenmanager.current = LIST_SCREEN_ID


class CopyButton(IconButton):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    field_name = StringProperty('')

    def on_release(self):
        logging.info("Copying field %s from Item %s to set %s", self.field_name,
            self.selected_item.item_id, self.selected_set.get_display_name())
        app =App.get_running_app()
        for target_item in self.selected_set.items:
            if target_item.item_id == self.selected_item.item_id:
                continue
            app.op_api.copy_field_values(self.selected_item, target_item, [self.field_name])
        screenmanager = App.get_running_app().sm
        details_screen = screenmanager.get_screen(SET_DETAILS_SCREEN_ID)
        details_screen.refresh()
        screenmanager.current = SET_DETAILS_SCREEN_ID


class HeaderRow(GridLayout):
    pass


class DataRow(GridLayout):
    pass


class RowHeaderCell(Label):
    pass


class SetDetailsOriginCell(RowHeaderCell):
    selected_set = ObjectProperty(None)


class FieldDataCell(BoxLayout):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    field_name = StringProperty('')
    field_data = StringProperty('')


class KivyGUI(App):
    """Controller for the Kivy Duplicate Manager GUI."""

    def __init__(self, vault):
        super().__init__()
        self.op_api = op_api.OpApi(vault=vault)
        self.infocus_duplicate_set = None
        self.copy_vars = []
        self.details_window = None
        self.sm = DedupeManager()


    def get_duplicates(self):
        duplicates = self.op_api.find_duplicates()
        if not duplicates:
            return []
        return sorted(duplicates, key=lambda x: x.difference_score())


    def build(self):
        self.title = "1Password Duplicate Manager"
        Builder.load_file('op_dedupe.kv')
        duplicates = self.get_duplicates()
        if not duplicates:
            self.sm.add_widget(EmptySetList())
            return self.sm

        set_list = DuplicateSetList(name=LIST_SCREEN_ID)
        self.sm.add_widget(set_list)
        set_details = DuplicateSetDetails(name=SET_DETAILS_SCREEN_ID)
        self.sm.add_widget(set_details)
        return self.sm

