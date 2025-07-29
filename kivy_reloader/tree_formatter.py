"""
Tree Formatter Utility

Provides beautiful tree structure formatting for file lists.
"""

from typing import List, Set, Union


def format_file_tree(files: Union[Set[str], List[str]], title: str) -> str:
    """
    Format a set of file paths as a beautiful tree structure.

    Args:
        files: Set or list of file paths to format
        title: Title for the tree section

    Returns:
        Formatted tree string
    """
    if not files:
        return f'{title}: (empty)'

    # Convert to sorted list and build tree structure
    sorted_files = sorted(files)
    tree_lines = [f'{title}:']

    # Group files by directory structure
    tree_dict = {}
    for file_path in sorted_files:
        parts = file_path.split('/')
        current = tree_dict
        for part in parts[:-1]:  # All parts except filename
            if part not in current:
                current[part] = {}
            current = current[part]
        # Add the filename
        current[parts[-1]] = None

    def _build_tree_lines(tree_dict, prefix='', is_last_list=None):
        """Recursively build tree lines with proper box drawing characters."""
        if is_last_list is None:
            is_last_list = []

        items = list(tree_dict.items())
        lines = []

        for i, (name, subtree) in enumerate(items):
            is_last = i == len(items) - 1

            # Build the current line prefix
            current_prefix = ''
            for is_ancestor_last in is_last_list:
                current_prefix += '    ' if is_ancestor_last else '│   '

            # Add the current item
            connector = '└── ' if is_last else '├── '
            lines.append(f'{prefix}{current_prefix}{connector}{name}')

            # If this has children (is a directory), recurse
            if subtree is not None and subtree:
                child_lines = _build_tree_lines(
                    subtree, prefix, is_last_list + [is_last]
                )
                lines.extend(child_lines)

        return lines

    tree_lines.extend(_build_tree_lines(tree_dict))
    return '\n'.join(tree_lines)
