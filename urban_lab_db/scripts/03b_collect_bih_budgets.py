from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import sys
import urllib.parse
from pathlib import Path
sys.path.insert(0, str(DB_DIR / "scripts"))
from common_net import RAW_DIR, fetch_url

targets = [
    ("sarajevo", "budget_ks_2026_pdf", "Budzet Kantona Sarajevo za 2026. godinu PDF",
     "https://mf.ks.gov.ba/sites/mf.ks.gov.ba/files/2026-01/budzet-kantona-sarajevo-za-2026-godinu_0.pdf",
     RAW_DIR / "sarajevo" / "budzet_ks_2026.pdf"),
    ("travnik", "budget_2026_pdf", "Budzet Opcine Travnik za 2026. godinu PDF",
     "https://opcinatravnik.com.ba/images/doc/budzet/" + urllib.parse.quote("Budžet_za_2026._godinu.pdf"),
     RAW_DIR / "travnik" / "travnik_budzet_2026.pdf"),
    ("travnik", "budget_rebalans_2026_pdf", "Rebalans Budzeta Opcine Travnik 2026 PDF",
     "https://opcinatravnik.com.ba/images/doc/2026/REBALANS_2026.pdf",
     RAW_DIR / "travnik" / "travnik_rebalans_2026.pdf"),
    ("travnik", "budget_exec_2025_xls", "Izvjestaj o izvrsenju budzeta Travnik 2025 XLS",
     "https://opcinatravnik.com.ba/images/doc/2026/Izvje%C5%A1taj_o_izvr%C5%A1enju_bud%C5%BEeta_za_period_01.01.-31.12.2025.xls",
     RAW_DIR / "travnik" / "travnik_izvrsenje_2025.xls"),
    ("travnik", "debt_2026_xlsx", "Podaci o dugu Opcine Travnik 30.06.2026 XLSX",
     "https://opcinatravnik.com.ba/images/doc/budzet/dug/Obrasci_za_objavu_podataka_o_dugu_30.06.2026.xlsx",
     RAW_DIR / "travnik" / "travnik_dug_2026.xlsx"),
]
for city, layer, name, url, dest in targets:
    r = fetch_url(url, dest=dest, city=city, layer=layer, source_name=name, timeout=90)
    print(f"[EXTRA] {city}/{layer}: ok={r['ok']} bytes={r.get('bytes')} err={r.get('error')}")
