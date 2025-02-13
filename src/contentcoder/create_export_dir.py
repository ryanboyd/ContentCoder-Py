import os
from pathlib import Path as plpath

def create_export_dir(export_path: str) -> None:

    export_path_pathlib = plpath(export_path)

    if not os.path.exists(export_path_pathlib.parent):
        os.makedirs(export_path_pathlib.parent)