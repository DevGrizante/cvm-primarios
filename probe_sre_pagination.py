import json
import urllib.request
import traceback

def probe():
    url = "https://web.cvm.gov.br/sre-publico-cvm/oferta-publica/filtro-pesquisa"
    
    pagina = 1
    total_found = 0
    while True:
        payload = json.dumps({
            "filtros": {"de": "2026-07-01", "ate": "2026-07-21"},
            "opa": False,
            "tipoOferta": "OFERTA_REGULAR",
            "modalidade": "TODAS",
            "direcaoOrdenacao": "DESC",
            "colunaOrdenacao": "data",
            "pagina": pagina,
            "tamanhoPagina": "200"
        }).encode('utf-8')

        req = urllib.request.Request(
            url, data=payload,
            headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        
        try:
            print(f"Buscando pagina {pagina}...")
            with urllib.request.urlopen(req, timeout=15) as res:
                dados = json.loads(res.read().decode('utf-8'))
                registros = dados.get('registros', [])
                if not registros:
                    print("Nenhum registro retornado nesta pagina.")
                    break
                print(f"Pagina {pagina} retornou {len(registros)} registros.")
                total_found += len(registros)
                if len(registros) < 200:
                    break
                pagina += 1
        except Exception as e:
            print(f"Erro na pagina {pagina}: {e}")
            break
            
    print(f"Total encontrado: {total_found}")

if __name__ == '__main__':
    probe()
