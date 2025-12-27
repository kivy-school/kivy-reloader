import fnmatch
from pathlib import Path
from typing import List

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

from .folder_selection_controller import FolderOnlySelectionController
from .selection_controller import SelectionController

Builder.load_file(__file__)


class HoverBehavior(object):
    """Hover behavior.
    :Events:
        `on_enter`
            Fired when mouse enter the bbox of the widget.
        `on_leave`
            Fired when the mouse exit the widget
    """

    is_hovered = BooleanProperty(False)
    border_point = ObjectProperty(None)
    """Contains the last relevant point received by the Hoverable. This can
    be used in `on_enter` or `on_leave` in order to know where was dispatched the event.
    """

    def __init__(self, **kwargs):
        self.register_event_type('on_enter')
        self.register_event_type('on_leave')
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(HoverBehavior, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return  # do proceed if I'm not displayed <=> If have no parent
        pos = args[1]
        # Next line to_widget allow to compensate for relative layout
        inside = self.collide_point(*self.to_widget(*pos))
        if self.is_hovered == inside:
            # We have already done what was needed
            return
        self.border_point = pos
        self.is_hovered = inside
        if inside:
            self.dispatch('on_enter')
        else:
            self.dispatch('on_leave')

    def on_enter(self):
        Clock.schedule_once(lambda dt: Window.set_system_cursor('hand'))

    def on_leave(self):
        Window.set_system_cursor('arrow')


Factory.register('HoverBehavior', HoverBehavior)


class BaseNode(BoxLayout):
    """Basic node for file/folder."""

    name = StringProperty()
    path = StringProperty()
    selected = BooleanProperty(False)
    indent_level = NumericProperty(0)
    parent_folder = ObjectProperty(None, allownone=True)
    selection_controller = ObjectProperty(None)
    auto_select_parent = BooleanProperty(
        True
    )  # Whether to auto-select parent when all children selected
    _syncing = False  # Flag to prevent infinite loops

    def sync_selection_from_controller(self):
        """Sync the selected property from the controller."""
        new_state = self.selection_controller.is_selected(self.path)
        if self.selected != new_state:
            self._syncing = True
            self.selected = new_state
            self._syncing = False

    def on_selected(self, instance, value):
        """When UI selection changes, update the controller and sync children."""
        if self._syncing:
            return

        self._syncing = True

        # Update controller
        if value:
            self.selection_controller.select_path(self.path)
        else:
            self.selection_controller.deselect_path(self.path)

        # If this is a folder, sync all children from controller (recursively)
        if isinstance(self, Folder) and self.items:
            self._sync_children_recursive()

        # Update parent folder's selection state based on siblings
        self._update_parent_selection()

        # Notify container to update count
        self._notify_selection_changed()

        self._syncing = False

    def _update_parent_selection(self):
        """Update parent folder selection based on children states.

        Behavior depends on auto_select_parent property:
        - If True (file picker): Selecting all children auto-selects parent
        - If False (folder picker): Only deselects parent when child is deselected
        """
        if not self.parent_folder or not isinstance(self.parent_folder, Folder):
            return

        parent = self.parent_folder
        if not parent.items or parent._syncing:
            return

        # Don't update parent if its children haven't been loaded yet
        # (lazy loading - children are loaded on expand)
        if not parent.children_loaded:
            return

        if not self.selection_controller:
            return

        parent_is_selected = parent.selection_controller.is_selected(parent.path)

        if self.auto_select_parent:
            # File picker behavior: auto-select parent when all children are selected
            all_selected = all(
                item.selection_controller.is_selected(item.path)
                for item in parent.items
                if isinstance(item, BaseNode)
            )

            parent_should_be_selected = all_selected

            if parent_should_be_selected != parent_is_selected:
                parent._syncing = True

                # Directly update controller's selected paths without triggering
                # recursive child selection
                parent_path_resolved = str(Path(parent.path).resolve())
                if parent_should_be_selected:
                    parent.selection_controller._selected_paths.add(
                        parent_path_resolved
                    )
                else:
                    parent.selection_controller._selected_paths.discard(
                        parent_path_resolved
                    )

                parent.sync_selection_from_controller()
                parent._syncing = False

                # Notify picker about the change
                parent._notify_selection_changed()

                # Recursively update grandparent
                parent._update_parent_selection()
        else:
            # Folder picker behavior: only deselect parent when a child is deselected
            any_deselected = any(
                not item.selection_controller.is_selected(item.path)
                for item in parent.items
                if isinstance(item, BaseNode)
            )

            # Only deselect parent if
            # any child is deselected AND parent is currently selected
            if any_deselected and parent_is_selected:
                parent._syncing = True

                # Deselect parent in controller
                # without triggering recursive child deselection
                parent_path_resolved = str(Path(parent.path).resolve())
                parent.selection_controller._selected_paths.discard(
                    parent_path_resolved
                )

                parent.sync_selection_from_controller()
                parent._syncing = False

                # Notify picker about the change
                parent._notify_selection_changed()

                # Recursively update grandparent
                parent._update_parent_selection()

    def _notify_selection_changed(self):
        """Notify the dropdown picker that selection changed."""
        # Find the DropdownContainer
        widget = self.parent
        while widget:
            if isinstance(widget, DropdownContainer):
                if widget.dropdown_picker:
                    widget.dropdown_picker._on_controller_selection_change()
                break
            widget = widget.parent if hasattr(widget, 'parent') else None


class File(BaseNode):
    """Leaf file in the tree."""

    pass


class Folder(BaseNode):
    """Folder containing files/subfolders."""

    expanded = BooleanProperty(False)
    items = ListProperty([])
    children_loaded = BooleanProperty(
        False
    )  # Track if we've loaded this folder's contents

    def on_items(self, instance, value):
        """When the list of items changes, set parent and pass controller reference."""
        for item in self.items:
            if isinstance(item, BaseNode):
                item.parent_folder = self
                item.selection_controller = self.selection_controller
                # Sync selection state from controller
                item.sync_selection_from_controller()

        self._update_children_visibility()

    def _sync_children_recursive(self):
        """Recursively sync all children and grandchildren from controller"""
        for item in self.items:
            if isinstance(item, BaseNode):
                item.sync_selection_from_controller()
                # If it's a folder with loaded children, sync recursively
                if isinstance(item, Folder) and item.items:
                    item._sync_children_recursive()

    def toggle_expanded(self):
        """Toggle between expanded/collapsed."""
        # If expanding and haven't loaded children yet, load them now
        if not self.expanded and not self.children_loaded:
            self._load_children()

        self.expanded = not self.expanded

    def _load_children(self):
        """Lazy load the contents of this folder (1 level only)"""
        if self.children_loaded:
            return

        folder_path = Path(self.path)
        if not folder_path.exists() or not folder_path.is_dir():
            return

        # Get pre-selected files from the dropdown picker (if available)
        pre_selected_paths = set()

        # Try to find the DropdownContainer
        widget = self.parent
        while widget:
            if isinstance(widget, DropdownContainer):
                if widget.dropdown_picker and widget.dropdown_picker.initial_selection:
                    # Convert relative paths to absolute for comparison
                    root = Path(widget.root_path)
                    for rel_path in widget.dropdown_picker.initial_selection:
                        abs_path = (root / rel_path).resolve()
                        pre_selected_paths.add(str(abs_path))
                break
            widget = widget.parent if hasattr(widget, 'parent') else None

        # Common patterns to ignore
        IGNORE_PATTERNS = {
            '__pycache__',
            '.git',
            '.venv',
            'venv',
            'env',
            '.idea',
            '.vscode',
            'node_modules',
            '.pytest_cache',
            '*.pyc',
            '.DS_Store',
            'Thumbs.db',
            '.gitignore',
        }

        def should_ignore(path):
            """Check if a path should be ignored"""
            name = path.name
            if name in IGNORE_PATTERNS:
                return True
            for pattern in IGNORE_PATTERNS:
                if '*' in pattern:
                    if fnmatch.fnmatch(name, pattern):
                        return True
            return False

        # Scan directory contents (only 1 level)
        try:
            folders = []
            files = []

            for item_path in folder_path.iterdir():
                if should_ignore(item_path):
                    continue

                if item_path.is_file():
                    file_node = File(
                        name=item_path.name,
                        path=str(item_path),
                        indent_level=self.indent_level + 1,
                        selection_controller=self.selection_controller,
                        auto_select_parent=self.auto_select_parent,
                    )
                    files.append(file_node)
                elif item_path.is_dir():
                    folder_node = Folder(
                        name=item_path.name,
                        path=str(item_path),
                        indent_level=self.indent_level + 1,
                        selection_controller=self.selection_controller,
                        auto_select_parent=self.auto_select_parent,
                    )
                    folders.append(folder_node)

            # Sort folders and files separately by name (case-insensitive)
            folders.sort(key=lambda x: x.name.lower())
            files.sort(key=lambda x: x.name.lower())

            # Combine: folders first, then files
            self.items = folders + files
            self.children_loaded = True

        except PermissionError:
            self.children_loaded = True  # Mark as loaded even if failed

    def on_expanded(self, instance, value):
        """Update visibility of children when expanding/collapsing."""
        self._update_children_visibility()

    def _update_children_visibility(self):
        """Add/remove children from the visual container."""
        container = self.children_container
        container.clear_widgets()

        if self.expanded:
            for item in self.items:
                if isinstance(item, BaseNode):
                    container.add_widget(item)


class FolderNode(Folder):
    """Folder node that only loads subfolders, not files."""

    def _load_children(self):
        """Lazy load only subfolders (no files)"""
        if self.children_loaded:
            return

        folder_path = Path(self.path)
        if not folder_path.exists() or not folder_path.is_dir():
            return

        # Common patterns to ignore
        IGNORE_PATTERNS = {
            '__pycache__',
            '.git',
            '.venv',
            'venv',
            'env',
            '.idea',
            '.vscode',
            'node_modules',
            '.pytest_cache',
            '*.pyc',
            '.DS_Store',
            'Thumbs.db',
            '.gitignore',
        }

        def should_ignore(path):
            """Check if a path should be ignored"""
            name = path.name
            if name in IGNORE_PATTERNS:
                return True
            for pattern in IGNORE_PATTERNS:
                if '*' in pattern:
                    if fnmatch.fnmatch(name, pattern):
                        return True
            return False

        # Scan directory contents (only folders, no files)
        try:
            folders = []

            for item_path in folder_path.iterdir():
                if should_ignore(item_path):
                    continue

                # Only add folders, skip files
                if item_path.is_dir():
                    folder_node = FolderNode(
                        name=item_path.name,
                        path=str(item_path),
                        indent_level=self.indent_level + 1,
                        selection_controller=self.selection_controller,
                        auto_select_parent=self.auto_select_parent,
                    )
                    folders.append(folder_node)

            # Sort folders by name (case-insensitive)
            folders.sort(key=lambda x: x.name.lower())

            # Set items (only folders)
            self.items = folders
            self.children_loaded = True

        except PermissionError:
            self.children_loaded = True  # Mark as loaded even if failed


class DropdownContainer(BoxLayout):
    """The dropdown menu container widget"""

    dropdown_picker = ObjectProperty(None, allownone=True)
    root_path = StringProperty('.')  # Path to scan, defaults to current directory
    selected_count = NumericProperty(0)  # Number of selected files (for display)
    selection_controller = ObjectProperty(None)  # Reference to SelectionController

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize selection controller
        self.selection_controller = SelectionController(self.root_path)
        self._create_tree_from_path()

    def _create_tree_from_path(self, dt=None):
        """Create just the root folder (lazy loading - children loaded on expand)"""
        root_path = Path(self.root_path)

        if not root_path.exists():
            print(f'Warning: Path does not exist: {self.root_path}')
            return

        # Create just the root folder (no children yet)
        root_folder = Folder(
            name=root_path.name if root_path.name else str(root_path),
            path=str(root_path),
            indent_level=0,
            selection_controller=self.selection_controller,
        )

        # Sync root folder selection from controller
        root_folder.sync_selection_from_controller()

        # Remove existing folders
        for child in self.tree_container.children[:]:
            if isinstance(child, Folder):
                self.tree_container.remove_widget(child)

        # Add the new root folder
        self.tree_container.add_widget(root_folder)

    def set_root_path(self, path):
        """Change the root path and rebuild the tree"""
        self.root_path = path
        self._create_tree_from_path()

    def get_selected_files(self):
        """Get list of all selected file paths using the controller"""
        return self.selection_controller.get_all_selected_files()

    def clear_selection(self):
        """Clear all selections using the controller"""
        self.selection_controller.clear_selection()
        # Clear initial_selection in the picker so it doesn't show stale data
        if self.dropdown_picker:
            self.dropdown_picker.initial_selection = []
        # Sync all visible nodes
        self._sync_all_nodes()
        # Notify picker to update display
        self.dropdown_picker._on_controller_selection_change()

    def _sync_all_nodes(self):
        """Recursively sync all nodes' selection state from controller"""
        for child in self.tree_container.children:
            if isinstance(child, BaseNode):
                self._sync_node_recursive(child)

    def _sync_node_recursive(self, node):
        """Recursively sync a node and its children"""
        node.sync_selection_from_controller()
        if isinstance(node, Folder):
            for item in node.items:
                self._sync_node_recursive(item)

    def on_touch_down(self, touch):
        """Handle touch events - consume touches to prevent background scrolling"""
        # If touch is inside the container bounds, always consume it
        if self.collide_point(*touch.pos):
            # Propagate to children (tree_container, buttons, etc.)
            super().on_touch_down(touch)
            # Return True to consume the touch
            # and prevent it from reaching background widgets
            return True
        # If touch is outside, ignore it (let it pass through)
        return False

    def on_touch_move(self, touch):
        """Handle touch move events - consume to prevent background scrolling"""
        # If touch is inside the container, always consume it
        if self.collide_point(*touch.pos):
            super().on_touch_move(touch)
            return True
        return False

    def on_touch_up(self, touch):
        """Handle touch up events"""
        # If touch is inside the container, always consume it
        if self.collide_point(*touch.pos):
            super().on_touch_up(touch)
            return True
        return False


class DropdownPicker(ButtonBehavior, BoxLayout):
    """The main dropdown picker widget for file/folder selection"""

    selected_text = StringProperty('Select files or folders...')
    placeholder_text = StringProperty(
        'Select files or folders...'
    )  # Placeholder when nothing selected
    is_hovered = BooleanProperty(False)
    is_open = BooleanProperty(False)
    container = ObjectProperty(None, allownone=True)
    root_path = StringProperty('.')  # Path to scan for files/folders
    selected_files = ListProperty([])  # List of selected file paths
    initial_selection = ListProperty([])  # Files to pre-select (relative paths)
    scroll_view = ObjectProperty(None)  # Reference to parent ScrollView

    def on_selected_files(self, instance, value):
        """Update the selected count in the container when selection changes"""
        if self.container:
            self.container.selected_count = len(value)

    #     # Data management
    #     cached_data = ListProperty([])  # Filtered data for display

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # When hovering over the picker, change background color
        Window.bind(mouse_pos=self.on_mouse_pos)

        # When clicking outside container, close the dropdown
        Window.bind(on_mouse_down=self.on_mouse_down)

        # Update text and selected_files when initial_selection changes
        self.bind(initial_selection=self._on_initial_selection_changed)

    #     # Initialize cached_data with data
    #     self.bind(data=self._update_cached_data)

    # def _update_cached_data(self, *args):
    #     """Update cached_data when data changes"""
    #     self.cached_data = self.data[:]

    def _on_initial_selection_changed(self, instance, value):
        """Convert initial_selection to selected_files for display before dropdown opens"""
        if value:
            # Convert relative paths to absolute paths
            root = Path(self.root_path).resolve()
            selected = []
            for rel_path in value:
                abs_path = (root / rel_path).resolve()
                if abs_path.exists():
                    selected.append(str(abs_path))
            self.selected_files = selected
        else:
            self.selected_files = []

        self._update_selected_text()

    def on_mouse_pos(self, window, pos):
        """Update hover state based on mouse position"""
        if not self.get_root_window():
            return

        # Convert window coordinates to widget coordinates
        widget_pos = self.to_widget(*pos)
        if self.collide_point(*widget_pos):
            self.is_hovered = True
        else:
            self.is_hovered = False

    def on_mouse_down(self, window, x, y, button, modifiers):
        """Close dropdown if clicking outside"""
        if self.is_open and self.container:
            # Adjust Window y coordinate for Kivy's coordinate system
            # In Kivy, (0,0) is bottom left, but Window gives (0,0) at top left
            # So we need to invert the y coordinate
            y = Window.height - y
            # If mouse pos is outside container and outside picker, close it
            if not (
                self.container.x <= x <= self.container.x + self.container.width
                and self.container.y
                <= y
                <= self.container.y + self.container.height + dp(34)
            ):
                self.close_dropdown()

    def toggle_dropdown(self):
        """Toggle the dropdown menu open/closed"""
        if self.is_open:
            self.close_dropdown()
        else:
            self.open_dropdown()

    def open_dropdown(self):
        """Open the dropdown menu"""
        if self.is_open:
            return

        # Mark as open
        self.is_open = True

        # Bind keyboard for Escape handling
        Window.bind(on_keyboard=self._on_keyboard)

        # Create container if it doesn't exist
        if not self.container:
            self.container = DropdownContainer(root_path=self.root_path)
            self.container.dropdown_picker = self

            # Initialize controller with initial selection
            if self.initial_selection:
                self.container.selection_controller.set_initial_selection(
                    self.initial_selection
                )

            # Update selected_files from controller after initialization
            self.selected_files = (
                self.container.selection_controller.get_all_selected_files()
            )
            # Explicitly update the count in case on_selected_files doesn't trigger
            self.container.selected_count = len(self.selected_files)

        # Add to window (so it floats above other widgets)
        Window.add_widget(self.container)

        # Position below the picker
        self._update_container_position()
        self._update_container_size()

        # Bind to update position when picker moves or resizes
        self.bind(
            pos=self._update_container_position, size=self._update_container_position
        )
        self.bind(size=self._update_container_size)

        # Bind to update position when container height changes (e.g. expanding folders)
        self.container.bind(height=self._update_container_position)

        # Bind to ScrollView's scroll position - close dropdown on any scroll
        if self.scroll_view:
            self.scroll_view.bind(scroll_y=self._on_scroll_change)

        # Bind to track selection changes
        self._setup_selection_tracking()

    def _on_scroll_change(self, instance, value):
        """Called when the ScrollView scrolls - close dropdown immediately"""
        self.close_dropdown()

    def _setup_selection_tracking(self):
        """Setup bindings to track selection changes in the tree"""
        if not self.container:
            return

        # Schedule update after container is fully built
        Clock.schedule_once(self._bind_selection_updates, 0.1)

    def _bind_selection_updates(self, dt):
        """Bind to selection changes in all nodes"""
        for child in self.container.tree_container.children:
            if isinstance(child, Folder):
                self._bind_node_selection(child)

    def _bind_node_selection(self, node):
        """Recursively bind to selection changes"""
        node.bind(selected=self._on_selection_change)

        if isinstance(node, Folder):
            for item in node.items:
                self._bind_node_selection(item)

    def _on_selection_change(self, instance, value):
        """Update selected files list when any node changes"""
        if self.container:
            self.selected_files = self.container.get_selected_files()
            self._update_selected_text()

    def _on_controller_selection_change(self):
        """Called when selection changes via controller"""
        if self.container and self.container.selection_controller:
            files = self.container.selection_controller.get_all_selected_files()
            # Force ListProperty update by creating a new list
            self.selected_files = files[:]
            self._update_selected_text()
            # Update the count in the container
            if self.container:
                self.container.selected_count = len(self.selected_files)

    def _update_selected_text(self):
        """Update the display text based on selected files"""
        count = len(self.selected_files)

        if count == 0:
            self.selected_text = self.placeholder_text
        elif count == 1:
            # Show just the filename
            self.selected_text = Path(self.selected_files[0]).name
        else:
            self.selected_text = f'{count} files selected'

    def close_dropdown(self):
        """Close the dropdown menu"""
        if not self.is_open:
            return

        # Mark as closed
        self.is_open = False

        # Unbind keyboard
        Window.unbind(on_keyboard=self._on_keyboard)

        # Force a property change notification to trigger bindings with the
        # final selection. This ensures config is updated when dropdown closes
        self.property('selected_files').dispatch(self)

        # Unbind from ScrollView
        if self.scroll_view:
            self.scroll_view.unbind(scroll_y=self._on_scroll_change)

        # Remove the dropdown container from window
        if self.container:
            Window.remove_widget(self.container)

    def _on_keyboard(self, window, keycode, scancode, codepoint, modifiers):
        """Handle keyboard events - close on Escape."""
        if keycode == 27:  # Escape
            self.close_dropdown()
            return True  # Consume the event
        return False

    def _update_container_position(self, *args):
        """Update container position when picker moves or resizes"""
        if self.container:
            self.container.x, self.container.y = self.to_window(
                self.x, self.y - self.container.height
            )

    def _update_container_size(self, *args):
        """Update container width to match the picker"""
        if self.container:
            self.container.width = self.width


class FolderOnlyDropdownContainer(DropdownContainer):
    """Container that only shows folders (no files)."""

    def __init__(self, **kwargs):
        # Don't call super().__init__() yet, we need to set up controller first
        BoxLayout.__init__(self, **kwargs)
        # Import here to avoid circular imports
        # Initialize folder-only selection controller
        self.selection_controller = FolderOnlySelectionController(self.root_path)
        self._create_tree_from_path()

    def _create_tree_from_path(self, dt=None):
        """Create just the root folder (lazy loading - children loaded on expand)"""
        root_path = Path(self.root_path)

        if not root_path.exists():
            print(f'Warning: Path does not exist: {self.root_path}')
            return

        # Create root as FolderNode instead of Folder
        root_folder = FolderNode(
            name=root_path.name if root_path.name else str(root_path),
            path=str(root_path),
            indent_level=0,
            selection_controller=self.selection_controller,
            auto_select_parent=False,  # Don't auto-select parent in folder picker
        )

        # Sync root folder selection from controller
        root_folder.sync_selection_from_controller()

        # Remove existing folders
        for child in self.tree_container.children[:]:
            if isinstance(child, (Folder, FolderNode)):
                self.tree_container.remove_widget(child)

        # Add the new root folder
        self.tree_container.add_widget(root_folder)


class FolderOnlyDropdownPicker(DropdownPicker):
    """Picker for selecting folders only (no files)."""

    selected_text = StringProperty('Select folders...')

    def _on_selection_change(self, instance, value):
        """Update selected folders list when any node changes - override to use folders"""
        # Call the controller selection change method which properly handles folders
        self._on_controller_selection_change()

    def _on_initial_selection_changed(self, instance, value):
        """Convert initial_selection to selected_files for display before dropdown opens"""
        if value:
            # Convert relative paths to absolute paths
            root = Path(self.root_path).resolve()
            selected = []
            for rel_path in value:
                abs_path = (root / rel_path).resolve()
                if abs_path.exists() and abs_path.is_dir():
                    selected.append(str(abs_path))
            self.selected_files = selected
        else:
            self.selected_files = []
        self._update_selected_text()

    def _on_controller_selection_change(self):
        """Called when selection changes via controller - override to use folders"""
        if self.container and self.container.selection_controller:
            # Get filtered folders (without redundant children)
            # Get relative folders (filtered) and convert back to absolute for display
            rel_folders = (
                self.container.selection_controller.get_relative_selected_folders()
            )
            # Convert relative paths back to absolute for selected_files
            root = Path(self.root_path).resolve()
            folders = [str(root / rel_path) for rel_path in rel_folders]

            self.selected_files = (
                folders  # Store folders in selected_files (keeps compatibility)
            )
            self._update_selected_text()
            # Update the count in the container - schedule for next frame to ensure UI updates
            if self.container:
                count = len(folders)
                # Use Clock.schedule_once to defer the update to next frame
                Clock.schedule_once(
                    lambda dt: setattr(self.container, 'selected_count', count), 0
                )

    def open_dropdown(self):
        """Open the dropdown menu with folder-only container"""
        if self.is_open:
            return

        # Mark as open
        self.is_open = True

        # Bind keyboard for Escape handling
        Window.bind(on_keyboard=self._on_keyboard)

        # Create folder-only container if it doesn't exist
        if not self.container:
            self.container = FolderOnlyDropdownContainer(root_path=self.root_path)
            self.container.dropdown_picker = self

            # Initialize controller with initial selection
            if self.initial_selection:
                self.container.selection_controller.set_initial_selection(
                    self.initial_selection
                )
                # Sync the root folder's selection state after setting initial selection
                if self.container.tree_container.children:
                    for child in self.container.tree_container.children:
                        if isinstance(child, BaseNode):
                            child.sync_selection_from_controller()

            # Update selected_files from controller (using filtered folders)
            # Get relative folders (filtered) and convert back to absolute for display
            rel_folders = (
                self.container.selection_controller.get_relative_selected_folders()
            )
            # Convert relative paths back to absolute for selected_files
            root = Path(self.root_path).resolve()
            folders = [str(root / rel_path) for rel_path in rel_folders]

            # Store folders in selected_files
            self.selected_files = folders
            # Update the count directly
            self.container.selected_count = len(folders)

        # Add to window (so it floats above other widgets)
        Window.add_widget(self.container)

        # Position below the picker
        self._update_container_position()
        self._update_container_size()

        # Bind to update position when picker moves or resizes
        self.bind(
            pos=self._update_container_position, size=self._update_container_position
        )
        self.bind(size=self._update_container_size)

        # Bind to update position when container height changes (e.g. expanding folders)
        self.container.bind(height=self._update_container_position)

        # Bind to ScrollView's scroll position - close dropdown on any scroll
        if self.scroll_view:
            self.scroll_view.bind(scroll_y=self._on_scroll_change)

        # Bind to track selection changes
        self._setup_selection_tracking()

    def get_selected_folders_for_config(self) -> List[str]:
        """
        Get selected folders in format for config.
        Special case: If root folder is selected, return ['.']

        Returns:
            List of relative folder paths, or ['.'] if root selected
        """
        # If container exists, use its controller
        if self.container and self.container.selection_controller:
            return self.container.selection_controller.get_relative_selected_folders()

        # If container doesn't exist but we have initial_selection, return that
        # (This happens when user hasn't opened dropdown since app started)
        if self.initial_selection:
            return self.initial_selection

        return []

    def _update_selected_text(self):
        """Update the display text based on selected folders"""
        # Check selected_files (which contains folders for this picker)
        count = len(self.selected_files)

        if count == 0:
            self.selected_text = 'Select folders...'
        elif count == 1:
            # Check if the selected folder is the root folder
            selected_path = Path(self.selected_files[0]).resolve()
            root_path = Path(self.root_path).resolve()

            if selected_path == root_path:
                # Root folder selected - show root folder name
                folder_name = root_path.name if root_path.name else str(root_path)
                self.selected_text = folder_name
            else:
                # Show the folder name
                self.selected_text = Path(self.selected_files[0]).name
        else:
            self.selected_text = f'{count} folders selected'
