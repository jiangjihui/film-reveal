"""
Build FilmReveal.exe with PyInstaller.

PyInstaller only auto-collects Python source files (.py).
Packages with data files (version.txt, templates, JS/CSS, etc.)
need explicit --collect-all flags.

This script auto-discovers packages with data files and generates
the appropriate flags, so new dependencies won't cause runtime crashes.
"""

import subprocess
import sys
from pathlib import Path


# Packages that are PyInstaller build tools, not application dependencies
SKIP_PACKAGES = {
    'pyinstaller', 'altgraph', 'pefile', 'pyinstaller_hooks_contrib',
    'macholib', 'setuptools', 'pip', 'wheel',
}


def discover_data_packages():
    """Discover installed packages that contain non-Python data files.

    Returns a list of package names (underscore-normalized for import).
    """
    import importlib.metadata

    data_packages = []

    for dist in importlib.metadata.distributions():
        name = dist.metadata.get('Name', '')
        if not name:
            continue

        # Normalize: pip uses hyphens, Python imports use underscores
        normalized = name.replace('-', '_')

        # Skip build tool packages
        if normalized.lower() in SKIP_PACKAGES:
            continue

        files = dist.files
        if not files:
            continue

        has_data = False
        for file_record in files:
            path = str(file_record)
            # Skip Python source/compiled files
            if path.endswith(('.py', '.pyc', '.pyd', '.pyo')):
                continue
            # Skip package metadata directories
            if '.dist-info/' in path or '.egg-info/' in path:
                continue
            # Skip RECORD file
            if path.endswith('/RECORD'):
                continue
            # This package has data files
            has_data = True
            break

        if has_data:
            data_packages.append(normalized)

    return sorted(data_packages)


def main():
    print("=== FilmReveal PyInstaller Build ===\n")

    # Discover packages with data files
    print("Discovering packages with data files...")
    data_packages = discover_data_packages()
    print(f"Found {len(data_packages)} packages with data files:")
    for pkg in data_packages:
        print(f"  - {pkg}")
    print()

    # Build --collect-all flags
    collect_flags = []
    for pkg in data_packages:
        collect_flags.extend(['--collect-all', pkg])

    # Full PyInstaller command
    cmd = [
        'pyinstaller',
        '--onefile',
        '--name', 'FilmReveal',
        '--noconfirm',
        '--paths', 'src',
    ] + collect_flags + ['run.py']

    print(f"Running PyInstaller with {len(collect_flags) // 2} --collect-all flags...")
    result = subprocess.run(cmd, check=False)

    if result.returncode != 0:
        print(f"\nPyInstaller failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    exe_path = Path('dist') / 'FilmReveal.exe'
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nBuild complete! Output: {exe_path} ({size_mb:.1f} MB)")
    else:
        print(f"\nBuild finished but {exe_path} not found")


if __name__ == '__main__':
    main()