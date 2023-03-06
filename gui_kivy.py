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
            for value in row_values:
                datacell = FieldDataCell(field_data=value)
                row.add_widget(datacell)
            self.ids.set_details_box.add_widget(row)
        self.populated_details = self.selected_set.get_display_name()

    def on_pre_enter(self):
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
            box.add_widget(RowHeaderCell(text=field_name))
            values = self.selected_item.fields.get(field_name, '')
            if isinstance(values, list):
                values = ", ".join(values)
            box.add_widget(DataCell(text=values))
            var = CheckBox()
            box.add_widget(var)
        self.populated_details = self.selected_item.item_id

    def on_pre_enter(self):
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


class IconButton(Button):
    pass


class ArchiveButton(IconButton):
    selected_item = ObjectProperty(None)


class IgnoreSetButton(IconButton):
    selected_set = ObjectProperty(None)


class HeaderRow(GridLayout):
    pass


class DataRow(GridLayout):
    pass


class RowHeaderCell(Label):
    pass


class SetDetailsOriginCell(RowHeaderCell):
    selected_set = ObjectProperty(None)


class DataCell(Label):
    pass


class FieldDataCell(BoxLayout):
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    field_data = StringProperty('')


class ApplyButton(Button):
    pass


class ConfirmCopyButton(Button):
    pass


class BackToSetButton(Button):

    def on_release(self):
        screenmanager = App.get_running_app().sm
        screenmanager.transition.direction = 'right'
        screenmanager.current = SET_DETAILS_SCREEN_ID


class BackToListButton(IconButton):

    def on_release(self):
        screenmanager = App.get_running_app().sm
        screenmanager.transition.direction = 'right'
        screenmanager.current = LIST_SCREEN_ID


class CopyButton(IconButton):
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

