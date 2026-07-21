
/**
 * Motor de dados local (Data Engine)
 * Replicando exatamente a lógica do backend Python.
 */

function toList(val) {
    if (!val || val === "Todos" || val === "") return ["Todos"];
    if (Array.isArray(val)) {
        if (val.length === 0) return ["Todos"];
        const flat = val.flatMap(v => String(v).split(',').map(s => s.trim()).filter(Boolean));
        if (flat.length === 0 || flat.some(i => i === "Todos" || i.startsWith("Todos os"))) return ["Todos"];
        return flat;
    }
    const items = String(val).split(',').map(s => s.trim()).filter(Boolean);
    if (items.length === 0 || items.some(i => i === "Todos" || i.startsWith("Todos os"))) return ["Todos"];
    return items;
}

export function filtrar(rows, filtros) {
    const anoList = toList(filtros.ano || "Recentes (2023-2026)");
    const ritoList = toList(filtros.rito);
    const ativoList = toList(filtros.ativo);
    const statusList = toList(filtros.status);
    const idxList = toList(filtros.indexador);
    const pubList = toList(filtros.publico);
    const regList = toList(filtros.regime);
    const buscaLower = (filtros.busca || "").toLowerCase().trim();
    const dataDe = (filtros.data_de || "").trim();
    const dataAte = (filtros.data_ate || "").trim();
    const incEst = filtros.incluir_estimados !== false && filtros.incluir_estimados !== "false";

    const hasDateRange = (dataDe && dataDe !== "Todos") || (dataAte && dataAte !== "Todos");
    let deStr = (dataDe && dataDe !== "Todos") ? dataDe.substring(0, 7) : "";
    if (deStr && deStr < "2023-01") deStr = "2023-01";
    const ateStr = (dataAte && dataAte !== "Todos") ? dataAte.substring(0, 7) : "";

    return rows.filter(r => {
        const r_dt = (r.data || "").substring(0, 7);
        const r_ano = String(r.ano || "").trim();

        if (r_dt.length >= 7 && /^\d{4}/.test(r_dt)) {
            if (r_dt < "2023-01") return false;
        } else if (/^\d{4}$/.test(r_ano) && r_ano < "2023") {
            return false;
        }

        if (!regList.includes("Todos")) {
            let match = false;
            for (let reg of regList) {
                const regLower = reg.toLowerCase();
                const rRegLower = (r.regime || "").toLowerCase();
                if (reg === "160" && r.regime.includes("160")) { match = true; break; }
                if (reg === "hist" && r.regime.includes("ICVM")) { match = true; break; }
                if (rRegLower.includes(regLower)) { match = true; break; }
            }
            if (!match) return false;
        }

        if (hasDateRange) {
            if (r_dt.length >= 7 && /^\d{4}/.test(r_dt)) {
                if (r_dt < "2023-01") return false;
                if (deStr && r_dt < deStr) return false;
                if (ateStr && r_dt > ateStr) return false;
            } else {
                return false;
            }
        } else if (!anoList.includes("Todos")) {
            let match = false;
            for (let a of anoList) {
                if (a === "Recentes (2023-2026)" && ["2023", "2024", "2025", "2026"].includes(r.ano)) { match = true; break; }
                if (String(r.ano) === String(a)) { match = true; break; }
            }
            if (!match) return false;
        }

        if (!ritoList.includes("Todos")) {
            const rRito = (r.rito || "").toLowerCase();
            if (!ritoList.some(rit => rRito.includes(rit.toLowerCase()))) return false;
        }

        if (!ativoList.includes("Todos")) {
            let match = false;
            const rAtUpper = (r.setor_ativo || "").toUpperCase();
            for (let at of ativoList) {
                const atUpper = String(at).toUpperCase();
                if (atUpper.includes("DEB") && rAtUpper.includes("DEB")) { match = true; break; }
                if ((atUpper.includes("CRI") || atUpper.includes("IMOBILI")) && (rAtUpper.includes("CRI") || rAtUpper.includes("IMOBILI"))) { match = true; break; }
                if ((atUpper.includes("CRA") || atUpper.includes("AGRONEG")) && (rAtUpper.includes("CRA") || rAtUpper.includes("AGRONEG"))) { match = true; break; }
                if ((atUpper.includes("FIDC") || atUpper.includes("CREDIT")) && (rAtUpper.includes("FIDC") || rAtUpper.includes("CREDIT"))) { match = true; break; }
                if ((atUpper.includes("CPR") || atUpper.includes("PRODUTO RURAL")) && (rAtUpper.includes("CPR") || rAtUpper.includes("PRODUTO RURAL"))) { match = true; break; }
                if ((atUpper.includes("NOTA COMERCIAL") || atUpper.includes("PROMISS") || atUpper === "NC") && (rAtUpper.includes("NOTA COMERCIAL") || rAtUpper.includes("PROMISS"))) { match = true; break; }
                if (r.setor_ativo === at || rAtUpper.includes(atUpper)) { match = true; break; }
            }
            if (!match) return false;
        }

        if (!statusList.includes("Todos")) {
            const rStatus = (r.status || "").toLowerCase();
            if (!statusList.some(st => rStatus.includes(st.toLowerCase()))) return false;
        }

        if (!idxList.includes("Todos")) {
            const rIdx = (r.indexador || "").toLowerCase();
            if (!idxList.some(ix => r.indexador === ix || rIdx.includes(ix.toLowerCase()))) return false;
        }

        if (!pubList.includes("Todos")) {
            const rPub = (r.publico || "").toLowerCase();
            if (!pubList.some(pb => rPub.includes(pb.toLowerCase()))) return false;
        }

        if (buscaLower) {
            const blob = `${r.emissor || ""} ${r.lider || ""} ${r.id || ""} ${r.setor_ativo || ""} ${r.status || ""}`.toLowerCase();
            if (!blob.includes(buscaLower)) return false;
        }

        if (!incEst && r.estimado) {
            return false;
        }

        return true;
    });
}

export function calcularKpis(rows) {
    let volConfirmado = 0, volEstimado = 0, countEstimado = 0;
    let countAuto = 0;
    let emAnalise = { vol: 0, count: 0 };
    let preOperacional = { vol: 0, count: 0 };
    let canceladas = { vol: 0, count: 0 };
    
    let vol160 = 0, count160 = 0;
    let vol400 = 0, count400 = 0;
    let vol476 = 0, count476 = 0;
    
    let volNtnb = 0, countNtnb = 0;
    let volCdi = 0, countCdi = 0;
    let volPre = 0, countPre = 0;
    
    let volPessoaFisica = 0;
    let volInstitucional = 0;
    let countComAlocacao = 0;

    for (const r of rows) {
        const v = parseFloat(r.volume || 0);
        if (isNaN(v) || v <= 0) continue;
        
        if (r.estimado) { volEstimado += v; countEstimado++; }
        else volConfirmado += v;
        
        const s = (r.status || "").toLowerCase();
        if (s.includes("análise") || s.includes("analise")) {
            emAnalise.vol += v;
            emAnalise.count++;
        } else if (s.includes("pré-operacional") || s.includes("pre-operacional") || s.includes("pre operacional")) {
            preOperacional.vol += v;
            preOperacional.count++;
        } else if (s.includes("cancelad") || s.includes("indeferid") || s.includes("desist")) {
            canceladas.vol += v;
            canceladas.count++;
        }
        
        const rg = (r.regime || "").toLowerCase();
        if (rg.includes("160")) { vol160 += v; count160++; }
        else if (rg.includes("400")) { vol400 += v; count400++; }
        else if (rg.includes("476")) { vol476 += v; count476++; }
        
        const rt = (r.rito || "").toLowerCase();
        if (rt.includes("auto")) { countAuto++; }

        const idx = (r.indexador || "").toLowerCase();
        if (idx.includes("ipca") || idx.includes("infla")) { volNtnb += v; countNtnb++; }
        else if (idx.includes("cdi") || idx.includes("di")) { volCdi += v; countCdi++; }
        else if (idx.includes("pré") || idx.includes("pre")) { volPre += v; countPre++; }
        
        if (!s.includes("análise") && !s.includes("cancel") && !s.includes("indeferid")) {
            const pf = parseFloat(r.vol_pf || 0);
            const fd = parseFloat(r.vol_fd || 0);
            const es = parseFloat(r.vol_est || 0);
            const pr = parseFloat(r.vol_prev || 0);
            const sg = parseFloat(r.vol_seg || 0);
            const is = parseFloat(r.vol_inst || 0);
            
            const totalInst = fd + es + pr + sg + is;
            if (pf > 0 || totalInst > 0) {
                volPessoaFisica += pf;
                volInstitucional += totalInst;
                countComAlocacao++;
            }
        }
    }

    const totalVol = volConfirmado + volEstimado;
    const totalIdx = volNtnb + volCdi + volPre;

    return {
        volume_total: totalVol,
        volume_estimado: volEstimado,
        qtd_ofertas: rows.length,
        share_cdi: totalIdx > 0 ? ((volCdi / totalIdx) * 100).toFixed(1) : 0,
        share_ipca: totalIdx > 0 ? ((volNtnb / totalIdx) * 100).toFixed(1) : 0,
        share_pre: totalIdx > 0 ? ((volPre / totalIdx) * 100).toFixed(1) : 0,
        vol_bookbuilding: volEstimado,
        qtd_bookbuilding: countEstimado,
        ticket_medio: rows.length > 0 ? totalVol / rows.length : 0,
        taxa_varejo: (volPessoaFisica + volInstitucional > 0) ? ((volPessoaFisica / (volPessoaFisica + volInstitucional)) * 100).toFixed(1) : 0,
        vol_confirmado: volConfirmado,
        taxa_auto: (rows.length > 0) ? ((countAuto / rows.length) * 100).toFixed(1) : 0,
        em_analise_volume: emAnalise.vol,
        em_analise_qtd: emAnalise.count,
        pre_operacional_volume: preOperacional.vol,
        pre_operacional_qtd: preOperacional.count,
        canceladas_volume: canceladas.vol,
        canceladas_qtd: canceladas.count,
        distribuicao_regime: {
            "Resolução 160": { volume: vol160, count: count160 },
            "ICVM 400": { volume: vol400, count: count400 },
            "ICVM 476": { volume: vol476, count: count476 }
        },
        indexadores: {
            "IPCA/NTN-B": { volume: volNtnb, count: countNtnb },
            "CDI/DI": { volume: volCdi, count: countCdi },
            "Pré-Fixado": { volume: volPre, count: countPre }
        },
        alocacao_varejo_inst: {
            "Varejo (PF)": { volume: volPessoaFisica, percentual: (volPessoaFisica + volInstitucional > 0) ? (volPessoaFisica / (volPessoaFisica + volInstitucional) * 100) : 0 },
            "Institucional": { volume: volInstitucional, percentual: (volPessoaFisica + volInstitucional > 0) ? (volInstitucional / (volPessoaFisica + volInstitucional) * 100) : 0 },
            "Total Alocado Analisado": volPessoaFisica + volInstitucional,
            "Emissões Analisadas": countComAlocacao
        }
    };
}

export function calcularChartsOverview(rows) {
    const lideres = {};
    const emissores = {};
    const monthlyVol = {};
    const monthlyIdx = {};
    const spreadCdi = {};
    const spreadIpca = {};
    const cdiPoints = [];
    const ipcaPoints = [];
    
    let totalIpca = 0;
    const ntnbDecl = {};
    const ntnbAprox = {};
    const ntnbCntDecl = {};
    const ntnbCntAprox = {};

    for (const r of rows) {
        const v = parseFloat(r.volume || 0);
        if (v <= 0) continue;

        // Lideres
        const l = r.lider || "Não Informado";
        if (!lideres[l]) lideres[l] = { v: 0, c: 0 };
        lideres[l].v += v; lideres[l].c += 1;

        // Emissores
        const e = r.emissor || "Não Informado";
        if (!emissores[e]) emissores[e] = { v: 0, c: 0 };
        emissores[e].v += v; emissores[e].c += 1;

        // Temporal / Monthly
        const dt = (r.data || "").substring(0, 7);
        if (dt && dt >= "2023-01") {
            const idx = r.indexador || "Não Informado (CVM)";
            if (!monthlyVol[dt]) monthlyVol[dt] = { volume: 0, count: 0 };
            monthlyVol[dt].volume += v;
            monthlyVol[dt].count += 1;
            
            if (!monthlyIdx[dt]) monthlyIdx[dt] = { CDI: 0, IPCA: 0, PRE: 0, OUTROS: 0 };
            const il = idx.toLowerCase();
            if (il.includes("cdi") || il.includes("di")) monthlyIdx[dt].CDI += v;
            else if (il.includes("ipca") || il.includes("infla") || il.includes("inpc")) monthlyIdx[dt].IPCA += v;
            else if (il.includes("pré") || il.includes("pre")) monthlyIdx[dt].PRE += v;
            else monthlyIdx[dt].OUTROS += v;
        }

        // Vencimento x Spread
        const isCdi = (r.indexador || "").toLowerCase().includes("cdi") || (r.indexador || "").toLowerCase().includes(" di");
        const isIpca = (r.indexador || "").toLowerCase().includes("ipca") || (r.indexador || "").toLowerCase().includes("infla");
        const t = String(r.taxa || "");
        const vencYearStr = r.vencimento ? r.vencimento.split("/").pop() : "";
        let vy = vencYearStr;
        if (vy.length === 2) vy = "20" + vy;
        
        if (vy.length === 4 && vy >= "2023" && vy <= "2060") {
            const match = t.match(/([0-9]+[.,][0-9]+)\s*\%?/);
            if (match) {
                const spread = parseFloat(match[1].replace(",", "."));
                if (spread > 0.01 && spread <= 30.0) {
                    const pt = { x: parseInt(vy), y: spread, r: Math.max(3, Math.min(16, Math.sqrt(v/1e6)/3)), tooltip: r.emissor, volume: v, is_estimated: r.estimado, emissor: r.emissor, taxa: t, indexador: r.indexador, id: r.id };
                    if (isCdi) {
                        if (!spreadCdi[vy]) spreadCdi[vy] = [];
                        spreadCdi[vy].push(spread);
                        cdiPoints.push(pt);
                    } else if (isIpca) {
                        if (!spreadIpca[vy]) spreadIpca[vy] = [];
                        spreadIpca[vy].push(spread);
                        ipcaPoints.push(pt);
                    }
                }
            }
        }

        // NTNB
        if (isIpca) {
            totalIpca += v;
            let ref = r.ntnb || "Outras / Não Espec.";
            const fonte = r.ntnb_fonte || "nenhuma";
            if (!ref.startsWith("NTN-B")) ref = "Outras / Não Espec.";
            
            if (fonte === "declarada") {
                ntnbDecl[ref] = (ntnbDecl[ref] || 0) + v;
                ntnbCntDecl[ref] = (ntnbCntDecl[ref] || 0) + 1;
            } else if (fonte === "aproximada") {
                ntnbAprox[ref] = (ntnbAprox[ref] || 0) + v;
                ntnbCntAprox[ref] = (ntnbCntAprox[ref] || 0) + 1;
            } else {
                ntnbDecl["Outras / Não Espec."] = (ntnbDecl["Outras / Não Espec."] || 0) + v;
                ntnbCntDecl["Outras / Não Espec."] = (ntnbCntDecl["Outras / Não Espec."] || 0) + 1;
            }
        }
    }

    const sortRanking = (obj) => Object.keys(obj).map(k => ({ label: k, v: obj[k].v, c: obj[k].c })).sort((a,b) => b.v - a.v);
    const topLideresList = sortRanking(lideres).slice(0, 100);
    const topEmissoresList = sortRanking(emissores).slice(0, 100);

    const median = (arr) => {
        if (!arr || !arr.length) return null;
        const s = [...arr].sort((a,b)=>a-b);
        const mid = Math.floor(s.length/2);
        return s.length % 2 !== 0 ? s[mid] : (s[mid-1]+s[mid])/2;
    };
    const allYears = Array.from(new Set([...Object.keys(spreadCdi), ...Object.keys(spreadIpca)])).sort();
    
    const allNtnbKeys = Array.from(new Set([...Object.keys(ntnbDecl), ...Object.keys(ntnbAprox)]));
    const ntnbSortedKeys = allNtnbKeys.filter(k => k !== "Outras / Não Espec.").sort((a,b) => {
        const ya = parseInt(a.replace(/\D/g, '')) || 0;
        const yb = parseInt(b.replace(/\D/g, '')) || 0;
        return ya - yb;
    });
    const outrasVol = (ntnbDecl["Outras / Não Espec."] || 0) + (ntnbAprox["Outras / Não Espec."] || 0);
    if (outrasVol > 0) ntnbSortedKeys.push("Outras / Não Espec.");

    const classificadoVol = ntnbSortedKeys.filter(k => k !== "Outras / Não Espec.").reduce((sum, k) => sum + (ntnbDecl[k]||0) + (ntnbAprox[k]||0), 0);
    const cobertura = totalIpca > 0 ? (classificadoVol / totalIpca * 100) : 0;

    const sortedMonths = Object.keys(monthlyVol).sort();

    return {
        temporal: {
            labels: sortedMonths,
            datasets: [
                { label: "Volume (R$)", data: sortedMonths.map(m => monthlyVol[m].volume) },
                { label: "Qtd Ofertas", data: sortedMonths.map(m => monthlyVol[m].count) }
            ]
        },
        monthly_indexer: {
            labels: sortedMonths,
            cdi: sortedMonths.map(m => monthlyIdx[m].CDI),
            ipca: sortedMonths.map(m => monthlyIdx[m].IPCA),
            pre: sortedMonths.map(m => monthlyIdx[m].PRE),
            outros: sortedMonths.map(m => monthlyIdx[m].OUTROS)
        },
        monthly_volume: null, // used in some places
        yearly_indexer: null, // not heavily used without temporal
        top_coordenadores: {
            labels: topLideresList.map(x => x.label),
            volumes: topLideresList.map(x => Number(x.v.toFixed(2))),
            counts: topLideresList.map(x => x.c)
        },
        top_emissores: {
            labels: topEmissoresList.map(x => x.label),
            volumes: topEmissoresList.map(x => Number(x.v.toFixed(2))),
            counts: topEmissoresList.map(x => x.c)
        },
        vencimento_spread: {
            labels: allYears,
            cdi_median: allYears.map(y => median(spreadCdi[y])),
            ipca_median: allYears.map(y => median(spreadIpca[y])),
            cdi_points: cdiPoints.sort((a,b) => b.volume - a.volume).slice(0, 500),
            ipca_points: ipcaPoints.sort((a,b) => b.volume - a.volume).slice(0, 500)
        },
        ntnb_volume: {
            labels: ntnbSortedKeys,
            vol_declarada: ntnbSortedKeys.map(k => Number((ntnbDecl[k]||0).toFixed(2))),
            vol_aproximada: ntnbSortedKeys.map(k => Number((ntnbAprox[k]||0).toFixed(2))),
            cnt_declarada: ntnbSortedKeys.map(k => ntnbCntDecl[k]||0),
            cnt_aproximada: ntnbSortedKeys.map(k => ntnbCntAprox[k]||0),
            cobertura: Number(cobertura.toFixed(1))
        }
    };
}

export function calcularInvestors(rows) {
    let pf=0, fd=0, est=0, prev=0, seg=0, inst=0;
    
    for (const r of rows) {
        pf += parseFloat(r.vol_pf || 0);
        fd += parseFloat(r.vol_fd || 0);
        est += parseFloat(r.vol_est || 0);
        prev += parseFloat(r.vol_prev || 0);
        seg += parseFloat(r.vol_seg || 0);
        inst += parseFloat(r.vol_inst || 0);
    }
    
    const total = pf + fd + est + prev + seg + inst;
    if (total === 0) return { alloc_pie: { labels: [], volumes: [] }, historico_mensal: { labels: [] } };

    const pieLabels = ["Pessoas Físicas", "Fundos", "Estrangeiros", "Previdência", "Seguradoras", "Demais Institucionais"];
    const pieVols = [pf, fd, est, prev, seg, inst];

    return {
        alloc_pie: {
            labels: pieLabels,
            volumes: pieVols.map(v => Number(v.toFixed(2)))
        },
        historico_mensal: { labels: [] } // Minimal since we use Pie primarily
    };
}

export function calcularRankings(rows) {
    const lideres = {};
    const emissores = {};
    const ativos = {};
    
    for (const r of rows) {
        const v = parseFloat(r.volume || 0);
        const l = r.lider || "Não Informado";
        const e = r.emissor || "Não Informado";
        const a = r.setor_ativo || "Não Informado";
        
        if (!lideres[l]) lideres[l] = { volume: 0, count: 0 };
        lideres[l].volume += v;
        lideres[l].count += 1;
        
        if (!emissores[e]) emissores[e] = { volume: 0, count: 0 };
        emissores[e].volume += v;
        emissores[e].count += 1;
        
        if (!ativos[a]) ativos[a] = { volume: 0, count: 0 };
        ativos[a].volume += v;
        ativos[a].count += 1;
    }
    
    const sortRanking = (obj) => Object.keys(obj).map(k => ({ nome: k, volume: obj[k].volume, qtd: obj[k].count })).sort((a, b) => b.volume - a.volume);

    return {
        lideres: sortRanking(lideres).slice(0, 30),
        emissores: sortRanking(emissores).slice(0, 30),
        ativos: sortRanking(ativos)
    };
}

export function exportToCsv(rows) {
    if (!rows || rows.length === 0) return;
    
    const truncated = rows.slice(0, 20000);
    const headers = [
        "Id_Processo", "Regime", "Ano", "Data", "Rito", "Status", "Valor_Mobiliario", "Indexador",
        "Emissor", "Coordenador_Lider", "Publico_Alvo", "ESG",
        "Volume_Registrado", "Taxa_Juros", "Vencimento"
    ];
    
    const csvLines = [headers.join(";")];
    for (const r of truncated) {
        csvLines.push([
            r.id, r.regime, r.ano, r.data, r.rito, r.status, r.setor_ativo, r.indexador,
            r.emissor, r.lider, r.publico, r.esg,
            r.volume.toFixed(2), r.taxa, r.vencimento
        ].map(val => `"${String(val || '').replace(/"/g, '""')}"`).join(";"));
    }
    
    const blob = new Blob([csvLines.join("\r\n")], { type: 'text/csv;charset=latin-1' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = "cvm_ofertas_primarias_export.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
}
