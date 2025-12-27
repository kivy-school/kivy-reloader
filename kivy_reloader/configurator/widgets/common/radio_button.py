"""Radio button and radio group components"""

from kivy.properties import (
    BooleanProperty,
    ListProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class RadioButton(BoxLayout):
    """Single radio button option"""

    label = StringProperty()
    value = StringProperty()
    selected = BooleanProperty(False)
    group = ObjectProperty(None)

    def select(self):
        """Select this radio button"""
        if self.group:
            self.group.select_value(self.value)


class RadioGroup(BoxLayout):
    """Radio button group container"""

    title = StringProperty()
    options = ListProperty([])  # List of {'label': 'USB', 'value': 'USB'}
    selected_value = StringProperty()

    def __init__(self, **kwargs):
        self.register_event_type('on_selected_value')
        super().__init__(**kwargs)
        self.radio_buttons = []
        # Bind to selected_value changes to update button states
        self.bind(selected_value=self._on_selected_value_changed)

    def on_selected_value(self, *args):
        """Event fired when selected value changes"""
        pass

    def _on_selected_value_changed(self, instance, value):
        """Update radio button states when selected_value changes externally"""
        # Update all radio buttons to match the new selected_value
        for btn in self.radio_buttons:
            btn.selected = btn.value == value

    def on_kv_post(self, base_widget):
        """Build radio buttons after KV is loaded"""
        self._build_options()

    def on_options(self, instance, value):
        """Rebuild when options change"""
        self._build_options()

    def _build_options(self):
        """Build radio button widgets"""
        container = self.options_container
        container.clear_widgets()
        self.radio_buttons = []

        for option in self.options:
            btn = RadioButton(
                label=option.get('label', ''),
                value=option.get('value', ''),
                selected=(option.get('value', '') == self.selected_value),
                group=self,
            )
            container.add_widget(btn)
            self.radio_buttons.append(btn)

    def select_value(self, value):
        """Select a value and update all radio buttons"""
        # Only update if value actually changed
        if self.selected_value != value:
            self.selected_value = value
            # Dispatch the event to notify listeners
            self.dispatch('on_selected_value', value)

        for btn in self.radio_buttons:
            btn.selected = btn.value == value
            self.selected_value = value
            # Dispatch the event to notify listeners
            self.dispatch('on_selected_value', value)

        for btn in self.radio_buttons:
            btn.selected = btn.value == value
