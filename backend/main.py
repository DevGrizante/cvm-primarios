from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
from collections import defaultdict
import csv
import io
import os
from data_engine import engine

app = FastAPI(title="CVM Primários Monitor PRO API", version="2.0.0")

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
    ano: str = Query("Recentes (2023-2026)"),
    rito: str = Query("Todos"),
    ativo: str = Query("Todos"),
    status: str = Query("Todos"),
    indexador: str = Query("Todos"),
    publico: str = Query("Todos"),
    regime: str = Query("Todos"),
    busca: str = Query("")
):
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    if not rows:
        return {
            "volume_total": 0.0,
            "qtd_ofertas": 0,
            "taxa_auto": 0.0,
            "ticket_medio": 0.0,
            "taxa_varejo": 0.0,
            "vol_pessoa_fisica": 0.0,
            "vol_fundos": 0.0,
            "vol_estrangeiro": 0.0
        }
    
    total_vol = sum(r["Volume_Float"] for r in rows)
    qtd = len(rows)
    auto_cnt = sum(1 for r in rows if "automático" in r["Rito"].lower())
    taxa_auto = (auto_cnt / qtd * 100.0) if qtd > 0 else 0.0
    ticket_medio = (total_vol / qtd) if qtd > 0 else 0.0
    
    vol_pf = sum(r["Vol_Pessoa_Fisica"] for r in rows)
    vol_fd = sum(r["Vol_Fundos"] for r in rows)
    vol_est = sum(r["Vol_Estrangeiro"] for r in rows)
    
    taxa_varejo = (vol_pf / total_vol * 100.0) if total_vol > 0 else 0.0
    
    return {
        "volume_total": total_vol,
        "qtd_ofertas": qtd,
        "taxa_auto": round(taxa_auto, 1),
        "ticket_medio": ticket_medio,
        "taxa_varejo": round(taxa_varejo, 2),
        "vol_pessoa_fisica": vol_pf,
        "vol_fundos": vol_fd,
        "vol_estrangeiro": vol_est
    }

@app.get("/api/charts/overview")
def get_charts_overview(
    ano: str = Query("Recentes (2023-2026)"),
    rito: str = Query("Todos"),
    ativo: str = Query("Todos"),
    status: str = Query("Todos"),
    indexador: str = Query("Todos"),
    publico: str = Query("Todos"),
    regime: str = Query("Todos"),
    busca: str = Query("")
):
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    temp_map = defaultdict(lambda: {"Automático": 0.0, "Ordinário": 0.0, "Total": 0.0})
    for r in rows:
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
    
    ativo_vol = defaultdict(float)
    ativo_cnt = defaultdict(int)
    for r in rows:
        a = r["Ativo"]
        if a and a != "Não Informado":
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
    
    return {
        "temporal": temporal_data,
        "top_ativos": top_ativos,
        "status_funnel": status_data
    }

@app.get("/api/charts/investors")
def get_charts_investors(
    ano: str = Query("Recentes (2023-2026)"),
    rito: str = Query("Todos"),
    ativo: str = Query("Todos"),
    status: str = Query("Todos"),
    indexador: str = Query("Todos"),
    publico: str = Query("Todos"),
    regime: str = Query("Todos"),
    busca: str = Query("")
):
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    vol_pf = sum(r["Vol_Pessoa_Fisica"] for r in rows)
    vol_fd = sum(r["Vol_Fundos"] for r in rows)
    vol_est = sum(r["Vol_Estrangeiro"] for r in rows)
    vol_prev = sum(r["Vol_Previdencia"] for r in rows)
    vol_seg = sum(r["Vol_Seguradoras"] for r in rows)
    vol_inst = sum(r["Vol_Instituicoes"] for r in rows)
    
    total_alloc = vol_pf + vol_fd + vol_est + vol_prev + vol_seg + vol_inst
    if total_alloc == 0:
        cnt_pf = sum(r["Qtd_Inv_Pessoa_Fisica"] for r in rows)
        cnt_fd = sum(r["Qtd_Inv_Fundos"] for r in rows)
        cnt_est = sum(r["Qtd_Inv_Estrangeiro"] for r in rows)
        return {
            "type": "count",
            "labels": ["Pessoa Física (Varejo)", "Fundos de Investimento", "Investidor Estrangeiro"],
            "values": [cnt_pf, cnt_fd, cnt_est]
        }
        
    return {
        "type": "volume",
        "labels": [
            "Fundos de Investimento",
            "Pessoa Física (Varejo)",
            "Investidor Estrangeiro",
            "Instituições & Intermediários",
            "Previdência Privada",
            "Companhias Seguradoras"
        ],
        "values": [
            round(vol_fd, 2),
            round(vol_pf, 2),
            round(vol_est, 2),
            round(vol_inst, 2),
            round(vol_prev, 2),
            round(vol_seg, 2)
        ]
    }

@app.get("/api/rankings")
def get_rankings(
    ano: str = Query("Recentes (2023-2026)"),
    rito: str = Query("Todos"),
    ativo: str = Query("Todos"),
    status: str = Query("Todos"),
    indexador: str = Query("Todos"),
    publico: str = Query("Todos"),
    regime: str = Query("Todos"),
    busca: str = Query(""),
    limit: int = Query(15)
):
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    lider_vol = defaultdict(float)
    lider_cnt = defaultdict(int)
    for r in rows:
        l = r["Lider"]
        if l and l != "Não Informado":
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
    ano: str = Query("Recentes (2023-2026)"),
    rito: str = Query("Todos"),
    ativo: str = Query("Todos"),
    status: str = Query("Todos"),
    indexador: str = Query("Todos"),
    publico: str = Query("Todos"),
    regime: str = Query("Todos"),
    busca: str = Query(""),
    page: int = Query(1),
    page_size: int = Query(50),
    sort_by: str = Query("Data_Clean"),
    sort_order: str = Query("desc")
):
    rows = engine.get_filtered_rows(ano, rito, ativo, status, indexador, publico, regime, busca)
    
    reverse = (sort_order == "desc")
    if sort_by == "Volume_Float":
        rows.sort(key=lambda x: x["Volume_Float"], reverse=reverse)
    elif sort_by == "Data_Clean":
        rows.sort(key=lambda x: x["Data_Clean"], reverse=reverse)
    elif sort_by == "Emissor":
        rows.sort(key=lambda x: x["Emissor"], reverse=reverse)
    
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = rows[start:end]
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
        "items": paginated
    }

@app.get("/api/export")
def export_offers(
    ano: str = Query("Recentes (2023-2026)"),
    rito: str = Query("Todos"),
    ativo: str = Query("Todos"),
    status: str = Query("Todos"),
    indexador: str = Query("Todos"),
    publico: str = Query("Todos"),
    regime: str = Query("Todos"),
    busca: str = Query("")
):
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

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
