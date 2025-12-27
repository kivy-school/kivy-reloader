import os
import subprocess
import sys

from kivy.animation import Animation
from kivy.app import App
from kivy.core.window import Window
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.screenmanager import Screen

from kivy_reloader.configurator.widgets.cards import (  # noqa: F401
    CoreCard,
    ServicesCard,
)
from kivy_reloader.configurator.widgets.common import ConfirmPopup, HelpPopup
from kivy_reloader.configurator.widgets.sidebar import SideBar  # noqa: F401
from kivy_reloader.configurator.widgets.toolbar import Toolbar  # noqa: F401
from kivy_reloader.lang import Builder

Builder.load_file(__file__)

# Keycodes for shortcuts
KEY_S = 115
KEY_F = 102
KEY_ESCAPE = 27
KEY_1 = 49  # 1-8 are consecutive: 49-56


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
        self._current_popup = None
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

        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

    def update_unsaved_indicator(self):
        """Update the unsaved changes indicator based on model state."""
        if self.config_model:
            self.toolbar.has_unsaved_changes = self.config_model.is_dirty()

    def _setup_keyboard_shortcuts(self):
        """Bind keyboard shortcuts to Window."""
        Window.bind(on_keyboard=self._on_keyboard)

    def _on_keyboard(self, window, keycode, scancode, codepoint, modifiers):
        """Handle keyboard shortcuts.

        Shortcuts:
            Ctrl+S: Save configuration
            Ctrl+F: Focus search field
            Ctrl+1-8: Navigate to section 1-8
            Escape: Close popup or show exit confirmation
        """
        modifier_set = set(modifiers)
        has_ctrl = 'ctrl' in modifier_set

        # Ctrl+S: Save
        if has_ctrl and keycode == KEY_S:
            self.handle_save()
            return True

        # Ctrl+F: Focus search
        if has_ctrl and keycode == KEY_F:
            self._focus_search()
            return True

        # Ctrl+1 through Ctrl+8: Navigate to section
        if has_ctrl and KEY_1 <= keycode <= KEY_1 + 7:
            section_index = keycode - KEY_1  # 0-7
            self._navigate_to_section_by_index(section_index)
            return True

        # Escape: Close popup or show exit confirmation
        if keycode == KEY_ESCAPE:
            self._handle_escape()
            return True

        return False

    def _focus_search(self):
        """Focus the search input in the sidebar."""
        if hasattr(self, 'sidebar') and 'search_input' in self.sidebar.ids:
            self.sidebar.ids.search_input.focus = True

    def _navigate_to_section_by_index(self, index):
        """Navigate to a section by its index (0-7)."""
        if not hasattr(self, 'sidebar'):
            return

        items = self.sidebar.all_items
        if 0 <= index < len(items):
            self.sidebar._select_item(items[index])

    def _handle_escape(self):
        """Handle Escape key: close popup or show exit confirmation."""
        # If a popup is open, close it
        if self._current_popup is not None:
            self._current_popup.dismiss()
            self._current_popup = None
            return

        # Otherwise, show exit confirmation
        self._show_exit_confirmation()

    def _show_exit_confirmation(self):
        """Show a confirmation popup asking if the user wants to exit."""
        popup = ConfirmPopup(
            title='Exit Configurator',
            message='Are you sure you want to exit the configurator?',
            confirm_text='Exit',
            cancel_text='Cancel',
            is_destructive=True,
            on_confirm=self._do_exit,
            on_cancel=self._clear_popup,
        )
        popup.bind(on_dismiss=lambda *args: self._clear_popup())
        self._current_popup = popup
        popup.open()

    def _do_exit(self):
        """Exit the application."""
        self._current_popup = None
        App.get_running_app().stop()

    def _clear_popup(self):
        """Clear the current popup reference."""
        self._current_popup = None

    def handle_apply_reload(self):
        """Handle Apply & Reload action"""
        if self.config_model:
            try:
                # Save first
                self.config_model.save()
                print('Configuration saved and will be applied on next reload')
                # Trigger hot reload on the configurator app itself
                app = App.get_running_app()
                if hasattr(app, 'rebuild'):
                    app.rebuild()
            except Exception as e:
                print(f'Error applying configuration: {e}')
        else:
            print('No config model available')

    def handle_save(self):
        """Handle Save action"""
        if self.config_model:
            try:
                self.config_model.save()
                self.update_unsaved_indicator()
                print(f'Configuration saved to {self.config_model.config_path}')
            except Exception as e:
                print(f'Error saving configuration: {e}')
        else:
            print('No config model available')

    def handle_restore(self):
        """Handle Restore defaults action - shows confirmation first."""
        popup = ConfirmPopup(
            title='Restore Defaults',
            message='This will reset ALL settings to their default values. Any unsaved changes will be lost. Are you sure?',
            confirm_text='Restore',
            cancel_text='Cancel',
            is_destructive=True,
            on_confirm=self._do_restore,
            on_cancel=self._clear_popup,
        )
        popup.bind(on_dismiss=lambda *args: self._clear_popup())
        self._current_popup = popup
        popup.open()

    def _do_restore(self):
        """Actually perform the restore after confirmation."""
        self._current_popup = None
        if self.config_model:
            self.config_model.reset_all(to_defaults=True)
            self._attach_model_to_cards()
            print('Configuration restored to defaults')
        else:
            print('No config model available')

    def handle_export(self):
        """Handle Export config action"""
        if not self.config_model or not self.config_model.config_path:
            print('No config model or path available')
            return

        export_path = self.config_model.config_path.parent / 'kivy-reloader-export.toml'
        try:
            self.config_model.export_to_file(export_path)
            # Show success popup
            self._show_export_success_popup(export_path)
        except Exception as e:
            print(f'Error exporting configuration: {e}')

    def _show_export_success_popup(self, export_path):
        """Show success popup after export."""

        def open_folder():
            self._current_popup = None
            folder = str(export_path.parent)
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.run(['open', folder])
            else:
                subprocess.run(['xdg-open', folder])

        popup = ConfirmPopup(
            title='Export Successful',
            message=f'Configuration exported to:\n{export_path.name}',
            confirm_text='Open Folder',
            cancel_text='OK',
            is_destructive=False,
            on_confirm=open_folder,
            on_cancel=self._clear_popup,
        )
        popup.bind(on_dismiss=lambda *args: self._clear_popup())
        self._current_popup = popup
        popup.open()

    def handle_import(self):
        """Handle Import config action - shows confirmation first."""
        if not self.config_model or not self.config_model.config_path:
            print('No config model or path available')
            return

        import_path = self.config_model.config_path.parent / 'kivy-reloader-import.toml'

        if not import_path.exists():
            # Show error popup if file doesn't exist
            popup = ConfirmPopup(
                title='Import Failed',
                message=f'Import file not found:\n{import_path.name}\n\nCreate this file with your settings to import.',
                confirm_text='OK',
                cancel_text='',
                is_destructive=False,
                on_confirm=self._clear_popup,
            )
            popup.bind(on_dismiss=lambda *args: self._clear_popup())
            self._current_popup = popup
            popup.open()
            return

        # Show confirmation popup
        def do_import():
            self._current_popup = None
            try:
                self.config_model.import_from_file(import_path, merge=True)
                self._attach_model_to_cards()
                print(f'Configuration imported from {import_path}')
            except Exception as e:
                print(f'Error importing configuration: {e}')

        popup = ConfirmPopup(
            title='Import Settings',
            message=f'Import settings from:\n{import_path.name}\n\nThis will merge with your current configuration.',
            confirm_text='Import',
            cancel_text='Cancel',
            is_destructive=False,
            on_confirm=do_import,
            on_cancel=self._clear_popup,
        )
        popup.bind(on_dismiss=lambda *args: self._clear_popup())
        self._current_popup = popup
        popup.open()

    def handle_help(self):
        """Handle Help button - shows keyboard shortcuts and version info."""
        popup = HelpPopup()
        popup.bind(on_dismiss=lambda *args: self._clear_popup())
        self._current_popup = popup
        popup.open()

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

        # Wire up config change callbacks to update unsaved indicator
        def on_any_config_change(config):
            self.update_unsaved_indicator()

        non_core_cards = {k: v for k, v in cards.items() if k != 'Core'}
        for name, card in non_core_cards.items():
            card.on_config_change = on_any_config_change
            card.root_path = self.core_card.root_path

        # Also wire up core card
        if self.core_card:
            self.core_card.on_config_change = on_any_config_change

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

        # Update indicator after initial load (should be clean)
        self.update_unsaved_indicator()

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
