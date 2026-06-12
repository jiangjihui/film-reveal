"""
Build FilmReveal.exe with PyInstaller.

Creates a clean virtual environment for the build, ensuring only the
application's actual dependencies (from requirements.txt) are included.
Unrelated global packages (torch, transformers, etc.) that may be
installed on the local machine are excluded automatically.

Gradio reads its own .py source files at runtime (via pathlib.read_text)
for .pyi stub generation. In PyInstaller --onefile mode, .py files are
compiled to bytecode in the PYZ archive, not available in the filesystem.
To fix this, the entire gradio/ package directory is added via --add-data,
which copies both .py source files and data files into the exe bundle.
"""

import shutil
import subprocess
import sys
from pathlib import Path


# Packages that need --collect-data for their data files only.
# gradio is handled separately via --add-data (see below).
COLLECT_DATA_PACKAGES = [
    'gradio_client',
    'safehttpx',
    'groovy',
]

# Packages whose entire directory is added via --add-data.
# This includes .py source files needed by Gradio's runtime
# .pyi generation (component_meta.create_or_modify_pyi).
ADD_DATA_PACKAGES = [
    'gradio',
    'gradio_imageslider',
]


def get_venv_bin(venv_dir, name):
    """Get executable path inside the venv (Windows: Scripts/, Linux: bin/)."""
    if sys.platform == 'win32':
        return venv_dir / 'Scripts' / (name + '.exe')
    return venv_dir / 'bin' / name


def main():
    print("=== FilmReveal PyInstaller Build ===\n")

    venv_dir = Path('_build_venv')

    # ── Step 1: Create clean venv ──
    print("Creating clean build environment...")
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run([sys.executable, '-m', 'venv', str(venv_dir)], check=True)

    venv_python = get_venv_bin(venv_dir, 'python')

    # ── Step 2: Install dependencies ──
    print("Installing dependencies in build environment...")
    subprocess.run(
        [str(venv_python), '-m', 'pip', 'install', '--upgrade', 'pip'],
        check=True,
    )
    subprocess.run(
        [str(venv_python), '-m', 'pip', 'install',
         '-r', 'requirements.txt', 'pyinstaller'],
        check=True,
    )

    # ── Step 3: Build PyInstaller flags ──
    site_packages = venv_dir / 'Lib' / 'site-packages'
    data_sep = ';' if sys.platform == 'win32' else ':'

    # --collect-data for packages that only need data files
    collect_flags = []
    for pkg in COLLECT_DATA_PACKAGES:
        collect_flags.extend(['--collect-data', pkg])

    # --add-data for packages that need .py source files available at runtime
    # (Gradio reads its own .py files via pathlib.read_text for .pyi generation)
    add_data_flags = []
    for pkg in ADD_DATA_PACKAGES:
        pkg_dir = site_packages / pkg
        if pkg_dir.exists():
            src = str(pkg_dir).replace('\\', '/')
            add_data_flags.extend(['--add-data', f'{src}{data_sep}{pkg}'])

    venv_pyinstaller = get_venv_bin(venv_dir, 'pyinstaller')

    cmd = [
        str(venv_pyinstaller),
        '--onefile',
        '--name', 'FilmReveal',
        '--noconfirm',
        '--paths', 'src',
    ] + collect_flags + add_data_flags + ['run.py']

    print(f"\nRunning PyInstaller from build environment...")
    print(f"  --collect-data: {len(collect_flags) // 2} packages")
    print(f"  --add-data: {len(add_data_flags) // 2} packages")
    result = subprocess.run(cmd, check=False)

    # ── Step 4: Report results ──
    if result.returncode != 0:
        print(f"\nPyInstaller failed with exit code {result.returncode}")
        print(f"Build environment preserved at: {venv_dir} (for debugging)")
        sys.exit(result.returncode)

    exe_path = Path('dist') / 'FilmReveal.exe'
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nBuild complete! Output: {exe_path} ({size_mb:.1f} MB)")
    else:
        print(f"\nBuild finished but {exe_path} not found")

    # ── Step 5: Clean up ──
    print("\nCleaning up build environment...")
    shutil.rmtree(venv_dir)
    shutil.rmtree('build', ignore_errors=True)
    for spec in Path('.').glob('FilmReveal.spec'):
        spec.unlink()
    print("Done!")


if __name__ == '__main__':
    main()