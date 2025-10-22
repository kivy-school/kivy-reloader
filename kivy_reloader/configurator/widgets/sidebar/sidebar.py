from kivy.properties import (
    BooleanProperty,
    ListProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class SidebarItem(BoxLayout):
    """Individual sidebar menu item"""

    icon = StringProperty()
    text = StringProperty()
    is_selected = BooleanProperty(False)
    callback = ObjectProperty(None, allownone=True)
    section = StringProperty()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.callback:
                self.callback(self)
            return True
        return super().on_touch_down(touch)


class SideBar(BoxLayout):
    """Main sidebar navigation component"""

    __events__ = ('on_section_select',)

    menu_items = ListProperty([
        {'icon': '🔥', 'text': 'Core'},
        {'icon': '🔧', 'text': 'Services'},
        {'icon': '📱', 'text': 'Device'},
        {'icon': '🪟', 'text': 'Window'},
        {'icon': '🖌️', 'text': 'Display'},
        {'icon': '🎵', 'text': 'Audio'},
        {'icon': '⚙️', 'text': 'Performance'},
        {'icon': '🚀', 'text': 'Advanced'},
        {'icon': '📦', 'text': 'Deployment'},
        {'icon': '🔔', 'text': 'Notifications'},
    ])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_item = None
        self.all_items = []  # Store all menu item widgets
        self.selected_section = 'Core'

    def on_kv_post(self, base_widget):
        """Called after KV rules are applied"""
        # Add menu items to the container
        menu_container = self.menu_container

        for item_data in self.menu_items:
            item = SidebarItem(
                icon=item_data['icon'],
                text=item_data['text'],
                section=item_data.get('section', item_data['text']),
            )
            item.callback = self._on_item_selected
            menu_container.add_widget(item)
            self.all_items.append(item)

        # Select default section
        default = self.selected_section
        initial_item = next(
            (itm for itm in self.all_items if itm.section == default), None
        )
        self._select_item(initial_item, trigger=True)

    def filter_items(self, search_text):
        """Filter menu items based on search text"""
        search_text = search_text.lower().strip()
        menu_container = self.menu_container
        menu_container.clear_widgets()

        if not search_text:
            # Restore all in original order
            for item in self.all_items:
                menu_container.add_widget(item)
        else:
            # Add only matching ones, but still in original order
            for item in self.all_items:
                if search_text in item.text.lower():
                    menu_container.add_widget(item)

    def _on_item_selected(self, item):
        self._select_item(item)

    def _select_item(self, item, trigger: bool = True):
        if self.selected_item is item:
            if trigger:
                self.dispatch('on_section_select', item.section)
            return

        if self.selected_item:
            self.selected_item.is_selected = False

        self.selected_item = item
        self.selected_section = item.section
        item.is_selected = True

        if trigger:
            self.dispatch('on_section_select', item.section)

    def on_section_select(self, section):
        """Event dispatched when a menu section is selected."""
        # Default handler; can be bound from outside
        return None
