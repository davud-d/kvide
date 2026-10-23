# PyInstaller spec for the single-file kvide binary.
#
# Textual, Rich and the tree-sitter grammars load data files and submodules
# dynamically, so they are collected explicitly instead of relying on the
# import graph.

from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = collect_data_files("kvide", includes=["*.cjs"])
binaries = []
hiddenimports = []

for package in ("textual", "rich", "tree_sitter"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

GRAMMARS = (
    "python",
    "javascript",
    "json",
    "toml",
    "yaml",
    "html",
    "css",
    "rust",
    "go",
    "sql",
    "java",
    "bash",
    "xml",
    "markdown",
)

for grammar in GRAMMARS:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(f"tree_sitter_{grammar}")
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

analysis = Analysis(
    ["kvide_entry.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    name="kvide",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
