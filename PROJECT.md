# ArchCrafter2 (Current Project)

Active files and folders:
- `Archcrafter2.glade` - GTK3 UI layout edited in Glade
- `main.py` - app bootstrap + sidebar/stack wiring + wallpaper page handlers
- `backend/settings.py` - JSON settings store
- `backend/wallpapers.py` - wallpaper backend (scan sources, persist modes, apply via nitrogen)
- `library/wallpapers/` - default custom wallpaper folder
- `settings.json` - runtime settings created by backend

Run:
```bash
python3 main.py
```
