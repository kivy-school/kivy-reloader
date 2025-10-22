from kivy.animation import Animation
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.screenmanager import Screen

from kivy_reloader.configurator.widgets.cards import (  # noqa: F401
    CoreCard,
    ServicesCard,
)
from kivy_reloader.configurator.widgets.sidebar import SideBar  # noqa: F401
from kivy_reloader.configurator.widgets.toolbar import Toolbar  # noqa: F401
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class SectionScreen(Screen):
    card_cls = ObjectProperty(None, allownone=True)
    card = ObjectProperty(None, allownone=True)

    def on_card_cls(self, instance, value):
        card = value()
        self.section_box.add_widget(card)
        self.card = card


class CoreScreen(Screen):
    """Main screen for editing core configuration"""

    config_model = ObjectProperty(None)
    sidebar_visible = True
    active_section = StringProperty('Core')
    section_manager = ObjectProperty(None)
    core_card = ObjectProperty(None)
    services_card = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._section_cards = {}
        self._pending_config_model = None
        super().__init__(**kwargs)

    def on_config_model(self, instance, value):
        """Called when config_model is set - propagate to core_card"""
        if value:
            self._pending_config_model = value
            self._attach_model_to_cards()

    def on_kv_post(self, base_widget):
        """Setup toolbar callbacks after KV is loaded"""
        toolbar = self.toolbar
        toolbar.on_apply_reload = self.handle_apply_reload
        toolbar.on_save = self.handle_save
        toolbar.on_restore = self.handle_restore
        toolbar.on_export = self.handle_export
        toolbar.on_import = self.handle_import
        toolbar.on_help = self.handle_help
        toolbar.on_toggle_sidebar = self.toggle_sidebar

        sidebar = self.sidebar
        self._sidebar_default_width = sidebar.width
        sidebar.bind(on_section_select=self._on_sidebar_section_select)

        self._collect_section_cards()
        self._attach_model_to_cards()

        initial_section = sidebar.selected_section or 'Core'
        self.show_section(initial_section)

    def handle_apply_reload(self):
        """Handle Apply & Reload action"""
        if self.config_model:
            try:
                # Save first
                self.config_model.save()
                print('Configuration saved and will be applied on next reload')
                # TODO: Trigger actual hot reload mechanism
            except Exception as e:
                print(f'Error applying configuration: {e}')
        else:
            print('No config model available')

    def handle_save(self):
        """Handle Save action"""
        if self.config_model:
            try:
                self.config_model.save()
                print(f'Configuration saved to {self.config_model.config_path}')
            except Exception as e:
                print(f'Error saving configuration: {e}')
        else:
            print('No config model available')

    def handle_restore(self):
        """Handle Restore defaults action"""
        # TODO: Should open a confirmation dialog

        if self.config_model:
            self.config_model.reset_all(to_defaults=True)
            self._attach_model_to_cards()
            print('Configuration restored to defaults')
        else:
            print('No config model available')

    def handle_export(self):
        """Handle Export config action"""
        if self.config_model and self.config_model.config_path:
            # For now, export to a file in the same directory
            export_path = (
                self.config_model.config_path.parent / 'kivy-reloader-export.toml'
            )
            try:
                self.config_model.export_to_file(export_path)
                print(f'Configuration exported to {export_path}')
            except Exception as e:
                print(f'Error exporting configuration: {e}')
        else:
            print('No config model or path available')

    def handle_import(self):
        """Handle Import config action"""
        if self.config_model and self.config_model.config_path:
            import_path = (
                self.config_model.config_path.parent / 'kivy-reloader-import.toml'
            )
            try:
                if import_path.exists():
                    self.config_model.import_from_file(import_path, merge=True)
                    self._attach_model_to_cards()
                    print(f'Configuration imported from {import_path}')
                else:
                    print(f'Import file not found: {import_path}')
            except Exception as e:
                print(f'Error importing configuration: {e}')
        else:
            print('No config model or path available')

    def handle_help(self):
        """Handle Help toggle action"""
        print('Help clicked')
        # TODO: Implement help panel toggle

    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        if 'sidebar' not in self.ids:
            return

        sidebar = self.sidebar
        self.sidebar_visible = not self.sidebar_visible

        if self.sidebar_visible:
            # Show sidebar with animation
            Animation(
                width=self._sidebar_default_width, duration=0.3, t='out_cubic'
            ).start(sidebar)
            sidebar.opacity = 1
        else:
            # Hide sidebar with animation
            Animation(width=0, duration=0.3, t='out_cubic').start(sidebar)
            sidebar.opacity = 0

    def _collect_section_cards(self):
        manager = self.section_manager

        cards = {}
        for screen in manager.screens:
            cards[screen.name] = screen.card

        if not cards:
            return

        self._section_cards = cards
        self.core_card = cards.get('Core')
        self.services_card = cards.get('Services')

        non_core_cards = {k: v for k, v in cards.items() if k != 'Core'}
        for name, card in non_core_cards.items():
            card.on_config_change = self.core_card.on_config_change
            card.root_path = self.core_card.root_path

    def _attach_model_to_cards(self):
        self._collect_section_cards()
        model = self.config_model or self._pending_config_model
        if not model:
            return

        self._pending_config_model = model

        for card in self._section_cards.values():
            if card is None:
                continue
            card.config_model = model
            card.load_from_model()

    def show_section(self, section):
        manager = self.section_manager
        self._collect_section_cards()

        target = section or 'Core'

        if target not in manager.screen_names:
            target = 'Core'

        manager.current = target
        self.active_section = target

    def _on_sidebar_section_select(self, sidebar, section):
        self.show_section(section)
