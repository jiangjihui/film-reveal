"""
PyInstaller runtime hook for Gradio.

In frozen mode (--onefile), .py source files are compiled to bytecode
and stored in the PYZ archive, NOT in the filesystem. Gradio's
component_meta.create_or_modify_pyi reads .py source files at runtime
to generate .pyi type hint stubs. When source files are missing, it
raises FileNotFoundError or ValueError, crashing the application.

This hook intercepts the import of gradio.component_meta and patches
create_or_modify_pyi to catch those errors and skip stub generation.
.pyi files are only needed for IDE type hints, not for runtime
functionality — skipping them is safe in production.
"""

import sys
import importlib

if getattr(sys, 'frozen', False):

    class _GradioPyiPatcher:
        """Import hook that patches gradio.component_meta on load."""

        def find_module(self, fullname, path=None):
            if fullname == 'gradio.component_meta':
                return self
            return None

        def load_module(self, fullname):
            if fullname in sys.modules:
                return sys.modules[fullname]

            # Remove ourselves temporarily to avoid recursion
            sys.meta_path.remove(self)
            try:
                module = importlib.import_module(fullname)
            finally:
                sys.meta_path.insert(0, self)

            # Patch create_or_modify_pyi to skip gracefully on errors
            original = module.create_or_modify_pyi

            def _patched_pyi(*args, **kwargs):
                try:
                    return original(*args, **kwargs)
                except (FileNotFoundError, ValueError):
                    # In PyInstaller mode, .py source files aren't in the
                    # filesystem (they're in the PYZ archive as bytecode).
                    # Skip .pyi generation — it's for IDE hints, not runtime.
                    return None

            module.create_or_modify_pyi = _patched_pyi
            sys.modules[fullname] = module
            return module

    sys.meta_path.insert(0, _GradioPyiPatcher())