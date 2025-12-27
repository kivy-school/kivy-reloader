"""
Folder-only selection controller for recursive folder watching.
Only tracks folders, not files.
"""

from pathlib import Path
from typing import List

try:
    from .selection_controller import SelectionController
except ImportError:
    from selection_controller import SelectionController


class FolderOnlySelectionController(SelectionController):
    """Selection controller that only tracks folders (no files)."""

    def get_all_selected_files(self) -> List[str]:
        """
        Override to return empty list since we only track folders.
        Use get_all_selected_folders() instead.
        """
        return []

    def get_all_selected_folders(self) -> List[str]:
        """
        Get list of all selected folder paths (no files).
        Uses cached folder contents when available to avoid re-scanning.

        Returns:
            List of absolute folder paths (deduplicated)
        """
        folders_set = set()

        for path_str in self._selected_paths:
            path = Path(path_str)

            if not path.exists():
                continue

            # Only add if it's a directory
            if path.is_dir():
                folders_set.add(str(path))

        return sorted(list(folders_set))

    def get_relative_selected_folders(self) -> List[str]:
        """
        Get list of all selected folder paths as relative paths.
        Special case: If root folder is among selected paths, return ['.']
        Filters out redundant child folders when parent is already selected.

        Returns:
            List of paths relative to root_path, or ['.'] if root is selected
        """
        folders = self.get_all_selected_folders()

        # Special case: if root folder is in the selection, return ['.']
        # (selecting root means watch everything, so just return ['.'])
        root_resolved = str(self.root_path.resolve())
        for folder_path in folders:
            if Path(folder_path).resolve() == Path(root_resolved):
                return ['.']

        # Convert to relative paths
        relative_folders = []
        for folder_path in folders:
            try:
                rel_path = Path(folder_path).relative_to(self.root_path)
                relative_folders.append(str(rel_path))
            except ValueError:
                # Path is not relative to root_path, skip it
                pass

        # Filter out redundant child folders
        # If a parent folder is in the list, remove all its children
        filtered_folders = []
        for folder in relative_folders:
            folder_path = Path(folder)
            is_redundant = False

            # Check if any parent of this folder is also in the list
            for other_folder in relative_folders:
                if folder == other_folder:
                    continue

                other_path = Path(other_folder)
                # Check if other_folder is a parent of folder
                try:
                    folder_path.relative_to(other_path)
                    # If we get here, other_folder is a parent of folder
                    is_redundant = True
                    break
                except ValueError:
                    # other_folder is not a parent
                    continue

            if not is_redundant:
                filtered_folders.append(folder)

        return filtered_folders

    def _select_folder_children(self, folder_path: Path) -> List[str]:
        """
        Override to only select subfolders, not files.
        Recursively select all subfolders of a folder.

        Args:
            folder_path: Path to folder

        Returns:
            Empty list (we don't track files)
        """
        if not folder_path.exists() or not folder_path.is_dir():
            return []

        try:
            for item_path in folder_path.iterdir():
                if self.should_ignore(item_path):
                    continue

                # Only process directories, skip files
                if item_path.is_dir():
                    item_resolved = str(item_path.resolve())

                    # Add this subfolder to selected paths
                    self._selected_paths.add(item_resolved)

                    # Recursively select its children
                    self._select_folder_children(item_path)
        except PermissionError:
            pass

        # We don't cache file lists since we don't track files
        return []

    def _deselect_folder_children(self, folder_path: Path) -> None:
        """
        Override to only deselect subfolders, not files.
        Recursively deselect all subfolders of a folder.

        Args:
            folder_path: Path to folder
        """
        if not folder_path.exists() or not folder_path.is_dir():
            return

        folder_path_str = str(folder_path.resolve())

        # Clear any cache for this folder
        self._folder_files_cache.pop(folder_path_str, None)

        try:
            for item_path in folder_path.iterdir():
                if self.should_ignore(item_path):
                    continue

                # Only process directories, skip files
                if item_path.is_dir():
                    item_resolved = str(item_path.resolve())

                    # Remove this subfolder from selected paths
                    self._selected_paths.discard(item_resolved)

                    # Recursively deselect its children
                    self._deselect_folder_children(item_path)
        except PermissionError:
            pass


if __name__ == '__main__':
    # Test the folder-only controller
    import os

    # Get current directory
    current_dir = os.path.dirname(__file__)
    root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

    print('=' * 60)
    print(f'Testing FolderOnlySelectionController with root: {root}')
    print('=' * 60)

    controller = FolderOnlySelectionController(root)

    # Test 1: Select root folder - should return ['.']
    print("\n[Test 1] Select root folder - should return ['.']")
    controller.select_path(root)
    folders = controller.get_relative_selected_folders()
    print(f'  ✓ Selected folders: {folders}')
    assert folders == ['.'], f"Expected ['.'], got {folders}"

    # Test 2: Clear and select a subfolder
    print('\n[Test 2] Select configurator_ui folder')
    controller.clear_selection()
    configurator_ui = os.path.join(root, 'configurator_ui')
    controller.select_path(configurator_ui)
    folders = controller.get_relative_selected_folders()
    print(f'  ✓ Selected folders: {folders}')
    assert 'configurator_ui' in folders or 'configurator_ui' in str(folders), (
        'Should contain configurator_ui'
    )

    # Test 3: Select multiple folders
    print('\n[Test 3] Select multiple folders')
    controller.clear_selection()
    configurator_ui = os.path.join(root, 'configurator_ui')
    style = os.path.join(root, 'style')
    controller.select_path(configurator_ui)
    controller.select_path(style)
    folders = controller.get_relative_selected_folders()
    print(f'  ✓ Selected folders: {folders}')
    assert len(folders) >= 2, f'Should have at least 2 folders, got {len(folders)}'

    # Test 4: Verify no files are tracked
    print('\n[Test 4] Verify get_all_selected_files returns empty')
    files = controller.get_all_selected_files()
    print(f'  ✓ Selected files: {files}')
    assert len(files) == 0, f'Should have 0 files, got {len(files)}'

    # Test 5: Get absolute folder paths
    print('\n[Test 5] Get absolute folder paths')
    abs_folders = controller.get_all_selected_folders()
    print(f'  ✓ Absolute folders count: {len(abs_folders)}')
    assert len(abs_folders) >= 2, 'Should have at least 2 folders'

    # Test 6: Filter redundant child folders
    print('\n[Test 6] Filter redundant child folders (parent + child selected)')
    controller.clear_selection()
    widgets_folder = os.path.join(root, 'configurator_ui', 'widgets')
    cards_folder = os.path.join(widgets_folder, 'cards')
    # Select both parent and child
    controller.select_path(widgets_folder)
    controller.select_path(cards_folder)
    folders = controller.get_relative_selected_folders()
    print(f'  ✓ Selected folders: {folders}')
    # Should only return parent folder, not the child
    rel_widgets = os.path.join('configurator_ui', 'widgets')
    assert any(rel_widgets in str(f) or f == rel_widgets for f in folders), (
        'Should contain widgets folder'
    )
    rel_cards = os.path.join('configurator_ui', 'widgets', 'cards')
    assert not any(rel_cards in str(f) for f in folders), (
        'Should NOT contain cards folder (redundant)'
    )
    assert len(folders) == 1, (
        f'Should have only 1 folder (parent), got {len(folders)}: {folders}'
    )

    print('\n' + '=' * 60)
    print('✅ All FolderOnlySelectionController tests passed!')
    print('=' * 60)
