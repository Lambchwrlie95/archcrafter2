import ast

class MethodExtractor(ast.NodeVisitor):
    def __init__(self, methods_to_extract):
        self.methods = methods_to_extract
        self.extracted = {}

    def visit_FunctionDef(self, node):
        if node.name in self.methods:
            self.extracted[node.name] = node
        self.generic_visit(node)

def extract_methods(filepath, methods):
    with open(filepath, "r") as f:
        source = f.read()
    
    tree = ast.parse(source)
    extractor = MethodExtractor(methods)
    extractor.visit(tree)
    
    for name, node in extractor.extracted.items():
        start = node.lineno - 1
        end = node.end_lineno
        lines = source.split('\n')[start:end]
        print(f"--- {name} ---")
        print('\n'.join(lines))

import sys
extract_methods("main.py", [
    "init_wallpaper_page", 
    "reload_wallpapers", 
    "sync_wallpaper_controls_from_settings",
    "on_wallpaper_system_source_toggled",
    "on_wallpaper_folder_set",
    "on_wallpaper_fill_mode_changed",
    "on_wallpaper_sort_changed",
    "on_wallpaper_search_changed",
    "on_wallpaper_zoom_scale_changed",
    "on_wallpaper_view_mode_changed"
])
