import os
import sys
sys.path.append(os.path.abspath('backend'))
from data_engine import CVMDataEngine

engine = CVMDataEngine()

tests = [
    {'Taxa_Juros': 'CDI + 1,80% a.a.', 'Indexador': 'Should be CDI / DI'},
    {'Taxa_Juros': 'IPCA + 6,50% a.a.', 'Indexador': 'Should be IPCA / Inflação'},
    {'Taxa_Juros': 'SELIC + 0,20%', 'Indexador': 'Should be CDI / DI'},
    {'Taxa_Juros': 'IGP-M + 5,00%', 'Indexador': 'Should be IPCA / Inflação'},
    {'Taxa_Juros': '12,50% a.a.', 'Indexador': 'Should be PRÉ (Prefixado)'},
    {'Taxa_Juros': 'PRÉ-FIXADO 5%', 'Indexador': 'Should be PRÉ (Prefixado)'},
    {'Taxa_Juros': 'N/A', 'Indexador': 'Should preserve original'},
    {'Taxa_Juros': '', 'Indexador': 'Should preserve original'},
]

for t in tests:
    r = {'Taxa_Juros': t['Taxa_Juros'], 'Indexador': 'Original Value'}
    engine._sync_row_indexador(r)
    print(f"{t['Taxa_Juros']:<20} -> {r['Indexador']}")
