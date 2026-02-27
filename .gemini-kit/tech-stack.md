# Tech Stack Context: ArchCrafter2

## Core Technologies
- **Language:** Python 3.12+
- **Desktop Framework:** GTK 3.24 (via PyGObject)
- **UI Design:** GtkBuilder with Glade XML files
- **Styling:** Custom GTK CSS (GtkCssProvider)

## Key Libraries & Tools
- **Wallpaper Service:** `nitrogen` (for applying), `ImageMagick` (for colorizing/processing), `GdkPixbuf` (for thumbnails).
- **Theme Service:** `openbox` (specifically `openbox --reconfigure`), Python's `xml.etree` for `rc.xml` parsing.
- **Concurrency:** Standard `threading` and `GLib.idle_add` for async UI updates.
- **Persistence:** Custom JSON settings store in `backend/settings.py`.
