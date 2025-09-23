"""
Delta Transfer System

Implements differential file transfer to send only changed files
instead of the entire project for hot reload optimization.
"""

import hashlib
import json
import os
import time
import zipfile
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Set, Tuple

from kivy.logger import Logger

from .tree_formatter import format_file_tree

# Constants
DELTA_CHANGE_THRESHOLD = 0.3  # Use delta if less than 30% of files changed


class DeltaTransferManager:
    """Manages delta transfers by tracking file changes and creating minimal updates."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.state_file = self.project_root / '.kivy_reloader_state.json'
        self.last_state: Dict[str, str] = {}
        self.load_state()

    def load_state(self):
        """Load the last known file state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.last_state = json.load(f)

                # Format and display the loaded files as a tree
                loaded_files_tree = format_file_tree(
                    set(self.last_state.keys()),
                    f'Current app state has {len(self.last_state)} files',
                )
                Logger.info(loaded_files_tree)

            except (json.JSONDecodeError, OSError) as e:
                Logger.warning(f'Delta: Failed to load state file: {e}')
                self.last_state = {}
        else:
            Logger.info('Delta: No previous state found, will perform full transfer')

    def save_state(self, current_state: Dict[str, str]):
        """Save the current file state to disk."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(current_state, f, indent=2)
            # Update in-memory state as well
            self.last_state = current_state.copy()
            Logger.info(f'Delta: Saved state with {len(current_state)} files')
        except OSError as e:
            Logger.warning(f'Delta: Failed to save state file: {e}')

    @staticmethod
    def get_file_hash(file_path: Path) -> str:
        """Calculate MD5 hash of a file."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (OSError, IOError) as e:
            Logger.warning(f'Delta: Failed to hash {file_path}: {e}')
            return ''

    def scan_project_files(self, exclude_patterns: List[str]) -> Dict[str, str]:
        """
        Scan project directory and return file paths with their hashes.

        Args:
            exclude_patterns: List of glob patterns for files to exclude

        Returns:
            Dict mapping relative file paths to their MD5 hashes
        """
        # Add internal files to exclude patterns
        internal_excludes = ['.kivy_reloader_state.json', 'app_copy.zip']
        exclude_patterns += internal_excludes

        file_hashes = {}

        for root, dirs, files in os.walk(self.project_root):
            # Convert to relative path from project root
            rel_root = Path(root).relative_to(self.project_root)

            # Filter directories based on exclude patterns
            dirs[:] = [
                d
                for d in dirs
                if not self._should_exclude_path(rel_root / d, exclude_patterns)
            ]

            for file in files:
                rel_path = rel_root / file
                abs_path = Path(root) / file

                # Check exclude patterns
                if not self._should_exclude_path(rel_path, exclude_patterns):
                    file_hash = self.get_file_hash(abs_path)
                    if file_hash:  # Only include files we can successfully hash
                        file_hashes[str(rel_path)] = file_hash
                        Logger.debug(f'Delta: Included {rel_path}')
                else:
                    Logger.debug(f'Delta: Excluded {rel_path}')

        Logger.info(f'Delta: Scanned {len(file_hashes)} files')
        return file_hashes

    def _should_exclude_path(self, rel_path: Path, exclude_patterns: List[str]) -> bool:
        """Check if a path should be excluded."""
        path_str = str(rel_path).replace('\\', '/')
        return any(
            self._match_pattern(path_str, pattern) for pattern in exclude_patterns
        )

    @staticmethod
    def _match_pattern(path: str, pattern: str) -> bool:
        """Match a path against a glob pattern."""

        # Handle both directory and file patterns
        if path.startswith(pattern.rstrip('/*')):
            return True

        # Use fnmatch for glob patterns
        if fnmatch(path, pattern):
            return True

        # Special handling for ** patterns - check if pattern matches without **
        if '**' in pattern:
            # For **/*.py, also check if it matches *.py for root files
            simplified_pattern = pattern.replace('**/', '')
            if fnmatch(path, simplified_pattern):
                return True

        return False

    def detect_changes(
        self, current_state: Dict[str, str]
    ) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Detect changes between current and last known state.

        Returns:
            Tuple of (added_files, modified_files, deleted_files)
        """
        current_files = set(current_state.keys())
        last_files = set(self.last_state.keys())

        added_files = current_files - last_files
        deleted_files = last_files - current_files

        # Check for modifications in existing files
        modified_files = set()
        for file_path in current_files & last_files:
            if current_state[file_path] != self.last_state[file_path]:
                modified_files.add(file_path)

        Logger.info(
            f'Delta: Changes detected - Added: {len(added_files)}, '
            f'Modified: {len(modified_files)}, Deleted: {len(deleted_files)}'
        )

        return added_files, modified_files, deleted_files

    def create_delta_archive(
        self, changed_files: Set[str], deleted_files: Set[str], output_path: str
    ) -> Dict[str, any]:
        """
        Create a zip archive containing only changed files.

        Args:
            changed_files: Set of relative file paths that have changed
            deleted_files: Set of relative file paths that were deleted
            output_path: Path where to save the delta archive

        Returns:
            Dict with metadata about the created archive
        """
        metadata = {
            'type': 'delta',
            'timestamp': time.time(),
            'file_count': len(changed_files),
            'files': list(changed_files),
            'deleted_files': list(deleted_files),
        }

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add metadata
            zip_file.writestr('_delta_metadata.json', json.dumps(metadata, indent=2))

            # Add changed files
            for rel_path in changed_files:
                abs_path = self.project_root / rel_path
                if abs_path.exists():
                    zip_file.write(abs_path, rel_path)
                    Logger.debug(f'Delta: Added {rel_path} to archive')

        archive_size = os.path.getsize(output_path)
        metadata['archive_size_mb'] = archive_size / (1024 * 1024)

        Logger.info(
            f'Delta: Created archive with {len(changed_files)} changed files, '
            f'{len(deleted_files)} deleted files ({archive_size / 1024:.1f} KB)'
        )
        return metadata

    def create_full_archive(
        self, all_files: Dict[str, str], output_path: str
    ) -> Dict[str, any]:
        """
        Create a full archive when delta transfer is not possible.

        Args:
            all_files: Dict of all project files with their hashes
            output_path: Path where to save the full archive

        Returns:
            Dict with metadata about the created archive
        """
        metadata = {
            'type': 'full',
            'timestamp': time.time(),
            'file_count': len(all_files),
            'files': list(all_files.keys()),
        }

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add metadata
            zip_file.writestr('_delta_metadata.json', json.dumps(metadata, indent=2))

            # Add all files
            for rel_path in all_files.keys():
                abs_path = self.project_root / rel_path
                if abs_path.exists():
                    zip_file.write(abs_path, rel_path)

        archive_size = os.path.getsize(output_path)
        metadata['archive_size_mb'] = archive_size / (1024 * 1024)

        Logger.info(
            'Delta: Created full archive with '
            f'{len(all_files)} files ({archive_size / 1024:.1f} KB)'
        )
        return metadata

    @staticmethod
    def should_use_delta(
        added_files: Set[str],
        modified_files: Set[str],
        deleted_files: Set[str],
        total_files: int,
    ) -> bool:
        """
        Determine if delta transfer would be beneficial.

        Args:
            added_files: Set of added file paths
            modified_files: Set of modified file paths
            deleted_files: Set of deleted file paths
            total_files: Total number of files in project

        Returns:
            True if delta transfer should be used
        """
        changed_count = len(added_files) + len(modified_files) + len(deleted_files)

        if total_files == 0:
            return False

        change_ratio = changed_count / total_files

        # Use delta if less than threshold of files changed
        use_delta = change_ratio < DELTA_CHANGE_THRESHOLD

        Logger.info(
            f'Delta: Change ratio {change_ratio:.1%} (threshold 30%)'
            f' - Using {"delta" if use_delta else "full"} transfer'
        )
        return use_delta

    def prepare_transfer(
        self, exclude_patterns: List[str]
    ) -> Tuple[str, Dict[str, any], Dict[str, str]]:
        """
        Prepare transfer archive (delta or full) based on detected changes.

        Args:
            exclude_patterns: List of glob patterns for files to exclude

        Returns:
            Tuple of (archive_path, metadata, current_state)
        """
        # Scan current project state
        current_state = self.scan_project_files(exclude_patterns)

        # Detect changes
        added_files, modified_files, deleted_files = self.detect_changes(current_state)
        changed_files = added_files | modified_files

        # Display changes as beautiful tree structures
        if added_files:
            Logger.info(format_file_tree(added_files, 'Added files'))
        else:
            Logger.info('Added files: (none)')

        if modified_files:
            Logger.info(format_file_tree(modified_files, 'Modified files'))
        else:
            Logger.info('Modified files: (none)')

        if deleted_files:
            Logger.info(format_file_tree(deleted_files, 'Deleted files'))
        else:
            Logger.info('Deleted files: (none)')

        if changed_files:
            Logger.info(format_file_tree(changed_files, 'Changed files'))
        else:
            Logger.info('Changed files: (none)')

        # Determine transfer type
        output_path = str(self.project_root / 'app_copy.zip')

        if self.should_use_delta(
            added_files, modified_files, deleted_files, len(current_state)
        ):
            # Create delta archive
            metadata = self.create_delta_archive(
                changed_files, deleted_files, output_path
            )
        else:
            # Create full archive
            metadata = self.create_full_archive(current_state, output_path)

        # Do NOT save state here. Caller should persist only after ACK.
        return output_path, metadata, current_state
