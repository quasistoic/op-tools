from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import op_api


class KivyGUI(App):
    """Controller for the Kivy Duplicate Manager GUI."""

    def __init__(self, vault):
        super().__init__()
        self.op_api = op_api.OpApi(vault=vault)
        self.infocus_duplicate_set = None
        self.copy_vars = []
        self.details_window = None

    def build(self):
        duplicates = self.op_api.find_duplicates()
        if not duplicates:
            self.root = BoxLayout(orientation='vertical')
            self.root.add_widget(Label(text='No duplicate items were found.'))
            return

        self.root = ScrollView()
        layout = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, padding=[10, 10, 10, 0])
        layout.bind(minimum_height=layout.setter('height'))

        for duplicate_set in sorted(duplicates, key=lambda x: x.difference_score()):
            button_text = f"{duplicate_set.difference_score()}: {duplicate_set.get_display_name()}"
            button = Button(text=button_text, size_hint_y=None, height=40, background_normal='',
                            background_color=[0.5, 0.5, 0.5, 1])
            button.bind(on_press=lambda instance, dup_set=duplicate_set: self.display_duplicate_set(dup_set))
            layout.add_widget(button)

        self.root.add_widget(layout)
        return self.root

    def show_duplicate_details(self, duplicate_set, source_index):
        pass

    def copy_selected_fields(self, source_index=0):
        pass

    def refresh_duplicate_set(self, duplicate_set, frame):
        pass

    def display_duplicate_set(self, duplicate_set):
        pass
