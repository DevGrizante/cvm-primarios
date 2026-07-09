from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List, Union
from collections import defaultdict
import csv
import io
import os
import sys
import requests
import re
from concurrent.futures import ThreadPoolExecutor
import threading
import time
_CUR_DIR = os.path.dirname(os.path.abspath(__file__))
if _CUR_DIR not in sys.path:
    sys.path.insert(0, _CUR_DIR)
try:
    from data_engine import engine
except ModuleNotFoundError:
    from backend.data_engine import engine

app = FastAPI(title="CVM Primários Monitor PRO API", version="2.0.0")

def _val(x):
    v = x.default if hasattr(x, "default") else x
    if isinstance(v, (list, tuple, set)):
        if not v:
            return "Todos"
        cleaned = [str(i).strip() for i in v if str(i).strip()]
        if not cleaned or any(i == "Todos" or i.startswith("Todos os") for i in cleaned):
            return "Todos"
        return cleaned if len(cleaned) > 1 else cleaned[0]
    if v and isinstance(v, str):
        s = v.strip()
        if s == "Todos" or s.startswith("Todos os"):
            return "Todos"
    return v

def _match_idx(row_idx, filter_idx):
    if filter_idx == "Todos" or not filter_idx:
        return True
    if isinstance(filter_idx, str):
        items = [i.strip() for i in filter_idx.split(",") if i.strip()]
        if not items or any(i == "Todos" for i in items):
            return True
        return any(row_idx == i or i.lower() in str(row_idx).lower() for i in items)
    if isinstance(filter_idx, (list, tuple, set)):
        items = []
        for v in filter_idx:
            items.extend([i.strip() for i in str(v).split(",") if i.strip()])
        if not items or any(i == "Todos" for i in items):
            return True
        return any(row_idx == i or str(i).lower() in str(row_idx).lower() for i in items)
    return row_idx == filter_idx or str(filter_idx).lower() in str(row_idx).lower()

_SRE_LOCK = threading.Lock()
_SRE_NEGATIVE_CACHE = {}

def _enrich_offer_from_api(r: dict, timeout: float = 1.4):
    if not isinstance(r, dict):
        return r
    if r.get("Taxa_Declarada") and r.get("Caracteristicas_CVM") and r.get("Vencimento") != "N/I":
        return r
        
    req_id = None
    if str(r.get("Numero_Requerimento", "")).isdigit():
        req_id = str(r.get("Numero_Requerimento", "")).strip()
    elif str(r.get("Id_Processo", "")).isdigit():
        req_id = str(r.get("Id_Processo", "")).strip()
        
    if not req_id:
        return r
        
    with _SRE_LOCK:
        if req_id in _SRE_NEGATIVE_CACHE:
            if time.time() - _SRE_NEGATIVE_CACHE[req_id] < 14400:
                return r
            else:
                del _SRE_NEGATIVE_CACHE[req_id]
        
    try:
        api_url = f"https://web.cvm.gov.br/sre-publico-cvm/rest/sitePublico/pesquisar/requerimento/{req_id}"
        resp = requests.get(api_url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            taxa_encontrada = None
            campos_encontrados = []
            venc_encontrado = None
            
            if data.get("grupos"):
                for g in data["grupos"]:
                    for s in g.get("series", []):
                        for lote_key in ("loteFinal", "loteInicial"):
                            lote = s.get(lote_key)
                            if lote and isinstance(lote, dict):
                                if not campos_encontrados and lote.get("camposCadastrados"):
                                    campos_encontrados = lote["camposCadastrados"]
                                
                                t = lote.get("taxaRemuneracao", "")
                                if t and str(t).strip() and str(t).strip() not in ("-", "--", "Não Informado", "0", "0%"):
                                    taxa_encontrada = str(t).strip()
                                
                                if lote.get("camposCadastrados"):
                                    for c in lote["camposCadastrados"]:
                                        nm = str(c.get("campoNome", "")).lower()
                                        val = str(c.get("campoValor", "")).strip()
                                        if not taxa_encontrada and any(k in nm for k in ("remuneração final", "remuneração máxima", "taxa de remuneração", "juros")):
                                            if val and val not in ("-", "--", "Não Informado", "0", "0%"):
                                                taxa_encontrada = val
                                        if not venc_encontrado and ("venc" in nm or "data de vencimento" in nm):
                                            if val and val not in ("-", "--", "00/00/0000", "Não Informado"):
                                                venc_encontrado = val
                        if taxa_encontrada and campos_encontrados and venc_encontrado: break
                    if taxa_encontrada and campos_encontrados and venc_encontrado: break
            
            with _SRE_LOCK:
                if taxa_encontrada:
                    r["Taxa_Juros"] = taxa_encontrada
                    r["Taxa_Declarada"] = True
                    r["Remuneracao_API_CVM"] = taxa_encontrada
                if campos_encontrados:
                    r["Caracteristicas_CVM"] = campos_encontrados
                if venc_encontrado:
                    if len(venc_encontrado) >= 10 and venc_encontrado[2] == "/":
                        parts = venc_encontrado.split("/")
                        r["Vencimento"] = f"{parts[1]}/{parts[2][-2:]}"
                    elif len(venc_encontrado) >= 10 and venc_encontrado[4] == "-":
                        parts = venc_encontrado.split("-")
                        r["Vencimento"] = f"{parts[1]}/{parts[0][-2:]}"
                    elif len(venc_encontrado) >= 7 and venc_encontrado[2] == "/":
                        r["Vencimento"] = f"{venc_encontrado[:2]}/{venc_encontrado[-2:]}"
                    else:
                        r["Vencimento"] = venc_encontrado[:7]
                
                if not taxa_encontrada and not campos_encontrados and not venc_encontrado:
                    _SRE_NEGATIVE_CACHE[req_id] = time.time()
                elif r.get("Taxa_Juros"):
                    t_upper = str(r["Taxa_Juros"]).upper()
                    if any(k in t_upper for k in ("CDI", " DI ", " DI+", " DI-", "% DI", "SELIC", "FLUTUANTE", "DI %")):
                        r["Indexador"] = "CDI / DI"
                        if r.get("Taxa_Declarada") or not any(w in t_upper for w in ("VER DOSSIÊ", "A DEFINIR", "NÃO INFORMADO")):
                            r["Indexador_Inferido"] = False
                    elif any(k in t_upper for k in ("IPCA", "INPC", "IGP-M", "IGPM", "TR ")):
                        r["Indexador"] = "IPCA / Inflação"
                        if r.get("Taxa_Declarada") or not any(w in t_upper for w in ("VER DOSSIÊ", "A DEFINIR", "NÃO INFORMADO")):
                            r["Indexador_Inferido"] = False
                    elif any(k in t_upper for k in ("PRÉ", "PRE ", "PREFIX")) or re.match(r'^\d+[\d,.]*\s*%', str(r["Taxa_Juros"])):
                        r["Indexador"] = "PRÉ (Prefixado)"
                        if r.get("Taxa_Declarada") or not any(w in t_upper for w in ("VER DOSSIÊ", "A DEFINIR", "NÃO INFORMADO")):
                            r["Indexador_Inferido"] = False
                            
                    r["Referencia_NTNB"] = engine._extract_ntnb_reference(r)
        else:
            with _SRE_LOCK:
                _SRE_NEGATIVE_CACHE[req_id] = time.time()
    except Exception:
        with _SRE_LOCK:
            _SRE_NEGATIVE_CACHE[req_id] = time.time()
        
    return r

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    print("Initializing CVM Data Engine...")
    engine.ensure_data()

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "rows_count": len(engine.rows),
        "last_update": engine.last_update,
        "options": engine.options_cache
    }

@app.get("/api/kpis")
def get_kpis(
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    if not rows:
        return {
            "volume_total": 0.0,
            "volume_estimado": 0.0,
            "qtd_ofertas": 0,
            "taxa_auto": 0.0,
            "ticket_medio": 0.0,
            "taxa_varejo": 0.0,
            "vol_pessoa_fisica": 0.0,
            "vol_fundos": 0.0,
            "vol_estrangeiro": 0.0
        }
    
    vol_confirmado = sum(r["Volume_Float"] for r in rows if not r.get("Is_Estimated_Vol") and r["Volume_Float"] > 0)
    vol_estimado = sum(r["Volume_Float"] for r in rows if r.get("Is_Estimated_Vol"))
    
    total_vol = (vol_confirmado + vol_estimado) if inc_est else vol_confirmado
    qtd = len(rows)
    auto_cnt = sum(1 for r in rows if "automático" in r["Rito"].lower())
    taxa_auto = (auto_cnt / qtd * 100.0) if qtd > 0 else 0.0
    ticket_medio = (total_vol / qtd) if qtd > 0 else 0.0
    
    vol_pf = sum(r["Vol_Pessoa_Fisica"] for r in rows if not (r.get("Is_Estimated_Vol") and not inc_est))
    vol_fd = sum(r["Vol_Fundos"] for r in rows if not (r.get("Is_Estimated_Vol") and not inc_est))
    vol_est = sum(r["Vol_Estrangeiro"] for r in rows if not (r.get("Is_Estimated_Vol") and not inc_est))
    
    taxa_varejo = (vol_pf / vol_confirmado * 100.0) if vol_confirmado > 0 else ((vol_pf / total_vol * 100.0) if total_vol > 0 else 0.0)
    
    bookbuilding_rows = [r for r in rows if r.get("Alocacao_Pendente") or "a definir" in str(r.get("Taxa_Juros")).lower() or "bookbuilding" in str(r.get("Taxa_Juros")).lower()]
    vol_bookbuilding = sum(r["Volume_Float"] for r in bookbuilding_rows if not (r.get("Is_Estimated_Vol") and not inc_est))
    qtd_bookbuilding = len(bookbuilding_rows)
    
    vol_cdi = sum(r["Volume_Float"] for r in rows if r["Indexador"] == "CDI / DI" and not (r.get("Is_Estimated_Vol") and not inc_est))
    vol_ipca = sum(r["Volume_Float"] for r in rows if r["Indexador"] == "IPCA / Inflação" and not (r.get("Is_Estimated_Vol") and not inc_est))
    vol_pre = sum(r["Volume_Float"] for r in rows if r["Indexador"] == "PRÉ (Prefixado)" and not (r.get("Is_Estimated_Vol") and not inc_est))
    share_cdi = (vol_cdi / total_vol * 100.0) if total_vol > 0 else 0.0
    share_ipca = (vol_ipca / total_vol * 100.0) if total_vol > 0 else 0.0
    share_pre = (vol_pre / total_vol * 100.0) if total_vol > 0 else 0.0
    
    return {
        "volume_total": total_vol,
        "volume_confirmado": vol_confirmado,
        "volume_estimado": vol_estimado,
        "qtd_ofertas": qtd,
        "taxa_auto": round(taxa_auto, 1),
        "ticket_medio": ticket_medio,
        "taxa_varejo": round(taxa_varejo, 2),
        "vol_pessoa_fisica": vol_pf,
        "vol_fundos": vol_fd,
        "vol_estrangeiro": vol_est,
        "vol_confirmado": vol_confirmado,
        "vol_bookbuilding": vol_bookbuilding,
        "qtd_bookbuilding": qtd_bookbuilding,
        "share_cdi": round(share_cdi, 1),
        "share_ipca": round(share_ipca, 1),
        "share_pre": round(share_pre, 1)
    }

@app.get("/api/charts/overview")
def get_charts_overview(
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    # If specific indexador is filtered, enrich top candidate offers concurrently so NTN-B references and real spreads/maturities are precise
    if indexador != "Todos":
        candidates_charts = [x for x in rows[:10] if not x.get("Taxa_Declarada") and (x.get("Numero_Requerimento") or x.get("Id_Processo"))]
        if candidates_charts:
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda item: _enrich_offer_from_api(item, timeout=1.2), candidates_charts))
        rows = [x for x in rows if _match_idx(x["Indexador"], indexador)]
        
    temp_map = defaultdict(lambda: {"Automático": 0.0, "Ordinário": 0.0, "Total": 0.0})
    for r in rows:
        if not (r.get("Is_Estimated_Vol") and not inc_est):
            y = r["Ano"]
            vol = r["Volume_Float"]
            if "automático" in r["Rito"].lower():
                temp_map[y]["Automático"] += vol
            else:
                temp_map[y]["Ordinário"] += vol
            temp_map[y]["Total"] += vol
        
    sorted_years = sorted(temp_map.keys())
    temporal_data = {
        "labels": sorted_years,
        "automatico": [round(temp_map[y]["Automático"], 2) for y in sorted_years],
        "ordinario": [round(temp_map[y]["Ordinário"], 2) for y in sorted_years],
        "total": [round(temp_map[y]["Total"], 2) for y in sorted_years]
    }
    
    month_names = {"01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr", "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago", "09": "Set", "10": "Out", "11": "Nov", "12": "Dez"}
    month_map = defaultdict(lambda: {"CDI": 0.0, "IPCA": 0.0, "PRE": 0.0})
    for r in rows:
        if not (r.get("Is_Estimated_Vol") and not inc_est):
            dt = str(r.get("Data_Clean", ""))
            if len(dt) >= 7 and dt[:4].isdigit() and dt[4] == "-":
                ym = dt[:7]
                if dt[:4] in ("2024", "2025", "2026"):
                    idx_type = r.get("Indexador", "")
                    if idx_type == "CDI / DI": month_map[ym]["CDI"] += r["Volume_Float"]
                    elif idx_type == "IPCA / Inflação": month_map[ym]["IPCA"] += r["Volume_Float"]
                    elif idx_type == "PRÉ (Prefixado)": month_map[ym]["PRE"] += r["Volume_Float"]
                
    sorted_months = sorted(month_map.keys())
    m_labels = [f"{month_names.get(ym[5:7], ym[5:7])}/{ym[2:4]}" for ym in sorted_months]
    monthly_indexer = {
        "labels": m_labels,
        "cdi": [round(month_map[ym]["CDI"], 2) for ym in sorted_months],
        "ipca": [round(month_map[ym]["IPCA"], 2) for ym in sorted_months],
        "pre": [round(month_map[ym]["PRE"], 2) for ym in sorted_months]
    }
    
    ativo_vol = defaultdict(float)
    ativo_cnt = defaultdict(int)
    for r in rows:
        a = r["Ativo"]
        if a and a != "Não Informado":
            if not (r.get("Is_Estimated_Vol") and not inc_est):
                ativo_vol[a] += r["Volume_Float"]
            ativo_cnt[a] += 1
            
    top_ativos_list = sorted(ativo_vol.items(), key=lambda x: x[1], reverse=True)[:10]
    top_ativos = {
        "labels": [k for k, v in top_ativos_list],
        "volumes": [round(v, 2) for k, v in top_ativos_list],
        "counts": [ativo_cnt[k] for k, v in top_ativos_list]
    }
    
    status_map = defaultdict(int)
    for r in rows:
        s = r["Status"]
        if s and s != "Não Informado":
            status_map[s] += 1
    top_status = sorted(status_map.items(), key=lambda x: x[1], reverse=True)[:8]
    status_data = {
        "labels": [k for k, v in top_status],
        "counts": [v for k, v in top_status]
    }
    
    # 1. Histórico de volume de emissão mês a mês
    monthly_volume = {
        "labels": m_labels,
        "volumes": [round(month_map[ym]["CDI"] + month_map[ym]["IPCA"] + month_map[ym]["PRE"], 2) for ym in sorted_months],
        "cdi": [round(month_map[ym]["CDI"], 2) for ym in sorted_months],
        "ipca": [round(month_map[ym]["IPCA"], 2) for ym in sorted_months],
        "pre": [round(month_map[ym]["PRE"], 2) for ym in sorted_months]
    }
    
    # 2. Coordenadores com mais envolvimento em emissão por volume (gráfico de barras)
    lider_vol = defaultdict(float)
    lider_cnt = defaultdict(int)
    for r in rows:
        l = r["Lider"]
        if l and l != "Não Informado":
            if not (r.get("Is_Estimated_Vol") and not inc_est):
                lider_vol[l] += r["Volume_Float"]
            lider_cnt[l] += 1
    top_lideres_list = sorted(lider_vol.items(), key=lambda x: x[1], reverse=True)[:12]
    top_coordenadores = {
        "labels": [k for k, v in top_lideres_list],
        "volumes": [round(v, 2) for k, v in top_lideres_list],
        "counts": [lider_cnt[k] for k, v in top_lideres_list]
    }
    
    # 3. Volume emitido por emissor (gráfico de barras)
    emissor_vol = defaultdict(float)
    emissor_cnt = defaultdict(int)
    for r in rows:
        e = r["Emissor"]
        if e and e != "Não Informado":
            if not (r.get("Is_Estimated_Vol") and not inc_est):
                emissor_vol[e] += r["Volume_Float"]
            emissor_cnt[e] += 1
    top_emiss_list = sorted(emissor_vol.items(), key=lambda x: x[1], reverse=True)[:12]
    top_emissores = {
        "labels": [k for k, v in top_emiss_list],
        "volumes": [round(v, 2) for k, v in top_emiss_list],
        "counts": [emissor_cnt[k] for k, v in top_emiss_list]
    }
    
    # 4. Vencimento X Spread
    venc_map_cdi = defaultdict(list)
    venc_map_ipca = defaultdict(list)
    venc_points = []
    for r in rows:
        v = str(r.get("Vencimento", "")).strip()
        t = str(r.get("Taxa_Juros", "")).strip()
        if v and v != "N/I" and t and "DEFINIR" not in t.upper() and "DOSSIÊ" not in t.upper():
            v_year = ""
            if len(v) >= 5 and "/" in v:
                v_year = "20" + v.split("/")[-1][-2:] if v.split("/")[-1].isdigit() else ""
            elif len(v) == 4 and v.isdigit():
                v_year = v
            if not v_year or not v_year.isdigit() or int(v_year) < 2024 or int(v_year) > 2060:
                continue
            
            # Extract numeric rate/spread
            val_float = None
            m = re.search(r'[\+\s](\d+[\d,.]*)\s*%', t) or re.search(r'^(\d+[\d,.]*)\s*%', t)
            if m:
                try:
                    val_float = float(m.group(1).replace(",", "."))
                except Exception:
                    pass
            if val_float is not None and 0.01 <= val_float <= 30.0:
                idx_lbl = r.get("Indexador", "")
                venc_points.append({
                    "x": f"{v_year}",
                    "vencimento": v,
                    "y": round(val_float, 2),
                    "emissor": r["Emissor"],
                    "taxa": t,
                    "indexador": idx_lbl,
                    "volume": r["Volume_Float"]
                })
                if idx_lbl == "CDI / DI":
                    venc_map_cdi[v_year].append(val_float)
                elif idx_lbl == "IPCA / Inflação":
                    venc_map_ipca[v_year].append(val_float)
                    
    sorted_v_years = sorted(list(set(list(venc_map_cdi.keys()) + list(venc_map_ipca.keys()))))[:12]
    vencimento_spread = {
        "labels": sorted_v_years,
        "cdi_spread": [round(sum(venc_map_cdi[y])/len(venc_map_cdi[y]), 2) if venc_map_cdi[y] else 0.0 for y in sorted_v_years],
        "ipca_spread": [round(sum(venc_map_ipca[y])/len(venc_map_ipca[y]), 2) if venc_map_ipca[y] else 0.0 for y in sorted_v_years],
        "points": venc_points[:150]
    }
    
    # 5. Volume emitido indexado em cada B (NTN-B)
    ntnb_vol = defaultdict(float)
    ntnb_cnt = defaultdict(int)
    for r in rows:
        if r.get("Indexador") == "IPCA / Inflação" and not (r.get("Is_Estimated_Vol") and not inc_est):
            ref = str(r.get("Referencia_NTNB", "Outras / Não Espec.")).strip()
            if not ref or ref == "N/I" or not ref.startswith("NTN-B"):
                ref = "Outras / Não Espec."
            ntnb_vol[ref] += r["Volume_Float"]
            ntnb_cnt[ref] += 1
            
    ntnb_sorted_keys = sorted([k for k in ntnb_vol.keys() if k != "Outras / Não Espec."], key=lambda x: x.split()[-1] if x.split()[-1].isdigit() else "9999")
    if "Outras / Não Espec." in ntnb_vol and ntnb_vol["Outras / Não Espec."] > 0:
        ntnb_sorted_keys.append("Outras / Não Espec.")
        
    ntnb_volume = {
        "labels": ntnb_sorted_keys,
        "volumes": [round(ntnb_vol[k], 2) for k in ntnb_sorted_keys],
        "counts": [ntnb_cnt[k] for k in ntnb_sorted_keys]
    }
    
    return {
        "temporal": temporal_data,
        "monthly_indexer": monthly_indexer,
        "monthly_volume": monthly_volume,
        "top_ativos": top_ativos,
        "top_coordenadores": top_coordenadores,
        "top_emissores": top_emissores,
        "vencimento_spread": vencimento_spread,
        "ntnb_volume": ntnb_volume,
        "status_funnel": status_data
    }

@app.get("/api/charts/investors")
def get_charts_investors(
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    valid_rows = [r for r in rows if not (r.get("Is_Estimated_Vol") and not inc_est)]
    vol_pf = sum(r["Vol_Pessoa_Fisica"] for r in valid_rows)
    vol_fd = sum(r["Vol_Fundos"] for r in valid_rows)
    vol_est = sum(r["Vol_Estrangeiro"] for r in valid_rows)
    vol_prev = sum(r["Vol_Previdencia"] for r in valid_rows)
    vol_seg = sum(r["Vol_Seguradoras"] for r in valid_rows)
    vol_inst = sum(r["Vol_Instituicoes"] for r in valid_rows)
    
    total_alloc = vol_pf + vol_fd + vol_est + vol_prev + vol_seg + vol_inst
    if total_alloc == 0:
        cnt_pf = sum(r["Qtd_Inv_Pessoa_Fisica"] for r in valid_rows)
        cnt_fd = sum(r["Qtd_Inv_Fundos"] for r in valid_rows)
        cnt_est = sum(r["Qtd_Inv_Estrangeiro"] for r in valid_rows)
        lbls = ["Pessoa Física (Varejo)", "Fundos de Investimento", "Investidor Estrangeiro"]
        vals = [cnt_pf, cnt_fd, cnt_est]
        return {
            "type": "count",
            "labels": lbls,
            "values": vals,
            "demographics": {"labels": lbls, "values": vals}
        }
        
    lbls = [
        "Fundos de Investimento",
        "Pessoa Física (Varejo)",
        "Investidor Estrangeiro",
        "Instituições & Intermediários",
        "Previdência Privada",
        "Companhias Seguradoras"
    ]
    vals = [
        round(vol_fd, 2),
        round(vol_pf, 2),
        round(vol_est, 2),
        round(vol_inst, 2),
        round(vol_prev, 2),
        round(vol_seg, 2)
    ]
    return {
        "type": "volume",
        "labels": lbls,
        "values": vals,
        "demographics": {"labels": lbls, "values": vals}
    }

@app.get("/api/rankings")
def get_rankings(
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    limit: int = Query(15),
    incluir_estimados: Union[str, bool] = Query("false")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca); limit = _val(limit)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    lider_vol = defaultdict(float)
    lider_cnt = defaultdict(int)
    for r in rows:
        l = r["Lider"]
        if l and l != "Não Informado":
            if not (r.get("Is_Estimated_Vol") and not inc_est):
                lider_vol[l] += r["Volume_Float"]
            lider_cnt[l] += 1
            
    top_lideres = sorted(lider_vol.items(), key=lambda x: x[1], reverse=True)[:limit]
    lideres_data = [
        {"nome": k, "volume": round(v, 2), "qtd": lider_cnt[k]} for k, v in top_lideres
    ]
    
    emissor_vol = defaultdict(float)
    emissor_cnt = defaultdict(int)
    for r in rows:
        e = r["Emissor"]
        if e and e != "Não Informado":
            if not (r.get("Is_Estimated_Vol") and not inc_est):
                emissor_vol[e] += r["Volume_Float"]
            emissor_cnt[e] += 1
            
    top_emissores = sorted(emissor_vol.items(), key=lambda x: x[1], reverse=True)[:limit]
    emissores_data = [
        {"nome": k, "volume": round(v, 2), "qtd": emissor_cnt[k]} for k, v in top_emissores
    ]
    
    return {
        "top_lideres": lideres_data,
        "top_emissores": emissores_data
    }

@app.get("/api/offers")
def get_offers(
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    page: int = Query(1),
    page_size: int = Query(50),
    sort_by: str = Query("Data_Clean"),
    sort_order: str = Query("desc")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    page = _val(page); page_size = _val(page_size); sort_by = _val(sort_by); sort_order = _val(sort_order)
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    reverse = (sort_order == "desc")
    if sort_by == "Volume_Float":
        rows.sort(key=lambda x: x["Volume_Float"], reverse=reverse)
    elif sort_by == "Data_Clean":
        rows.sort(key=lambda x: x["Data_Clean"], reverse=reverse)
    elif sort_by == "Emissor":
        rows.sort(key=lambda x: x["Emissor"], reverse=reverse)
    
    start = (page - 1) * page_size
    
    # If indexador filter is active, enrich top candidate pool first before slicing
    if indexador != "Todos":
        candidate_enrich = [x for x in rows[start:start + page_size + 5] if not x.get("Taxa_Declarada") and (x.get("Numero_Requerimento") or x.get("Id_Processo"))][:10]
        if candidate_enrich:
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda item: _enrich_offer_from_api(item, timeout=1.2), candidate_enrich))
        rows = [x for x in rows if _match_idx(x["Indexador"], indexador)]
        
    total = len(rows)
    end = start + page_size
    paginated = rows[start:end]
    
    # Live concurrent enrichment of the current page rows from official CVM SRE API (do not refilter paginated or change total after slicing)
    items_to_enrich = [x for x in paginated if not x.get("Taxa_Declarada") and (x.get("Numero_Requerimento") or x.get("Id_Processo"))][:12]
    if items_to_enrich:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda item: _enrich_offer_from_api(item, timeout=1.2), items_to_enrich))
            
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
        "items": paginated
    }

@app.get("/api/search")
def get_search(
    q: str = Query(""),
    type: str = Query("todos"),
    limit: int = Query(20),
    page: int = Query(1)
):
    q_val = _val(q)
    type_val = _val(type)
    limit_val = _val(limit)
    page_val = _val(page)
    q_lower = str(q_val).lower().strip() if q_val else ""
    if not q_lower:
        return {"total": 0, "page": page_val, "limit": limit_val, "items": []}
    
    results = []
    for r in engine.rows:
        t_lower = str(type_val).lower()
        match = False
        if t_lower in ("emissor", "todos"):
            if q_lower in r["Emissor"].lower(): match = True
        if not match and t_lower in ("coordenador", "lider", "todos"):
            if q_lower in r["Lider"].lower(): match = True
        if not match and t_lower == "todos":
            if q_lower in r["Id_Processo"].lower() or q_lower in r["Ativo"].lower() or q_lower in r["Status"].lower():
                match = True
        if match:
            results.append(r)
            
    total = len(results)
    start = (page_val - 1) * limit_val
    paginated = results[start:start + limit_val]
    return {
        "total": total,
        "page": page_val,
        "limit": limit_val,
        "items": paginated
    }

@app.get("/api/offers/{id_processo:path}")
def get_offer_detail(id_processo: str):
    clean_id = id_processo.strip()
    for r in engine.rows:
        if str(r.get("Id_Processo")).strip() == clean_id or str(r.get("Numero_Requerimento")).strip() == clean_id:
            return _enrich_offer_from_api(r)
    raise HTTPException(status_code=404, detail="Oferta não encontrada no banco de dados CVM.")

@app.get("/api/export")
def export_offers(
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query("")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    headers = [
        "Id_Processo", "Regime", "Ano", "Data", "Rito", "Status", "Valor_Mobiliario", "Indexador",
        "Tipo_Oferta", "Emissor", "Coordenador_Lider", "Publico_Alvo", "ESG",
        "Volume_Registrado", "Qtde_Registrada", "Vol_Pessoa_Fisica", "Vol_Fundos",
        "Vol_Estrangeiro", "Administrador", "Gestor", "Custodiante", "Processo_SEI"
    ]
    writer.writerow(headers)
    for r in rows:
        writer.writerow([
            r["Id_Processo"], r["Regime"], r["Ano"], r["Data_Clean"], r["Rito"], r["Status"], r["Ativo"], r["Indexador"],
            r["Tipo_Oferta_Clean"], r["Emissor"], r["Lider"], r["Publico_Alvo"], r["ESG"],
            f"{r['Volume_Float']:.2f}", f"{r['Qtde_Float']:.2f}", f"{r['Vol_Pessoa_Fisica']:.2f}",
            f"{r['Vol_Fundos']:.2f}", f"{r['Vol_Estrangeiro']:.2f}", r["Administrador"], r["Gestor"], r["Custodiante"], r["Processo_SEI"]
        ])
    
    csv_data = output.getvalue().encode("latin-1", errors="replace")
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cvm_ofertas_primarias_export.csv"}
    )

frontend_dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dist_dir):
    app.mount("/", StaticFiles(directory=frontend_dist_dir, html=True), name="frontend")
elif os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
