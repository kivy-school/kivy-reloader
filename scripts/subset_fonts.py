#!/usr/bin/env python3
"""
Font Subsetting Script for kivy-reloader.

Automatically scans the codebase to find which MDI icons and emojis are used,
then creates subset font files containing only those glyphs.

This dramatically reduces font file sizes (typically 90-98% reduction).

Usage:
    python scripts/subset_fonts.py

Requirements:
    pip install fonttools brotli
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

THEME_DIR = PROJECT_ROOT / 'kivy_reloader' / 'configurator' / 'theme'
ASSETS_DIR = THEME_DIR / 'assets'
CONFIGURATOR_DIR = PROJECT_ROOT / 'kivy_reloader' / 'configurator'


def extract_used_icon_names(search_dir: Path) -> set[str]:
    """
    Scan .py and .kv files to find MDI icon names referenced via unicode['icon-name'].
    """
    icon_pattern = re.compile(r"unicode\s*\[\s*['\"]([a-zA-Z0-9-]+)['\"]\s*\]")
    used_icons = set()

    for ext in ('*.py', '*.kv'):
        for file_path in search_dir.rglob(ext):
            try:
                content = file_path.read_text(encoding='utf-8')
                matches = icon_pattern.findall(content)
                used_icons.update(matches)
            except (OSError, UnicodeDecodeError) as e:
                print(f'Warning: Could not read {file_path}: {e}')

    return used_icons


def extract_used_emojis(search_dir: Path) -> set[str]:
    """
    Scan .py and .kv files to find emoji characters.

    Searches for:
    1. Emojis in markup like [font={emoji_font}]💾[/font]
    2. Emojis in Python strings (e.g., sidebar menu_items with 'icon': '🔥')
    3. Any high-unicode character that could be an emoji
    """
    # Pattern to find emojis in markup like [font={emoji_font}]💾[/font]
    emoji_markup_pattern = re.compile(r'\[font=\{?emoji_font\}?\]([^\[]+)\[/font\]')

    # Pattern to find emojis in Python dict/list literals like 'icon': '🔥'
    icon_dict_pattern = re.compile(r"['\"]icon['\"]\s*:\s*['\"]([^'\"]+)['\"]")

    used_emojis = set()

    def add_emoji_chars(text: str):
        """Extract emoji characters from a string."""
        for char in text:
            codepoint = ord(char)
            # Include: emojis (U+1F300+), symbols (U+2000+), variation selectors
            if codepoint > 0x2000 or codepoint == 0xFE0F:
                used_emojis.add(char)

    for ext in ('*.py', '*.kv'):
        for file_path in search_dir.rglob(ext):
            try:
                content = file_path.read_text(encoding='utf-8')

                # Find emojis in [font={emoji_font}]...[/font] markup
                for match in emoji_markup_pattern.findall(content):
                    add_emoji_chars(match)

                # Find emojis in 'icon': '...' patterns (sidebar, etc.)
                for match in icon_dict_pattern.findall(content):
                    add_emoji_chars(match)

            except (OSError, UnicodeDecodeError) as e:
                print(f'Warning: Could not read {file_path}: {e}')

    return used_emojis


def get_icon_unicodes_from_module(icon_names: set[str]) -> dict[str, str]:
    """
    Parse icons.py to get unicode values for the given icon names.
    Returns a dict mapping icon name to unicode codepoint (e.g., 'U+F0156').
    """
    icons_py = THEME_DIR / 'icons.py'
    content = icons_py.read_text(encoding='utf-8')

    icon_to_unicode = {}

    for name in icon_names:
        # Match patterns like 'icon-name': '\U000f0xxx'
        pattern = rf"'{re.escape(name)}':\s*'(\\U[0-9a-fA-F]+)'"
        match = re.search(pattern, content)
        if match:
            # Convert \U000f0xxx to U+F0XXX format for pyftsubset
            unicode_escape = match.group(1)
            # \U000f0156 -> f0156 -> F0156
            hex_val = unicode_escape.replace('\\U', '').lstrip('0').upper()
            if not hex_val:
                hex_val = '0'
            icon_to_unicode[name] = f'U+{hex_val}'
        else:
            print(f'Warning: Icon "{name}" not found in icons.py')

    return icon_to_unicode


def emojis_to_unicode_ranges(emojis: set[str]) -> list[str]:
    """
    Convert emoji characters to unicode range format for pyftsubset.
    """
    unicode_ranges = []
    for emoji in emojis:
        for char in emoji:
            codepoint = ord(char)
            if codepoint > 0x7F:  # Non-ASCII
                unicode_ranges.append(f'U+{codepoint:04X}')
    return sorted(set(unicode_ranges))


def subset_font(
    input_path: Path,
    output_path: Path,
    unicodes: list[str] | None = None,
    text: str | None = None,
) -> bool:
    """
    Create a subset font containing only the specified glyphs.

    Args:
        input_path: Path to the original font file
        output_path: Path for the subset font file
        unicodes: List of unicode ranges (e.g., ['U+F0156', 'U+F0453'])
        text: String of characters to include (alternative to unicodes)

    Returns:
        True if successful, False otherwise
    """
    try:
        from fontTools.subset import main as subset_main
    except ImportError:
        print('Error: fonttools not installed. Run: pip install fonttools brotli')
        return False

    args = [
        str(input_path),
        f'--output-file={output_path}',
        '--no-hinting',  # Remove hinting for smaller size
        '--desubroutinize',  # Better compression for small subsets
    ]

    if unicodes:
        args.append(f'--unicodes={",".join(unicodes)}')
    elif text:
        args.append(f'--text={text}')
    else:
        print('Error: Must specify either unicodes or text')
        return False

    try:
        subset_main(args)
        return True
    except Exception as e:
        print(f'Error subsetting font: {e}')
        return False


def format_size(size_bytes: int) -> str:
    """Format byte size as human-readable string."""
    if size_bytes >= 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.2f} MB'
    elif size_bytes >= 1024:
        return f'{size_bytes / 1024:.1f} KB'
    return f'{size_bytes} bytes'


def main():
    print('=' * 60)
    print('Font Subsetting for kivy-reloader')
    print('=' * 60)

    # Check if fonttools is installed
    try:
        import fontTools  # noqa: F401
    except ImportError:
        print('\nError: fonttools is not installed.')
        print('Install it with: pip install fonttools brotli')
        sys.exit(1)

    # Step 1: Find used icons
    print('\n📍 Scanning codebase for used icons...')
    used_icon_names = extract_used_icon_names(CONFIGURATOR_DIR)
    print(f'   Found {len(used_icon_names)} unique MDI icons:')
    for name in sorted(used_icon_names):
        print(f'      - {name}')

    # Step 2: Find used emojis
    print('\n📍 Scanning codebase for used emojis...')
    used_emojis = extract_used_emojis(CONFIGURATOR_DIR)
    print(f'   Found {len(used_emojis)} unique emoji characters:')
    print(f'      {"".join(sorted(used_emojis))}')

    # Step 3: Get unicode values for icons
    print('\n📍 Resolving icon unicode values...')
    icon_unicodes = get_icon_unicodes_from_module(used_icon_names)
    print(f'   Resolved {len(icon_unicodes)} icon unicodes')

    # Step 4: Subset MDI font
    print('\n📍 Creating MDI subset font...')
    mdi_input = ASSETS_DIR / 'materialdesignicons.ttf'
    mdi_output = ASSETS_DIR / 'mdi-subset.ttf'

    if not mdi_input.exists():
        print(f'   Error: {mdi_input} not found')
    else:
        original_size = mdi_input.stat().st_size
        if subset_font(mdi_input, mdi_output, unicodes=list(icon_unicodes.values())):
            new_size = mdi_output.stat().st_size
            reduction = (1 - new_size / original_size) * 100
            print(f'   ✅ Created: {mdi_output.name}')
            print(
                f'      {format_size(original_size)} → {format_size(new_size)} ({reduction:.1f}% reduction)'
            )
        else:
            print('   ❌ Failed to create MDI subset')

    # Step 5: Subset Twemoji font
    print('\n📍 Creating Twemoji subset font...')
    emoji_input = ASSETS_DIR / 'twemoji-mozilla.ttf'
    emoji_output = ASSETS_DIR / 'twemoji-subset.ttf'

    if not emoji_input.exists():
        print(f'   Error: {emoji_input} not found')
    else:
        original_size = emoji_input.stat().st_size
        emoji_text = ''.join(used_emojis)
        emoji_unicodes = emojis_to_unicode_ranges(used_emojis)

        if subset_font(emoji_input, emoji_output, unicodes=emoji_unicodes):
            new_size = emoji_output.stat().st_size
            reduction = (1 - new_size / original_size) * 100
            print(f'   ✅ Created: {emoji_output.name}')
            print(
                f'      {format_size(original_size)} → {format_size(new_size)} ({reduction:.1f}% reduction)'
            )
        else:
            print('   ❌ Failed to create Twemoji subset')

    # Summary
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)

    total_original = 0
    total_subset = 0

    for orig, sub in [
        (mdi_input, mdi_output),
        (emoji_input, emoji_output),
    ]:
        if orig.exists() and sub.exists():
            total_original += orig.stat().st_size
            total_subset += sub.stat().st_size

    if total_original > 0 and total_subset > 0:
        total_reduction = (1 - total_subset / total_original) * 100
        print(
            f'\nTotal font size: {format_size(total_original)} → {format_size(total_subset)}'
        )
        print(f'Total reduction: {total_reduction:.1f}%')
        print(f'\nSaved: {format_size(total_original - total_subset)}')

    print('\n✅ Done! Subset fonts created in:')
    print(f'   {ASSETS_DIR}')
    print('\nRemember to update icons.py to use the subset fonts.')


if __name__ == '__main__':
    main()
