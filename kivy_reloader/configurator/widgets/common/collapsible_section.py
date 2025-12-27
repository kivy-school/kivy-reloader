"""Collapsible section widget for advanced settings"""

from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class CollapsibleSection(BoxLayout):
    """A collapsible container for grouping advanced settings.

    This widget uses deferred widget addition: children added after the header
    are stored in a list and only actually added to the widget tree when expanded.
    This avoids layout conflicts and infinite loops.

    Usage in KV:
        CollapsibleSection:
            title: 'Advanced Settings'
            collapsed: True

            # Children are stored and only attached when expanded
            CustomSwitch:
                title: 'Option 1'
                ...
    """

    title = StringProperty('Advanced Settings')
    collapsed = BooleanProperty(True)
    icon_rotation = NumericProperty(0)

    # Reference to the header widget (first child, defined in KV)
    _header = ObjectProperty(None, allownone=True)
    # List of stored children (not yet added to widget tree)
    _stored_children = ListProperty([])
    # Flag to track if header has been added
    _header_added = BooleanProperty(False)

    def add_widget(self, widget, *args, **kwargs):
        """Intercept widget additions - first widget is header, rest are stored."""
        if not self._header_added:
            # First widget added is the header from our KV rule
            self._header_added = True
            self._header = widget
            super().add_widget(widget, *args, **kwargs)
        else:
            # All subsequent widgets are stored
            self._stored_children.append(widget)

    def remove_widget(self, widget, *args, **kwargs):
        """Remove widget from both stored list and widget tree."""
        # Remove from stored list if present
        if widget in self._stored_children:
            self._stored_children.remove(widget)
        # Remove from widget tree if present
        if widget.parent is self:
            super().remove_widget(widget, *args, **kwargs)

    def on_kv_post(self, base_widget):
        """Initialize after KV is loaded."""
        # Set initial icon rotation
        self.icon_rotation = 0 if self.collapsed else 180

        # Attach children if starting expanded
        if not self.collapsed:
            self._attach_children()

    def toggle(self):
        """Toggle the collapsed state."""
        self.collapsed = not self.collapsed

    def on_collapsed(self, instance, value):
        """Handle collapsed state changes."""
        # Update icon rotation instantly
        self.icon_rotation = 0 if value else 180

        # Attach or detach children
        if value:
            self._detach_children()
        else:
            self._attach_children()

    def _attach_children(self):
        """Add stored children to the widget tree."""
        for child in self._stored_children:
            # Only add if not already in the tree
            if child.parent is None:
                super().add_widget(child)

    def _detach_children(self):
        """Remove stored children from the widget tree (but keep in list)."""
        for child in self._stored_children:
            if child.parent is self:
                super().remove_widget(child)
