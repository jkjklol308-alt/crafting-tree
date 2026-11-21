"""Import-check: stub out PySide6 and import every project module.

Catches: missing imports, wrong names, typos in class-level code.
Does NOT exercise GUI behaviour (no real Qt in this sandbox).
"""
import sys
import types

ROOT = '/home/user/crafting-tree'
sys.path.insert(0, ROOT)


class _Dummy:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return self
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def __getattr__(self, name): return _Dummy()
    def __iter__(self): return iter(())
    def __getitem__(self, k): return _Dummy()
    def __eq__(self, other): return False
    def __hash__(self): return 0
    def __ne__(self, other): return True
    def __ne__(self, other): return True
    def __bool__(self): return True
    def __gt__(self, other): return False
    def __lt__(self, other): return False


class _ModuleStub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith('__'): raise AttributeError(name)
        return _Dummy


def install_stub():
    qt = types.ModuleType('PySide6')
    qt.__path__ = []
    for sub in ['QtCore', 'QtGui', 'QtWidgets', 'QtPrintSupport', 'QtNetwork']:
        mod = _ModuleStub(f'PySide6.{sub}')
        mod.__path__ = []
        qt.__getattr__ = lambda name, s=sub: __import__(f'PySide6.{s}', fromlist=[name]).__getattr__(name) if name == s else _Dummy
        sys.modules[f'PySide6.{sub}'] = mod
        mod.__getattr__ = lambda name, s=sub: getattr(sys.modules[f'PySide6.{s}'], '__gen__', _Dummy) if False else _Dummy
        # make `QFont.Bold` etc work: return _Dummy
        def make_getattr(sub_name):
            def __getattr__(name):
                return _Dummy
            return __getattr__
        mod.__getattr__ = make_getattr(sub)
    qt.__getattr__ = lambda name: _Dummy
    sys.modules['PySide6'] = qt


install_stub()

MODULES = [
    'src.util', 'src.models', 'src.layout', 'src.db', 'src.calculator',
    'src.io_manager', 'src.theme', 'src.graph',
    'src.sidebar', 'src.info_panel', 'src.dialogs_common',
    'src.dialogs_items', 'src.dialogs_recipe', 'src.dialogs_meta',
    'src.calculator_ui', 'src.main_window',
]

failed = []
for mod in MODULES:
    try:
        module = __import__(mod, fromlist=['x'])
        print(f'OK   {mod}')
    except Exception as e:
        print(f'FAIL {mod}: {type(e).__name__}: {e}')
        failed.append(mod)

if failed:
    print('\nFAILED IMPORTS:', failed)
    sys.exit(1)
print('\nALL MODULE IMPORTS OK')
