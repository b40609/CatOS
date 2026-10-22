# -*- coding: utf-8 -*-
import pathlib
import shutil

SRC = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')
DST = pathlib.Path(r'C:\Users\user\Desktop\CatOS_Astra\frontend\workspace')

def sync_assets():
    if not DST.exists():
        DST.mkdir(parents=True, exist_ok=True)

    count = 0
    for item in SRC.rglob('*'):
        rel_path = item.relative_to(SRC)
        dest_path = DST / rel_path
        if item.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_path)
            count += 1

    print(f"Synchronized {count} files from {SRC} to {DST}.")

if __name__ == '__main__':
    sync_assets()
