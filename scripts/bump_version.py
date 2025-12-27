#!/usr/bin/env python3
"""
Version Bumping Script for kivy-reloader.

Updates the version number in all relevant files:
- pyproject.toml
- uv.lock
- kivy_reloader/__init__.py

Usage:
    python scripts/bump_version.py patch   # 0.8.2 -> 0.8.3
    python scripts/bump_version.py minor   # 0.8.2 -> 0.9.0
    python scripts/bump_version.py major   # 0.8.2 -> 1.0.0
    python scripts/bump_version.py 1.2.3   # Set specific version
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Files to update with their patterns
VERSION_FILES = {
    'pyproject.toml': {
        'path': PROJECT_ROOT / 'pyproject.toml',
        'pattern': r'(version\s*=\s*["\'])(\d+\.\d+\.\d+)(["\'])',
    },
    '__init__.py': {
        'path': PROJECT_ROOT / 'kivy_reloader' / '__init__.py',
        'pattern': r'(__version__\s*=\s*["\'])(\d+\.\d+\.\d+)(["\'])',
    },
}

# uv.lock needs special handling since it has multiple packages
UV_LOCK_PATH = PROJECT_ROOT / 'uv.lock'

# Expected number of command-line arguments (script name + bump type)
REQUIRED_ARGS = 2


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a version string into (major, minor, patch) tuple."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_str)
    if not match:
        raise ValueError(f'Invalid version format: {version_str}')
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_version(major: int, minor: int, patch: int) -> str:
    """Format version tuple as string."""
    return f'{major}.{minor}.{patch}'


def get_current_version() -> str:
    """Get the current version from pyproject.toml."""
    pyproject = VERSION_FILES['pyproject.toml']['path']
    content = pyproject.read_text(encoding='utf-8')
    pattern = VERSION_FILES['pyproject.toml']['pattern']
    match = re.search(pattern, content)
    if not match:
        raise ValueError('Could not find version in pyproject.toml')
    return match.group(2)


def bump_version(current: str, bump_type: str) -> str:
    """
    Bump the version based on the bump type.

    Args:
        current: Current version string (e.g., '0.8.2')
        bump_type: One of 'patch', 'minor', 'major', or a specific version

    Returns:
        New version string
    """
    major, minor, patch = parse_version(current)

    if bump_type == 'patch':
        return format_version(major, minor, patch + 1)
    elif bump_type == 'minor':
        return format_version(major, minor + 1, 0)
    elif bump_type == 'major':
        return format_version(major + 1, 0, 0)
    else:
        # Assume it's a specific version string
        parse_version(bump_type)  # Validate format
        return bump_type


def update_file(file_info: dict, old_version: str, new_version: str) -> bool:
    """
    Update version in a single file.

    Returns:
        True if file was updated, False if version not found or file doesn't exist
    """
    path = file_info['path']
    pattern = file_info['pattern']

    if not path.exists():
        return False

    content = path.read_text(encoding='utf-8')

    # Replace the version
    def replace_version(match):
        prefix = match.group(1)
        suffix = match.group(3)
        return f'{prefix}{new_version}{suffix}'

    new_content, count = re.subn(pattern, replace_version, content, count=1)

    if count == 0:
        return False

    path.write_text(new_content, encoding='utf-8')
    return True


def update_uv_lock(old_version: str, new_version: str) -> bool:
    """
    Update version in uv.lock for the kivy-reloader package specifically.

    uv.lock has multiple packages, so we need to find the kivy-reloader section
    and update only its version.
    """
    if not UV_LOCK_PATH.exists():
        return False

    content = UV_LOCK_PATH.read_text(encoding='utf-8')

    # Pattern to find kivy-reloader package block and its version
    # Matches: name = "kivy-reloader"\nversion = "X.X.X"
    pattern = r'(name\s*=\s*["\']kivy-reloader["\']\s*\n\s*version\s*=\s*["\'])(\d+\.\d+\.\d+)(["\'])'

    new_content, count = re.subn(pattern, rf'\g<1>{new_version}\g<3>', content)

    if count == 0:
        return False

    UV_LOCK_PATH.write_text(new_content, encoding='utf-8')
    return True


def main():  # noqa: PLR0912, PLR0915
    if len(sys.argv) < REQUIRED_ARGS:
        print(__doc__)
        print('Error: Please specify bump type (patch, minor, major) or version number')
        sys.exit(1)

    bump_type = sys.argv[1].lower()

    # Validate bump type
    valid_types = {'patch', 'minor', 'major'}
    if bump_type not in valid_types:
        # Check if it's a valid version string
        try:
            parse_version(bump_type)
        except ValueError:
            print(f'Error: Invalid bump type or version: {bump_type}')
            print(f'Valid types: {", ".join(valid_types)} or a version like 1.2.3')
            sys.exit(1)

    # Get current version
    try:
        current_version = get_current_version()
    except ValueError as e:
        print(f'Error: {e}')
        sys.exit(1)

    # Calculate new version
    new_version = bump_version(current_version, bump_type)

    print('=' * 50)
    print('Version Bump')
    print('=' * 50)
    print(f'\n  {current_version} → {new_version}\n')

    # Update all files
    print('Updating files:')
    for name, file_info in VERSION_FILES.items():
        path = file_info['path']
        if not path.exists():
            print(f'  ⚠️  {name}: file not found')
            continue

        if update_file(file_info, current_version, new_version):
            print(f'  ✅ {name}')
        else:
            print(f'  ⚠️  {name}: version pattern not found')

    # Update uv.lock separately (needs special handling)
    if UV_LOCK_PATH.exists():
        if update_uv_lock(current_version, new_version):
            print('  ✅ uv.lock')
        else:
            print('  ⚠️  uv.lock: kivy-reloader version not found')
    else:
        print('  ⚠️  uv.lock: file not found')

    print(f'\n✅ Version bumped to {new_version}')

    # Clean dist folder and build
    print('\n📦 Building package...')
    dist_dir = PROJECT_ROOT / 'dist'

    # Remove old wheels and tarballs (keep .gitignore)
    if dist_dir.exists():
        for file in dist_dir.iterdir():
            if file.suffix in {'.whl', '.gz'}:
                file.unlink()
                print(f'  🗑️  Removed: {file.name}')

    # Run uv build
    result = subprocess.run(
        ['uv', 'build'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print('  ❌ Build failed:')
        print(result.stderr)
        sys.exit(1)

    # List created files
    print('  ✅ Build complete!')
    if dist_dir.exists():
        for file in dist_dir.iterdir():
            if file.suffix in {'.whl', '.gz'}:
                size_kb = file.stat().st_size / 1024
                print(f'     📄 {file.name} ({size_kb:.1f} KB)')

    print('\n🚀 Ready to publish!')
    print('   uv publish')
    print("\nDon't forget to:")
    print('  1. Commit changes')
    print(f'  2. Create git tag: git tag v{new_version}')


if __name__ == '__main__':
    main()
