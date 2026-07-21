import urllib.request
import json

endpoints = [
    'pesquisar/requerimento',
    'pesquisar/requerimentos',
    'pesquisar',
    'pesquisar/oferta',
    'pesquisar/ofertas'
]
for e in endpoints:
    req = urllib.request.Request(
        f'https://web.cvm.gov.br/sre-publico-cvm/rest/sitePublico/{e}',
        data=json.dumps({"dataRegistroInicio": "2026-07-01", "dataRegistroFim": "2026-07-21"}).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req) as res:
            print(f"Success POST {e}:", res.read()[:100])
    except Exception as ex:
        print(f"Error POST {e}:", ex)
        
    req_get = urllib.request.Request(
        f'https://web.cvm.gov.br/sre-publico-cvm/rest/sitePublico/{e}?dataRegistroInicio=01/07/2026&dataRegistroFim=21/07/2026',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req_get) as res:
            print(f"Success GET {e}:", res.read()[:100])
    except Exception as ex:
        print(f"Error GET {e}:", ex)
