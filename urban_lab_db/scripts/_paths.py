"""Koreni putanja za sve skripte; nista nije vezano za jednu masinu.

DB_DIR      = folder urban_lab_db/ (ili promenljiva URBAN_LAB_DB_DIR)
SCRATCH_DIR = privremeni preuzeti arhivi (ili URBAN_LAB_SCRATCH); van gita
"""
import os
from pathlib import Path

DB_DIR = Path(os.environ.get("URBAN_LAB_DB_DIR") or Path(__file__).resolve().parent.parent)
REPO_DIR = DB_DIR.parent
SCRATCH_DIR = Path(os.environ.get("URBAN_LAB_SCRATCH") or REPO_DIR / ".scratch")


def rel(p):
    """Putanja za manifest: relativna na koren repozitorijuma, sa kosim crtama."""
    p = Path(p).resolve()
    try:
        return p.relative_to(REPO_DIR.resolve()).as_posix()
    except ValueError:
        return str(p)
