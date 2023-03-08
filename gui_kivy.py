"""Implementation of a Kivy-based GUI for the 1Password Deduplication Manager."""


import logging
import webbrowser

# pylint: disable=import-error
from kivy.app import App
from kivy.clock import Clock
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen
# pylint: enable=import-error

import op_api


NODISPLAY_FIELDS = frozenset(["updated_at"])
LIST_SCREEN_ID = "duplicate_set_list"
SET_DETAILS_SCREEN_ID = "duplicate_set_details"
PROGRESS_SCREEN_ID = "doing_stuff"


class DedupeManager(ScreenManager):  # pylint: disable=too-few-public-methods
    """Deduplication Screen Manager."""


def navigate_to_screen(screen_id, direction='right', refresh=False):
    """Refreshes data within a screen and navigates there."""
    screenmanager = App.get_running_app().manager
    screenmanager.transition.direction = direction
    screenmanager.transition.duration = 0.2

    desired_screen = screenmanager.get_screen(screen_id)
    if refresh:
        screenmanager.current = PROGRESS_SCREEN_ID
        def refresh_and_navigate(unused_dt):
            desired_screen.refresh()
            screenmanager.current = screen_id
        Clock.schedule_once(refresh_and_navigate, 0.25)
        return
    screenmanager.current = screen_id


class EmptySetList(Screen):  # pylint: disable=too-few-public-methods
    """Page to display when there are no duplicates to show."""


class ProgressScreen(Screen):  # pylint: disable=too-few-public-methods
    """Transitional screen to give the impression of progress."""


class ViewSetDetailsButton(Button):
    """Button that, when clicked, navigates to a duplicate set details page."""
    selected_set = ObjectProperty(None)

    def on_release(self):
        screenmanager = App.get_running_app().manager
        details_screen = screenmanager.get_screen(SET_DETAILS_SCREEN_ID)
        details_screen.selected_set = self.selected_set
        screenmanager.transition.direction = 'left'
        screenmanager.transition.duration = 0.2
        screenmanager.current = SET_DETAILS_SCREEN_ID

    def get_display_text(self):
        return "{name} (Score: {score})".format(
            name=self.selected_set.get_display_name(),
            score=self.selected_set.difference_score())


class DuplicateSetList(Screen):
    """Page showing the list of all duplicate sets."""

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
            button = ViewSetDetailsButton()
            button.selected_set = this_set
            button.text = button.get_display_text()  # pylint: disable=attribute-defined-outside-init
            self.ids.set_list_box.add_widget(button)
        self.initialized = True

    def refresh(self):
        app = App.get_running_app()
        app.op_api.refresh_item_ids()
        self.initialized = False
        self.populate_list()


class DuplicateSetDetails(Screen):
    """Page showing the details of a particular duplicate set."""

    selected_set = ObjectProperty(None)
    populated_details = StringProperty()

    def clear_set_details(self):
        self.ids.set_details_box.clear_widgets(children=self.ids.set_details_box.children)
        self.populated_details = ''

    def build_column_header(self, item):
        column_header = DuplicateSetDetailsColumnHeader()
        column_header.selected_set = self.selected_set
        column_header.selected_item = item
        column_header.item_id = item.item_id
        return column_header

    def populate_set_details(self):
        items = self.selected_set.items
        column_count = len(items) + 1
        logging.info("Looking for %s columns", column_count)
        logging.info("Item ids: %s", [item.item_id for item in items])

        # Add a header row with buttons/checkboxes
        header_row = HeaderRow(cols=column_count)
        header_row.add_widget(SetDetailsOriginCell(text="Item id"))
        for i, item in enumerate(items):
            header_row.add_widget(self.build_column_header(item))
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
                    selected_set=self.selected_set, selected_item=self.selected_set.items[i],
                    for_display_only=bool(field_name in op_api.UNIMPLEMENTED_FIELDS))
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
            updated_items.append(
                app.op_api.get_item_details(item.item_id, force_refresh=True))
        self.selected_set = op_api.DuplicateSet(updated_items, op_api=app.op_api)
        self.clear_set_details()
        self.populate_set_details()


class DuplicateSetDetailsColumnHeader(BoxLayout):  # pylint: disable=too-few-public-methods
    """Column header on a duplicate set details page (one item per column)."""
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    item_id = StringProperty('')


class IconButton(Button):  # pylint: disable=too-few-public-methods
    """A button containing both an icon and a label."""


class ArchiveButton(IconButton):  # pylint: disable=too-few-public-methods
    """A button that, when pressed, archives a 1Password item."""
    selected_item = ObjectProperty(None)

    def on_release(self):
        navigate_to_screen(PROGRESS_SCREEN_ID, direction='right')
        def archive_and_navigate(unused_dt):
            App.get_running_app().op_api.archive_item(self.selected_item.item_id)
            navigate_to_screen(LIST_SCREEN_ID, direction='right', refresh=True)
        Clock.schedule_once(archive_and_navigate, 0.25)


class IgnoreSetButton(IconButton):  # pylint: disable=too-few-public-methods
    """A button that marks the items in a duplicate set as ignorable by this program."""
    selected_set = ObjectProperty(None)

    def on_release(self):
        navigate_to_screen(PROGRESS_SCREEN_ID, direction='right')
        def ignore_and_navigate(unused_dt):
            App.get_running_app().op_api.mark_as_multiprofile(self.selected_set.items)
            navigate_to_screen(LIST_SCREEN_ID, direction='right', refresh=True)
        Clock.schedule_once(ignore_and_navigate, 0.25)


class RefreshButton(IconButton):  # pylint: disable=too-few-public-methods
    """An abstract button that can refresh something."""


class RefreshListButton(RefreshButton):  # pylint: disable=too-few-public-methods
    """A button that refreshes the list view."""

    def on_release(self):
        # pylint: disable=no-self-use
        navigate_to_screen(LIST_SCREEN_ID, direction='up', refresh=True)


class RefreshSetButton(RefreshButton):  # pylint: disable=too-few-public-methods
    """A button that refreshes the duplicate set details page."""
    selected_set = ObjectProperty(None)

    def on_release(self):
        # pylint: disable=no-self-use
        navigate_to_screen(SET_DETAILS_SCREEN_ID, direction='up', refresh=True)


class EmptyCacheButton(IconButton):
    """A button to clear the on-disk cache."""

    def on_release(self):
        # pylint: disable=no-self-use
        App.get_running_app().op_api.clear_entire_cache()


class OpenLinkButton(IconButton):
    """A button to open a link in a web browser."""
    selected_item = ObjectProperty(None)

    def on_release(self):
        # pylint: disable=no-self-use
        webbrowser.open_new_tab(self.selected_item.fields['urls'][0])

class BackToListButton(IconButton):  # pylint: disable=too-few-public-methods
    """A button for navigating back to the list view."""

    def on_release(self):
        # pylint: disable=no-self-use
        navigate_to_screen(LIST_SCREEN_ID, direction='right', refresh=False)


class CopyButton(IconButton):
    """A button that copies the value of a field from one 1Password item to another."""
    # pylint: disable=too-few-public-methods
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    field_name = StringProperty('')

    def on_release(self):
        logging.info("Copying field %s from Item %s to set %s", self.field_name,
            self.selected_item.item_id, self.selected_set.get_display_name())
        navigate_to_screen(PROGRESS_SCREEN_ID, direction='up')
        def copy_and_navigate(unused_dt):
            app = App.get_running_app()
            for target_item in self.selected_set.items:
                if target_item.item_id == self.selected_item.item_id:
                    continue
                app.op_api.copy_field_values(self.selected_item, target_item, [self.field_name])
            navigate_to_screen(SET_DETAILS_SCREEN_ID, direction='up', refresh=True)
        Clock.schedule_once(copy_and_navigate, 0.25)


class HeaderRow(GridLayout):  # pylint: disable=too-few-public-methods
    """A generic header row container for layout."""


class DataRow(GridLayout):  # pylint: disable=too-few-public-methods
    """A generic data row container for layout."""


class RowHeaderCell(Label):  # pylint: disable=too-few-public-methods
    """A generic header cell container for layout."""


class SetDetailsOriginCell(RowHeaderCell):  # pylint: disable=too-few-public-methods
    """The upper-left cell on a duplicate set details page."""
    selected_set = ObjectProperty(None)


class FieldDataCell(BoxLayout):  # pylint: disable=too-few-public-methods
    """A data cell on a duplicate set details page."""
    selected_set = ObjectProperty(None)
    selected_item = ObjectProperty(None)
    field_name = StringProperty('')
    field_data = StringProperty('')
    for_display_only = BooleanProperty(False)


class KivyGUI(App):
    """Controller for the Kivy Duplicate Manager GUI."""

    def __init__(self, vault):
        super().__init__()
        self.op_api = op_api.OpApi(vault=vault)
        self.infocus_duplicate_set = None
        self.copy_vars = []
        self.details_window = None
        self.manager = DedupeManager()
        self.title = "1Password Duplicate Manager"


    def get_duplicates(self):
        duplicates = self.op_api.find_duplicates()
        if not duplicates:
            return []
        return sorted(duplicates, key=lambda x: x.difference_score())


    def build(self):
        Builder.load_file('op_dedupe.kv')
        duplicates = self.get_duplicates()
        if not duplicates:
            self.manager.add_widget(EmptySetList())
            return self.manager

        self.manager.add_widget(DuplicateSetList(name=LIST_SCREEN_ID))
        self.manager.add_widget(DuplicateSetDetails(name=SET_DETAILS_SCREEN_ID))
        self.manager.add_widget(ProgressScreen(name=PROGRESS_SCREEN_ID))
        return self.manager
