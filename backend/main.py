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

is_prod = bool(os.getenv("RENDER"))
app = FastAPI(
    title="CVM Primários Monitor PRO API",
    version="2.0.0",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json"
)

from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1024)


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
    req_link_id = str(r.get("Numero_Requerimento", "")).strip() if str(r.get("Numero_Requerimento", "")).isdigit() else str(r.get("Id_Processo", "")).strip()
    if req_link_id and req_link_id.isdigit():
        r["Link_CVM_SRE"] = f"https://web.cvm.gov.br/app/sre-publico/#/oferta-publica/{req_link_id}"
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
            if time.time() - _SRE_NEGATIVE_CACHE[req_id] < 600:
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

            # Always recalculate NTN-B after any enrichment update
            if taxa_encontrada or campos_encontrados or venc_encontrado:
                ref, fonte = engine._extract_ntnb_reference(r)
                r["Referencia_NTNB"] = ref
                r["NTNB_Fonte"] = fonte
                engine._sync_row_indexador(r)
                engine.save_single_sre_cache(req_id, taxa_encontrada or r.get("Taxa_Juros"), r.get("Vencimento"), campos_encontrados or r.get("Caracteristicas_CVM"))
            else:
                engine._sync_row_indexador(r)
        else:
            with _SRE_LOCK:
                _SRE_NEGATIVE_CACHE[req_id] = time.time()
    except Exception:
        pass
        
    return r

# Enable strict CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cvm-primarios.onrender.com", "http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

from fastapi import Request
from fastapi.responses import JSONResponse

_IP_RATE_BUCKET = defaultdict(list)
_EXPORT_RATE_LIMIT = defaultdict(list)
_RESPONSE_CACHE = {}

def _get_cached_response(cache_key: str):
    if cache_key in _RESPONSE_CACHE:
        ts, payload = _RESPONSE_CACHE[cache_key]
        if time.time() - ts < 120:
            return payload
        else:
            del _RESPONSE_CACHE[cache_key]
    return None

def _put_cached_response(cache_key: str, payload):
    if len(_RESPONSE_CACHE) >= 200:
        oldest_key = min(_RESPONSE_CACHE.keys(), key=lambda k: _RESPONSE_CACHE[k][0])
        del _RESPONSE_CACHE[oldest_key]
    _RESPONSE_CACHE[cache_key] = (time.time(), payload)

@app.middleware("http")
async def rate_limit_and_timing_middleware(request: Request, call_next):
    start_time = time.time()
    ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    
    _IP_RATE_BUCKET[ip] = [t for t in _IP_RATE_BUCKET[ip] if now - t < 60]
    if len(_IP_RATE_BUCKET[ip]) >= 120:
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})
    _IP_RATE_BUCKET[ip].append(now)
    
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    if request.url.path.startswith("/api/"):
        print(f"[TIMING] {request.url.path} took {duration:.2f}ms")
        if request.url.path in ("/api/dashboard", "/api/offers", "/api/kpis", "/api/rankings") or request.url.path.startswith("/api/charts"):
            response.headers["Cache-Control"] = "private, max-age=30"
    return response

@app.on_event("startup")
def startup_event():
    print("[STARTUP] Binding port — data loading started in background thread...")
    import threading
    def _load_and_clear():
        engine.ensure_data()
        _RESPONSE_CACHE.clear()
    threading.Thread(target=_load_and_clear, daemon=True).start()


@app.get("/api/ready")
def get_ready():
    """Returns loading status so the frontend can show a loading screen."""
    is_ready = len(engine.rows) > 0
    return {
        "ready": is_ready,
        "rows_count": len(engine.rows),
        "last_update": engine.last_update,
        "message": "Dados carregados com sucesso." if is_ready else "Carregando dados CVM em background... Aguarde."
    }

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "rows_count": len(engine.rows),
        "last_update": engine.last_update,
        "options": engine.options_cache
    }

@app.get("/api/dashboard")
def get_dashboard(
    request: Request,
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    data_de: str = Query(""),
    data_ate: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false"),
    modo_coordenador: str = Query("lider")
):
    cache_key = f"/api/dashboard?{request.url.query}"
    cached = _get_cached_response(cache_key)
    if cached is not None:
        return cached

    ano_val = _val(ano); rito_val = _val(rito); ativo_val = _val(ativo); status_val = _val(status)
    indexador_val = _val(indexador); publico_val = _val(publico); regime_val = _val(regime); busca_val = _val(busca)
    data_de_val = _val(data_de); data_ate_val = _val(data_ate)
    
    rows = engine.get_filtered_rows(ano_val, rito_val, ativo_val, status_val, indexador_val, publico_val, regime_val, busca_val, data_de_val, data_ate_val)
    
    kpis_data = get_kpis(ano=ano, rito=rito, ativo=ativo, status=status, indexador=indexador, publico=publico, regime=regime, busca=busca, data_de=data_de, data_ate=data_ate, incluir_estimados=incluir_estimados, cached_rows=rows)
    overview_data = get_charts_overview(ano=ano, rito=rito, ativo=ativo, status=status, indexador=indexador, publico=publico, regime=regime, busca=busca, data_de=data_de, data_ate=data_ate, incluir_estimados=incluir_estimados, modo_coordenador=modo_coordenador, cached_rows=rows)
    investors_data = get_charts_investors(ano=ano, rito=rito, ativo=ativo, status=status, indexador=indexador, publico=publico, regime=regime, busca=busca, data_de=data_de, data_ate=data_ate, incluir_estimados=incluir_estimados, cached_rows=rows)
    rankings_data = get_rankings(ano=ano, rito=rito, ativo=ativo, status=status, indexador=indexador, publico=publico, regime=regime, busca=busca, data_de=data_de, data_ate=data_ate, limit=100, incluir_estimados=incluir_estimados, modo_coordenador=modo_coordenador, cached_rows=rows)
    
    payload = {
        "kpis": kpis_data,
        "charts_overview": overview_data,
        "investors": investors_data,
        "rankings": rankings_data
    }
    _put_cached_response(cache_key, payload)
    return payload

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
    data_de: str = Query(""),
    data_ate: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false"),
    cached_rows: Optional[List[dict]] = None
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    data_de = _val(data_de); data_ate = _val(data_ate)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    
    rows = cached_rows if cached_rows is not None else engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca, data_de, data_ate)
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
    data_de: str = Query(""),
    data_ate: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false"),
    cached_rows: Optional[List[dict]] = None
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    data_de = _val(data_de); data_ate = _val(data_ate)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    rows = cached_rows if cached_rows is not None else engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca, data_de, data_ate)
    
    if indexador != "Todos":
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
    
    year_map = defaultdict(lambda: {"CDI": 0.0, "IPCA": 0.0, "PRE": 0.0, "Outros": 0.0, "Total": 0.0})
    for r in rows:
        if not (r.get("Is_Estimated_Vol") and not inc_est):
            y = str(r.get("Ano", "")).strip()
            if len(y) == 4 and y.isdigit() and int(y) >= 2010:
                idx_type = r.get("Indexador", "")
                vol = r["Volume_Float"]
                if idx_type == "CDI / DI": year_map[y]["CDI"] += vol
                elif idx_type == "IPCA / Inflação": year_map[y]["IPCA"] += vol
                elif idx_type == "PRÉ (Prefixado)": year_map[y]["PRE"] += vol
                else: year_map[y]["Outros"] += vol
                year_map[y]["Total"] += vol
                
    sorted_y_keys = sorted(year_map.keys())
    cum_vol = 0.0
    cum_list = []
    for y in sorted_y_keys:
        cum_vol += year_map[y]["Total"]
        cum_list.append(round(cum_vol, 2))
        
    yearly_indexer = {
        "labels": sorted_y_keys,
        "cdi": [round(year_map[y]["CDI"], 2) for y in sorted_y_keys],
        "ipca": [round(year_map[y]["IPCA"], 2) for y in sorted_y_keys],
        "pre": [round(year_map[y]["PRE"], 2) for y in sorted_y_keys],
        "outros": [round(year_map[y]["Outros"], 2) for y in sorted_y_keys],
        "cumulativo": cum_list
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
        if modo_coordenador == "todos":
            coords = []
            if r.get("Coordenadores_Todos") and isinstance(r.get("Coordenadores_Todos"), dict) and r["Coordenadores_Todos"].get("coordenadores"):
                for c in r["Coordenadores_Todos"]["coordenadores"]:
                    nm = str(c.get("nome", "")).strip()
                    if nm: coords.append(nm)
            if not coords:
                coords = r.get("Consorcio_List") or [r.get("Lider", "Não Informado")]
            if not isinstance(coords, list):
                coords = [coords]
        else:
            coords = [r.get("Lider", "Não Informado")]
            
        for l in coords:
            if l and l != "Não Informado":
                if not (r.get("Is_Estimated_Vol") and not inc_est):
                    lider_vol[l] += r["Volume_Float"]
                lider_cnt[l] += 1
    top_lideres_list = sorted(lider_vol.items(), key=lambda x: x[1], reverse=True)[:100]
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
    top_emiss_list = sorted(emissor_vol.items(), key=lambda x: x[1], reverse=True)[:100]
    top_emissores = {
        "labels": [k for k, v in top_emiss_list],
        "volumes": [round(v, 2) for k, v in top_emiss_list],
        "counts": [emissor_cnt[k] for k, v in top_emiss_list]
    }
    
    # 4. Vencimento X Spread (scatter/bubble)
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
            if not v_year or not v_year.isdigit() or int(v_year) < 2000 or int(v_year) > 2060:
                continue
            
            idx_lbl = str(r.get("Indexador", ""))
            if any(k in idx_lbl.upper() for k in ("PRÉ", "PRE ", "PREFIX")):
                continue
            
            val_float = None
            m = re.search(r'[\+\s\(](\d+[\d,.]*)\s*%', t) or re.search(r'(\d+[\d,.]*)\s*%', t) or re.search(r'(\d+[\d,.]*)\s*(?:aa|a\.a\.)', t, re.I)
            if m:
                try:
                    val_float = float(m.group(1).replace(",", "."))
                except Exception:
                    pass
            if val_float is not None and 0.01 <= val_float <= 30.0:
                point = {
                    "x": int(v_year),
                    "y": round(val_float, 2),
                    "r": round(min(max((r["Volume_Float"] / 1e6) ** 0.5 / 3, 3), 16), 1),
                    "vencimento": v,
                    "emissor": r["Emissor"],
                    "taxa": t,
                    "indexador": idx_lbl,
                    "volume": r["Volume_Float"],
                    "id": r.get("Id_Processo", ""),
                    "instrumento": r.get("Ativo", ""),
                    "coordenador": r.get("Lider", ""),
                    "is_estimated": bool(r.get("Is_Estimated_Vol"))
                }
                venc_points.append(point)
                if any(k in idx_lbl.upper() for k in ("CDI", " DI")):
                    venc_map_cdi[v_year].append(val_float)
                elif any(k in idx_lbl.upper() for k in ("IPCA", "INFLA", "INPC", "IGP-M")):
                    venc_map_ipca[v_year].append(val_float)
                    
    # Sort by volume descending, keep top 500 points
    venc_points.sort(key=lambda p: p["volume"], reverse=True)
    venc_points = venc_points[:500]
    
    # Separate points by indexer for frontend datasets
    cdi_points = [p for p in venc_points if any(k in p["indexador"].upper() for k in ("CDI", " DI"))]
    ipca_points = [p for p in venc_points if any(k in p["indexador"].upper() for k in ("IPCA", "INFLA", "INPC", "IGP-M"))]
    
    def _median(lst):
        if not lst:
            return None
        s = sorted(lst)
        n = len(s)
        if n % 2 == 1:
            return round(s[n // 2], 2)
        return round((s[n // 2 - 1] + s[n // 2]) / 2, 2)
    
    all_years = sorted(set(list(venc_map_cdi.keys()) + list(venc_map_ipca.keys())))
    
    vencimento_spread = {
        "labels": all_years,
        "cdi_median": [_median(venc_map_cdi[y]) for y in all_years],
        "ipca_median": [_median(venc_map_ipca[y]) for y in all_years],
        "cdi_points": cdi_points,
        "ipca_points": ipca_points
    }
    
    # 5. Volume emitido indexado em cada B (NTN-B)
    ntnb_vol_declarada = defaultdict(float)
    ntnb_vol_aproximada = defaultdict(float)
    ntnb_cnt_declarada = defaultdict(int)
    ntnb_cnt_aproximada = defaultdict(int)
    total_ipca_vol = 0.0
    for r in rows:
        idx_val = str(r.get("Indexador", "")).upper()
        if any(k in idx_val for k in ("IPCA", "INFLA", "INPC", "IGP-M")) and not (r.get("Is_Estimated_Vol") and not inc_est):
            vol = r["Volume_Float"]
            total_ipca_vol += vol
            ref = str(r.get("Referencia_NTNB", "Outras / Não Espec.")).strip()
            fonte = str(r.get("NTNB_Fonte", "nenhuma")).strip()
            if not ref or ref == "N/I" or not ref.startswith("NTN-B"):
                ref = "Outras / Não Espec."
                fonte = "nenhuma"
            if fonte == "declarada":
                ntnb_vol_declarada[ref] += vol
                ntnb_cnt_declarada[ref] += 1
            elif fonte == "aproximada":
                ntnb_vol_aproximada[ref] += vol
                ntnb_cnt_aproximada[ref] += 1
            else:
                ntnb_vol_declarada["Outras / Não Espec."] += vol
                ntnb_cnt_declarada["Outras / Não Espec."] += 1
    
    all_ntnb_keys = set(list(ntnb_vol_declarada.keys()) + list(ntnb_vol_aproximada.keys()))
    ntnb_sorted_keys = sorted(
        [k for k in all_ntnb_keys if k != "Outras / Não Espec."],
        key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 9999
    )
    outras_vol = ntnb_vol_declarada.get("Outras / Não Espec.", 0) + ntnb_vol_aproximada.get("Outras / Não Espec.", 0)
    if outras_vol > 0:
        ntnb_sorted_keys.append("Outras / Não Espec.")
    
    classificado_vol = sum(ntnb_vol_declarada.get(k, 0) + ntnb_vol_aproximada.get(k, 0) for k in ntnb_sorted_keys if k != "Outras / Não Espec.")
    cobertura = round((classificado_vol / total_ipca_vol * 100), 1) if total_ipca_vol > 0 else 0.0
    
    ntnb_volume = {
        "labels": ntnb_sorted_keys,
        "vol_declarada": [round(ntnb_vol_declarada.get(k, 0), 2) for k in ntnb_sorted_keys],
        "vol_aproximada": [round(ntnb_vol_aproximada.get(k, 0), 2) for k in ntnb_sorted_keys],
        "cnt_declarada": [ntnb_cnt_declarada.get(k, 0) for k in ntnb_sorted_keys],
        "cnt_aproximada": [ntnb_cnt_aproximada.get(k, 0) for k in ntnb_sorted_keys],
        "cobertura": cobertura
    }
    
    return {
        "temporal": temporal_data,
        "monthly_indexer": monthly_indexer,
        "monthly_volume": monthly_volume,
        "yearly_indexer": yearly_indexer,
        "top_coordenadores": top_coordenadores,
        "top_emissores": top_emissores,
        "vencimento_spread": vencimento_spread,
        "ntnb_volume": ntnb_volume
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
    data_de: str = Query(""),
    data_ate: str = Query(""),
    incluir_estimados: Union[str, bool] = Query("false"),
    cached_rows: Optional[List[dict]] = None
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    data_de = _val(data_de); data_ate = _val(data_ate)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    rows = cached_rows if cached_rows is not None else engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca, data_de, data_ate)
    
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
        cnt_inst = sum(r.get("Qtd_Inv_Instituicoes", 0) for r in valid_rows)
        cnt_prev = sum(r.get("Qtd_Inv_Previdencia", 0) for r in valid_rows)
        cnt_seg = sum(r.get("Qtd_Inv_Seguradoras", 0) for r in valid_rows)
        lbls = [
            "Fundos de Investimento",
            "Pessoa Física (Varejo)",
            "Investidor Estrangeiro",
            "Instituições & Intermediários",
            "Previdência Privada",
            "Companhias Seguradoras"
        ]
        vals = [cnt_fd, cnt_pf, cnt_est, cnt_inst, cnt_prev, cnt_seg]
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
    data_de: str = Query(""),
    data_ate: str = Query(""),
    limit: int = Query(100),
    incluir_estimados: Union[str, bool] = Query("false"),
    modo_coordenador: str = Query("lider"),
    cached_rows: Optional[List[dict]] = None
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca); limit = _val(limit)
    data_de = _val(data_de); data_ate = _val(data_ate)
    inc_est = str(_val(incluir_estimados)).lower() in ("true", "1", "sim", "yes")
    rows = cached_rows if cached_rows is not None else engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca, data_de, data_ate)
    
    lider_vol = defaultdict(float)
    lider_cnt = defaultdict(int)
    for r in rows:
        if modo_coordenador == "todos":
            coords = []
            if r.get("Coordenadores_Todos") and isinstance(r.get("Coordenadores_Todos"), dict) and r["Coordenadores_Todos"].get("coordenadores"):
                for c in r["Coordenadores_Todos"]["coordenadores"]:
                    nm = str(c.get("nome", "")).strip()
                    if nm: coords.append(nm)
            if not coords:
                coords = r.get("Consorcio_List") or [r.get("Lider", "Não Informado")]
            if not isinstance(coords, list):
                coords = [coords]
        else:
            coords = [r.get("Lider", "Não Informado")]
            
        for l in coords:
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
    data_de: str = Query(""),
    data_ate: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("Data_Clean"),
    sort_order: str = Query("desc")
):
    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    data_de = _val(data_de); data_ate = _val(data_ate)
    page = _val(page); page_size = _val(page_size); sort_by = _val(sort_by); sort_order = _val(sort_order)
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca, data_de, data_ate)
    
    reverse = (sort_order == "desc")
    if sort_by == "Volume_Float":
        rows.sort(key=lambda x: x["Volume_Float"], reverse=reverse)
    elif sort_by == "Data_Clean":
        rows.sort(key=lambda x: x["Data_Clean"], reverse=reverse)
    elif sort_by == "Emissor":
        rows.sort(key=lambda x: x["Emissor"], reverse=reverse)
    elif sort_by == "Status":
        rows.sort(key=lambda x: x["Status"], reverse=reverse)
    
    start = (page - 1) * page_size
    
    if indexador != "Todos":
        rows = [x for x in rows if _match_idx(x["Indexador"], indexador)]
        
    total = len(rows)
    end = start + page_size
    paginated = rows[start:end]
    
    candidates = [
        r for r in paginated
        if (not r.get("Taxa_Juros") or r.get("Taxa_Juros") in ("N/I", "(Ver Dossiê / API CVM)", "-", "") or not r.get("Vencimento") or r.get("Vencimento") in ("N/I", "-", ""))
        and (r.get("Numero_Requerimento") or r.get("Id_Processo"))
    ]
    if candidates:
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda x: _enrich_offer_from_api(x, timeout=3.5), candidates[:12]))
            
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
        r_dt = str(r.get("Data_Clean", ""))[:7]
        r_ano = str(r.get("Ano", "")).strip()
        if (len(r_dt) >= 7 and r_dt[:4].isdigit() and r_dt < "2023-01") or (r_ano.isdigit() and r_ano < "2023"):
            continue
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
    
    candidates = [
        r for r in paginated
        if (not r.get("Taxa_Juros") or r.get("Taxa_Juros") in ("N/I", "(Ver Dossiê / API CVM)", "-", "") or not r.get("Vencimento") or r.get("Vencimento") in ("N/I", "-", ""))
        and (r.get("Numero_Requerimento") or r.get("Id_Processo"))
    ]
    if candidates:
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda x: _enrich_offer_from_api(x, timeout=3.5), candidates[:12]))
            
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
    request: Request,
    ano: Union[List[str], str] = Query("Recentes (2023-2026)"),
    rito: Union[List[str], str] = Query("Todos"),
    ativo: Union[List[str], str] = Query("Todos"),
    status: Union[List[str], str] = Query("Todos"),
    indexador: Union[List[str], str] = Query("Todos"),
    publico: Union[List[str], str] = Query("Todos"),
    regime: Union[List[str], str] = Query("Todos"),
    busca: str = Query(""),
    data_de: str = Query(""),
    data_ate: str = Query("")
):
    ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    _EXPORT_RATE_LIMIT[ip] = [t for t in _EXPORT_RATE_LIMIT[ip] if now - t < 60]
    if len(_EXPORT_RATE_LIMIT[ip]) >= 3:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Maximum 3 exports per minute per IP."})
    _EXPORT_RATE_LIMIT[ip].append(now)

    ano = _val(ano); rito = _val(rito); ativo = _val(ativo); status = _val(status)
    indexador = _val(indexador); publico = _val(publico); regime = _val(regime); busca = _val(busca)
    data_de = _val(data_de); data_ate = _val(data_ate)
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca, data_de, data_ate)
    
    output = io.StringIO()
    if len(rows) > 20000:
        output.write("# AVISO: Exportacao truncada no limite de 20.000 registros para protecao da infraestrutura e memoria.\r\n")
        rows = rows[:20000]
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
