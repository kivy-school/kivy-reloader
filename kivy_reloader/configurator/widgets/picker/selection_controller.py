"""
Selection controller for file/folder tree picker.
Handles all selection logic independently from UI.
"""

import fnmatch
from pathlib import Path
from typing import List, Set

from kivy_reloader.config import config


class SelectionController:
    """Manages file/folder selection state and operations."""

    # Common patterns to ignore when scanning directories
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

    def __init__(self, root_path: str):
        """
        Initialize the selection controller.

        Args:
            root_path: Root directory path for file scanning
        """
        self.root_path = Path(root_path)
        self._selected_paths: Set[str] = set()  # Set of selected file/folder paths
        self._folder_files_cache: dict[
            str, List[str]
        ] = {}  # Cache: folder_path -> list of file paths

    @property
    def selected_paths(self) -> Set[str]:
        """Get the set of selected paths."""
        return self._selected_paths.copy()

    @property
    def selected_count(self) -> int:
        """Get the total number of selected files (expanding folders)."""
        return len(self.get_all_selected_files())

    def select_path(self, path: str) -> None:
        """
        Mark a path (file or folder) as selected.
        If it's a folder, also marks all children recursively as selected.
        """
        path_obj = Path(path)
        path_resolved = str(path_obj.resolve())
        self._selected_paths.add(path_resolved)

        # If it's a folder, recursively select all children
        if path_obj.exists() and path_obj.is_dir():
            self._select_folder_children(path_obj)

    def deselect_path(self, path: str) -> None:
        """
        Mark a path (file or folder) as deselected.
        If it's a folder, also deselects all children recursively.
        """
        path_obj = Path(path)
        path_resolved = str(path_obj.resolve())
        self._selected_paths.discard(path_resolved)

        # If it's a folder, recursively deselect all children
        if path_obj.exists() and path_obj.is_dir():
            self._deselect_folder_children(path_obj)

    def toggle_path(self, path: str) -> bool:
        """
        Toggle selection state of a path.

        Returns:
            bool: True if now selected, False if now deselected
        """
        path_resolved = str(Path(path).resolve())
        if path_resolved in self._selected_paths:
            self._selected_paths.discard(path_resolved)
            return False
        else:
            self._selected_paths.add(path_resolved)
            return True

    def is_selected(self, path: str) -> bool:
        """Check if a path is selected."""
        return str(Path(path).resolve()) in self._selected_paths

    def clear_selection(self) -> None:
        """Clear all selections and cache."""
        self._selected_paths.clear()
        self._folder_files_cache.clear()

    def set_initial_selection(self, relative_paths: List[str]) -> None:
        """
        Set initial selection from relative paths.

        Args:
            relative_paths: List of paths relative to root_path
        """
        self._selected_paths.clear()
        self._folder_files_cache.clear()  # Clear cache when changing selection
        for rel_path in relative_paths:
            abs_path = (self.root_path / rel_path).resolve()
            # Use select_path to trigger recursive folder selection
            self.select_path(str(abs_path))

    def get_all_selected_files(self) -> List[str]:
        """
        Get list of all selected file paths, expanding folders recursively.
        Uses cached folder contents when available to avoid re-scanning.

        Returns:
            List of absolute file paths (deduplicated)
        """
        files_set = set()

        for path_str in self._selected_paths:
            path = Path(path_str)

            if not path.exists():
                continue

            if path.is_file():
                files_set.add(str(path))
            elif path.is_dir():
                # Check cache first
                if path_str in self._folder_files_cache:
                    files_set.update(self._folder_files_cache[path_str])
                else:
                    # Cache miss - walk the folder and cache the result
                    folder_files = self._walk_folder_for_files(path)
                    self._folder_files_cache[path_str] = folder_files
                    files_set.update(folder_files)

        return sorted(list(files_set))

    def get_relative_selected_files(self) -> List[str]:
        """
        Get list of all selected file paths as relative paths.

        Returns:
            List of paths relative to root_path
        """
        files = self.get_all_selected_files()
        relative_files = []

        for file_path in files:
            try:
                rel_path = Path(file_path).relative_to(self.root_path)
                relative_files.append(str(rel_path))
            except ValueError:
                # Path is not relative to root_path, skip it
                pass

        return relative_files

    def should_ignore(self, path: Path) -> bool:
        """
        Check if a path should be ignored based on ignore patterns.

        Args:
            path: Path to check

        Returns:
            bool: True if path should be ignored
        """
        name = path.name
        if name in self.IGNORE_PATTERNS:
            return True

        for pattern in self.IGNORE_PATTERNS:
            if '*' in pattern:
                if fnmatch.fnmatch(name, pattern):
                    return True

        return False

    def _select_folder_children(self, folder_path: Path) -> List[str]:
        """
        Recursively select all children (files and folders) of a folder.
        Also builds cache of files in each folder to avoid re-scanning.

        Args:
            folder_path: Path to folder

        Returns:
            List of file paths in this folder and all subfolders
        """
        if not folder_path.exists() or not folder_path.is_dir():
            return []

        folder_path_str = str(folder_path.resolve())
        files_in_this_folder = []

        try:
            for item_path in folder_path.iterdir():
                if self.should_ignore(item_path):
                    continue

                item_resolved = str(item_path.resolve())

                # Add this child to selected paths
                self._selected_paths.add(item_resolved)

                # If it's a file, add to this folder's file list
                if item_path.is_file():
                    files_in_this_folder.append(item_resolved)
                # If it's a folder, recursively select its children
                elif item_path.is_dir():
                    subfolder_files = self._select_folder_children(item_path)
                    # Include subfolder's files in this folder's count
                    if subfolder_files:  # Only extend if there are files
                        files_in_this_folder.extend(subfolder_files)
        except PermissionError:
            pass

        # Cache the file list for this folder
        self._folder_files_cache[folder_path_str] = files_in_this_folder
        return files_in_this_folder

    def _deselect_folder_children(self, folder_path: Path) -> None:
        """
        Recursively deselect all children (files and folders) of a folder.
        Also invalidates cache for this folder.

        Args:
            folder_path: Path to folder
        """
        if not folder_path.exists() or not folder_path.is_dir():
            return

        folder_path_str = str(folder_path.resolve())

        # Invalidate cache for this folder
        self._folder_files_cache.pop(folder_path_str, None)

        try:
            for item_path in folder_path.iterdir():
                if self.should_ignore(item_path):
                    continue

                # Remove this child from selected paths
                self._selected_paths.discard(str(item_path.resolve()))

                # If it's a folder, recursively deselect its children
                if item_path.is_dir():
                    self._deselect_folder_children(item_path)
        except PermissionError:
            pass

    def _walk_folder_for_files(self, folder_path: Path) -> List[str]:
        """
        Walk through a folder recursively and return all file paths.

        Args:
            folder_path: Path to folder to walk

        Returns:
            List of absolute file paths
        """
        files = []

        if not folder_path.exists() or not folder_path.is_dir():
            return files

        try:
            for item_path in folder_path.rglob('*'):
                if item_path.is_file() and not self.should_ignore(item_path):
                    # Check if any parent directory should be ignored
                    parents_ok = True
                    for parent in item_path.parents:
                        if parent == folder_path:
                            break
                        if self.should_ignore(parent):
                            parents_ok = False
                            break

                    if parents_ok:
                        files.append(str(item_path))
        except PermissionError:
            pass

        return files

    def get_folder_file_count(self, folder_path: str) -> int:
        """
        Get the count of files in a folder (recursively).

        Args:
            folder_path: Path to folder

        Returns:
            int: Number of files in the folder
        """
        return len(self._walk_folder_for_files(Path(folder_path)))

    def get_children_selection_state(
        self, folder_path: str, children_paths: List[str]
    ) -> str:
        """
        Determine the selection state of a folder based on its children.

        Args:
            folder_path: Path to the folder
            children_paths: List of direct children paths

        Returns:
            str: 'all' if all selected, 'none' if none selected, 'partial' if some selected
        """
        if not children_paths:
            # No children - check if folder itself is selected
            return 'all' if self.is_selected(folder_path) else 'none'

        selected_count = sum(1 for child in children_paths if self.is_selected(child))

        if selected_count == 0:
            return 'none'
        elif selected_count == len(children_paths):
            return 'all'
        else:
            return 'partial'

    def select_all_children(self, folder_path: str, children_paths: List[str]) -> None:
        """
        Select all children of a folder.

        Args:
            folder_path: Path to the folder
            children_paths: List of direct children paths
        """
        for child in children_paths:
            self.select_path(child)

    def deselect_all_children(
        self, folder_path: str, children_paths: List[str]
    ) -> None:
        """
        Deselect all children of a folder.

        Args:
            folder_path: Path to the folder
            children_paths: List of direct children paths
        """
        for child in children_paths:
            self.deselect_path(child)


if __name__ == '__main__':
    # Comprehensive tests
    import os

    # Get current directory
    current_dir = os.path.dirname(__file__)
    root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

    print('=' * 60)
    print(f'Testing SelectionController with root: {root}')
    print('=' * 60)

    controller = SelectionController(root)

    # Test 1: Initial selection
    print('\n[Test 1] Initial selection: main.py')
    controller.set_initial_selection(['main.py'])
    count = controller.selected_count
    files = controller.get_relative_selected_files()
    print(f'  ✓ Selected count: {count}')
    print(f'  ✓ Selected files: {files}')
    assert count == 1, f'Expected 1, got {count}'
    assert 'main.py' in files, 'main.py should be selected'

    # Test 2: Add another file selection
    print('\n[Test 2] Select configurator_ui/app.py')
    app_py_path = os.path.join(root, 'configurator_ui', 'app.py')
    controller.select_path(app_py_path)
    count = controller.selected_count
    files = controller.get_relative_selected_files()
    print(f'  ✓ Selected count: {count}')
    print(f'  ✓ Selected files: {files}')
    assert count == 2, f'Expected 2, got {count}'
    assert 'main.py' in files, 'main.py should still be selected'
    assert (
        os.path.join('configurator_ui', 'app.py') in files
        or 'configurator_ui\\app.py' in files
    ), 'app.py should be selected'

    # Test 3: Unselect the file
    print('\n[Test 3] Unselect configurator_ui/app.py')
    controller.deselect_path(app_py_path)
    count = controller.selected_count
    files = controller.get_relative_selected_files()
    print(f'  ✓ Selected count: {count}')
    print(f'  ✓ Selected files: {files}')
    assert count == 1, f'Expected 1, got {count}'
    assert 'main.py' in files, 'main.py should still be selected'

    # Test 4: Select a folder (without expanding - simulates unexpanded folder)
    print('\n[Test 4] Select configurator_ui/widgets folder (unexpanded)')
    widgets_folder = os.path.join(root, 'configurator_ui', 'widgets')
    controller.select_path(widgets_folder)
    count = controller.selected_count
    print(f'  ✓ Selected count: {count} (includes all files in widgets folder)')
    assert count > 1, f'Expected more than 1 file, got {count}'
    assert controller.is_selected(widgets_folder), 'widgets folder should be selected'

    # Test 5: Check folder file count
    print('\n[Test 5] Get folder file count for widgets')
    folder_count = controller.get_folder_file_count(widgets_folder)
    print(f'  ✓ Widgets folder contains {folder_count} files')
    assert folder_count > 0, 'Widgets folder should contain files'

    # Test 6: Simulate expanding folder and checking children states (Option A behavior)
    print(
        '\n[Test 6] Simulate expanding widgets folder - check if subfolders inherit selection'
    )
    cards_folder = os.path.join(widgets_folder, 'cards')
    common_folder = os.path.join(widgets_folder, 'common')
    picker_folder = os.path.join(widgets_folder, 'picker')

    # With Option A, when parent is selected, ALL children should also be marked as selected
    print(f'  ✓ Is widgets selected? {controller.is_selected(widgets_folder)}')
    print(f'  ✓ Is widgets/cards selected? {controller.is_selected(cards_folder)}')
    print(f'  ✓ Is widgets/common selected? {controller.is_selected(common_folder)}')
    print(f'  ✓ Is widgets/picker selected? {controller.is_selected(picker_folder)}')
    assert controller.is_selected(widgets_folder), 'Parent folder should be selected'
    assert controller.is_selected(cards_folder), (
        'Child folder (cards) should be auto-selected'
    )
    assert controller.is_selected(common_folder), (
        'Child folder (common) should be auto-selected'
    )
    assert controller.is_selected(picker_folder), (
        'Child folder (picker) should be auto-selected'
    )

    # Test 7: Get children selection state
    print('\n[Test 7] Get selection state of widgets folder children')
    children = [cards_folder, common_folder, picker_folder]
    state = controller.get_children_selection_state(widgets_folder, children)
    print(f'  ✓ Children selection state: {state}')
    # Since widgets is selected but children aren't individually selected, state should be 'none'
    # This is actually a design question - should selecting parent auto-select children?

    # Test 8: Select all children explicitly
    print('\n[Test 8] Select all children of widgets folder explicitly')
    controller.select_all_children(widgets_folder, children)
    state = controller.get_children_selection_state(widgets_folder, children)
    print(f'  ✓ Children selection state after select_all: {state}')
    assert state == 'all', f"Expected 'all', got {state}"

    # Test 9: Deselect one child to create partial selection
    print('\n[Test 9] Deselect one child (cards) to create partial selection')
    controller.deselect_path(cards_folder)
    state = controller.get_children_selection_state(widgets_folder, children)
    print(f'  ✓ Children selection state after deselecting one: {state}')
    assert state == 'partial', f"Expected 'partial', got {state}"

    # Test 10: Toggle functionality
    print('\n[Test 10] Toggle selection')
    print(
        f'  ✓ Is main.py selected? {controller.is_selected(os.path.join(root, "main.py"))}'
    )
    result = controller.toggle_path(os.path.join(root, 'main.py'))
    print(f'  ✓ After toggle: {result} (False = deselected)')
    assert not result, 'Should be deselected after toggle'
    result = controller.toggle_path(os.path.join(root, 'main.py'))
    print(f'  ✓ After second toggle: {result} (True = selected)')
    assert result, 'Should be selected after second toggle'

    # Test 11: Clear all selections
    print('\n[Test 11] Clear all selections')
    controller.clear_selection()
    count = controller.selected_count
    print(f'  ✓ Selected count after clear: {count}')
    assert count == 0, f'Expected 0, got {count}'

    # Test 12: Relative path conversion
    print('\n[Test 12] Test relative path conversion')
    controller.select_path(os.path.join(root, 'main.py'))
    controller.select_path(os.path.join(root, 'configurator_ui', 'app.py'))
    relative_files = controller.get_relative_selected_files()
    print(f'  ✓ Relative paths: {relative_files}')
    assert all(not os.path.isabs(f) for f in relative_files), (
        'All paths should be relative'
    )

    print('\n' + '=' * 60)
    print('✅ All tests passed!')
    print('=' * 60)
