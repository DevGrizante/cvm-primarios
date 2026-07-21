# -*- coding: utf-8 -*-
import os
import re

file_path = "backend/data_engine.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix Pagination in _fetch_recent_offers_realtime
old_fetch = """        payload = json.dumps({
            "periodoCriacaoProcesso": {
                "de": dt_ini,
                "ate": dt_fim
            },
            "opa": False,
            "tipoOferta": "OFERTA_REGULAR",
            "modalidade": "TODAS",
            "direcaoOrdenacao": "DESC",
            "colunaOrdenacao": "data",
            "pagina": 1,
            "tamanhoPagina": "1000"
        }).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        
        novas = []
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                dados = json.loads(res.read().decode('utf-8'))
                registros = dados.get('registros', [])
                
                for r in registros:"""

new_fetch = """        novas = []
        pagina = 1
        while True:
            payload = json.dumps({
                "periodoCriacaoProcesso": {
                    "de": dt_ini,
                    "ate": dt_fim
                },
                "opa": False,
                "tipoOferta": "OFERTA_REGULAR",
                "modalidade": "TODAS",
                "direcaoOrdenacao": "DESC",
                "colunaOrdenacao": "data",
                "pagina": pagina,
                "tamanhoPagina": "200"
            }).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=payload,
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            
            try:
                with urllib.request.urlopen(req, timeout=15) as res:
                    dados = json.loads(res.read().decode('utf-8'))
                    registros = dados.get('registros', [])
                    if not registros:
                        break
                    
                    for r in registros:"""

content = content.replace(old_fetch, new_fetch)

# 2. Add missing fields to row_dict
old_dict = """"Vencimento_Clean": "",
                        "Demografia_Detalhada": [],
                        "_ym": dt_clean[:7],
                        "_is_hist": False
                    }
                    novas.append(row_dict)
        except Exception as e:"""

new_dict = """"Vencimento_Clean": "",
                        "Demografia_Detalhada": [],
                        "Vol_Pessoa_Fisica": 0.0,
                        "Vol_Fundos": 0.0,
                        "Vol_Estrangeiro": 0.0,
                        "Vol_Previdencia": 0.0,
                        "Vol_Seguradoras": 0.0,
                        "Vol_Instituicoes": 0.0,
                        "_ym": dt_clean[:7],
                        "_is_hist": False
                    }
                    novas.append(row_dict)
                if len(registros) < 200:
                    break
                pagina += 1
        except Exception as e:"""

content = content.replace(old_dict, new_dict)

# 3. Update _fetch_api_sre to fetch participants
old_api = """                            return taxa_encontrada, campos_encontrados, venc_encontrado
                except Exception:
                    pass
                return None, [], None

            def _apply_row_update(r, taxa_e, campos_e, venc_e, req_id):"""

new_api = """                            
                            # Fetch participants to extract all coordinators
                            coordenadores = []
                            try:
                                part_url = f"https://web.cvm.gov.br/sre-publico-cvm/rest/sitePublico/pesquisar/participantes/{req_id}"
                                preq = urllib.request.Request(part_url, headers={'User-Agent': 'Mozilla/5.0'})
                                with urllib.request.urlopen(preq, context=ctx, timeout=2.0) as presp:
                                    if presp.status == 200:
                                        pdata = json.loads(presp.read().decode("utf-8"))
                                        for part in pdata:
                                            if part.get("tipo") == "COORDENADOR":
                                                coordenadores.append(part.get("razaoSocial", "").strip())
                            except Exception:
                                pass

                            return taxa_encontrada, campos_encontrados, venc_encontrado, coordenadores
                except Exception:
                    pass
                return None, [], None, []

            def _apply_row_update(r, taxa_e, campos_e, venc_e, coordenadores_e, req_id):"""

content = content.replace(old_api, new_api)

# 4. Update _apply_row_update to handle indexador rules and coordinators
old_apply = """            def _apply_row_update(r, taxa_e, campos_e, venc_e, req_id):
                updated = False
                if taxa_e or campos_e or venc_e:
                    if taxa_e:
                        r["Taxa_Juros"] = taxa_e
                        r["Taxa_Declarada"] = True
                        r["Remuneracao_API_CVM"] = taxa_e
                        updated = True
                    if campos_e:
                        r["Caracteristicas_CVM"] = campos_e
                    if venc_e:
                        r["Vencimento"] = venc_e
                        r["Vencimento_Clean"] = str(venc_e)[:10]
                        updated = True
                return updated"""

new_apply = """            def _apply_row_update(r, taxa_e, campos_e, venc_e, coordenadores_e, req_id):
                updated = False
                if taxa_e or campos_e or venc_e or coordenadores_e:
                    if taxa_e:
                        r["Taxa_Juros"] = taxa_e
                        r["Taxa_Declarada"] = True
                        r["Remuneracao_API_CVM"] = taxa_e
                        taxa_upper = taxa_e.upper()
                        if "IPCA" in taxa_upper or "NTNB" in taxa_upper or "NTN-B" in taxa_upper:
                            r["Indexador"] = "IPCA+"
                            r["Indexador_Tipo"] = "IPCA+"
                        elif "CDI" in taxa_upper or "DI" in taxa_upper:
                            r["Indexador"] = "CDI+"
                            r["Indexador_Tipo"] = "CDI+"
                        elif "PRÉ-FIXADA" in taxa_upper or "PREFIXADA" in taxa_upper or "PRE-FIXADA" in taxa_upper:
                            r["Indexador"] = "PRÉ"
                            r["Indexador_Tipo"] = "PRÉ"
                        else:
                            r["Indexador"] = "PRÉ"
                            r["Indexador_Tipo"] = "PRÉ"
                        updated = True
                    if campos_e:
                        r["Caracteristicas_CVM"] = campos_e
                    if venc_e:
                        r["Vencimento"] = venc_e
                        r["Vencimento_Clean"] = str(venc_e)[:10]
                        updated = True
                    if coordenadores_e:
                        # Convert to canonical names
                        norm_coords = []
                        for c in coordenadores_e:
                            norm = self._normalize_coordenador(c)
                            if norm and norm != "Nao Informado" and norm not in norm_coords:
                                norm_coords.append(norm)
                        if norm_coords:
                            r["Consorcio_List"] = norm_coords
                            r["Consorcio"] = " / ".join(norm_coords)
                            r["Lider"] = norm_coords[0]
                            consorcio_cache[req_id] = norm_coords
                            r["Coordenadores_Todos"] = norm_coords
                            updated = True
                return updated"""

content = content.replace(old_apply, new_apply)

# 5. Fix _fetch_api_sre call
old_call = """                taxa, campos, venc = _fetch_api_sre(req_id)
                if _apply_row_update(r, taxa, campos, venc, req_id):"""

new_call = """                taxa, campos, venc, coords = _fetch_api_sre(req_id)
                if _apply_row_update(r, taxa, campos, venc, coords, req_id):"""

content = content.replace(old_call, new_call)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched data_engine.py successfully.")
