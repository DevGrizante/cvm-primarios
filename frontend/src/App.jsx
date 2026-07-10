import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Chart from 'chart.js/auto';

const formatCurrency = (val) => {
    if (val === undefined || val === null || isNaN(val)) return "R$ 0,00";
    if (val >= 1e9) return `R$ ${(val / 1e9).toFixed(2).replace(".", ",")} Bi`;
    if (val >= 1e6) return `R$ ${(val / 1e6).toFixed(2).replace(".", ",")} Mi`;
    return val.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
};

const formatNumber = (val) => {
    if (val === undefined || val === null || isNaN(val)) return "0";
    return val.toLocaleString("pt-BR");
};

const formatDate = (dateStr) => {
    if (!dateStr || typeof dateStr !== "string") return "-";
    const parts = dateStr.split("T")[0].split("-");
    if (parts.length === 3 && parts[0].length === 4) {
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return dateStr;
};

const getApiBase = () => {
    if (typeof window === "undefined") return "/api";
    if (window.location.protocol === "file:") return "http://localhost:8000/api";
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        if (window.location.port !== "8000") return "http://localhost:8000/api";
    }
    return "/api";
};
const API_BASE = getApiBase();

// Professional Lucide Vector Icons
const Icons = {
    TrendingUp: () => <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>,
    Shield: () => <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
    Search: () => <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>,
    X: () => <svg className="w-5 h-5 text-slate-400 hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>,
    ChevronUp: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" /></svg>,
    ChevronDown: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>,
    Download: () => <svg className="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>,
    RefreshCw: () => <svg className="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>,
    BarChart2: () => <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 20V10M12 20V4M6 20v-6" /></svg>,
    PieChart: () => <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>,
    Award: () => <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    FileText: () => <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
    AlertCircle: () => <svg className="w-4 h-4 text-amber-400 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    CheckCircle: () => <svg className="w-4 h-4 text-emerald-400 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    Clock: () => <svg className="w-4 h-4 text-slate-400 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    Filter: () => <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>
};

const ChartWrapper = ({ type, data, options, height = 300 }) => {
    const canvasRef = useRef(null);
    const chartInstance = useRef(null);

    useEffect(() => {
        if (!canvasRef.current || !data) return;
        if (chartInstance.current) {
            chartInstance.current.destroy();
        }
        const ctx = canvasRef.current.getContext("2d");
        chartInstance.current = new Chart(ctx, {
            type: type,
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                ...options
            }
        });
        return () => {
            if (chartInstance.current) {
                chartInstance.current.destroy();
            }
        };
    }, [type, data, options]);

    return (
        <div style={{ height: `${height}px`, width: "100%", position: "relative" }}>
            <canvas ref={canvasRef}></canvas>
        </div>
    );
};

// Loading Skeletons
const OffersTableSkeleton = () => (
    <div className="space-y-3 p-4">
        {[...Array(8)].map((_, i) => (
            <div key={i} className="flex items-center space-x-4 p-3 bg-slate-900/50 rounded border border-slate-800/60 animate-pulse">
                <div className="w-24 h-5 skeleton-bar rounded"></div>
                <div className="w-16 h-5 skeleton-bar rounded"></div>
                <div className="w-48 h-5 skeleton-bar rounded flex-1"></div>
                <div className="w-32 h-5 skeleton-bar rounded"></div>
                <div className="w-24 h-5 skeleton-bar rounded"></div>
                <div className="w-24 h-5 skeleton-bar rounded"></div>
            </div>
        ))}
    </div>
);

// Slide-over Drawer (Dossiê Executivo da Mesa)
const DrawerLateralDossie = ({ offer: initialOffer, onClose, onNavigate, totalItems, currentIndex, onUpdateOffer }) => {
    if (!initialOffer) return null;
    const [liveOffer, setLiveOffer] = useState(initialOffer);
    const [loadingApi, setLoadingApi] = useState(false);

    useEffect(() => {
        setLiveOffer(initialOffer);
        if (initialOffer && initialOffer.Id_Processo && (!initialOffer.Caracteristicas_CVM || !initialOffer.Taxa_Declarada)) {
            setLoadingApi(true);
            fetch(API_BASE + '/offers/' + encodeURIComponent(initialOffer.Id_Processo))
                .then(res => res.json())
                .then(data => {
                    setLoadingApi(false);
                    if (data && !data.detail) {
                        setLiveOffer(data);
                        if (onUpdateOffer) onUpdateOffer(data);
                    }
                })
                .catch(() => setLoadingApi(false));
        }
    }, [initialOffer]);

    const offer = liveOffer;

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "ArrowUp") onNavigate("prev");
            if (e.key === "ArrowDown") onNavigate("next");
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose, onNavigate]);

    const getIndexerColorClass = (idx) => {
        if (idx === "IPCA / Inflação") return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        if (idx === "CDI / DI") return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
        if (idx === "PRÉ (Prefixado)") return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        return "bg-slate-800 text-slate-300 border-slate-700";
    };

    const isTaxaConfirmada = offer.Taxa_Declarada || (offer.Taxa_Juros && !offer.Taxa_Juros.includes("a Definir") && !offer.Taxa_Juros.includes("Não Informado"));
    const isBookbuilding = (offer.Status?.toUpperCase().includes("ANDAMENTO") || offer.Status?.toUpperCase().includes("ANÁLISE INICIAL") || offer.Status?.toUpperCase().includes("AGUARDANDO BOOKBUILDING")) || offer.Alocacao_Pendente;

    return (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end transition-opacity duration-300">
            <div className="w-full md:w-[700px] bg-cvm-card border-l border-slate-800 shadow-2xl flex flex-col h-full drawer-slide-in">
                {/* Drawer Header */}
                <div className="p-5 glass-header flex items-center justify-between border-b border-slate-800">
                    <div className="flex items-center space-x-3">
                        <span className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                            <Icons.FileText />
                        </span>
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider block">Dossiê de Auditoria Executiva</span>
                                {loadingApi && (
                                    <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 animate-pulse flex items-center">
                                        <Icons.RefreshCw className="w-3 h-3 animate-spin mr-1.5" /> Consultando API CVM...
                                    </span>
                                )}
                            </div>
                            <h3 className="text-lg font-bold text-white font-display truncate max-w-[360px]" title={offer.Emissor}>{offer.Emissor}</h3>
                        </div>
                    </div>
                    
                    {/* Navigation Buttons Cima / Baixo & Esc */}
                    <div className="flex items-center space-x-2">
                        <button 
                            onClick={() => onNavigate("prev")} 
                            disabled={currentIndex <= 0}
                            title="Oferta Anterior (Cima)"
                            className="p-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 rounded text-slate-300 flex items-center space-x-1 text-xs font-mono border border-slate-700">
                            <Icons.ChevronUp />
                            <span>&uarr;</span>
                        </button>
                        <button 
                            onClick={() => onNavigate("next")} 
                            disabled={currentIndex >= totalItems - 1}
                            title="Próxima Oferta (Baixo)"
                            className="p-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 rounded text-slate-300 flex items-center space-x-1 text-xs font-mono border border-slate-700">
                            <Icons.ChevronDown />
                            <span>&darr;</span>
                        </button>
                        <div className="h-6 w-[1px] bg-slate-800 mx-1"></div>
                        <button 
                            onClick={onClose} 
                            title="Fechar (Esc)"
                            className="p-2 bg-slate-800/80 hover:bg-red-500/20 hover:text-red-400 rounded text-slate-400 transition-colors border border-slate-700">
                            <Icons.X />
                        </button>
                    </div>
                </div>

                {/* Drawer Body Scrollable */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {/* Executive Summary Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
                            <span className="text-xs text-slate-400 block mb-1">Volume Oficial Registrado</span>
                            <span className="text-xl font-bold text-emerald-400 font-display">{formatCurrency(offer.Volume_Float)}</span>
                        </div>
                        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
                            <span className="text-xs text-slate-400 block mb-1">Ativo / Tipo</span>
                            <span className="text-base font-semibold text-white truncate block" title={offer.Ativo}>{offer.Ativo}</span>
                        </div>
                        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 col-span-2 md:col-span-1">
                            <span className="text-xs text-slate-400 block mb-1">Status CVM</span>
                            <span className="text-xs font-semibold text-indigo-300 bg-indigo-500/10 px-2.5 py-1 rounded-full border border-indigo-500/20 inline-block mt-0.5">
                                {offer.Status}
                            </span>
                        </div>
                    </div>

                    {/* Credit Desk Remuneration Section (Spotless Audit) */}
                    <div className="p-5 bg-slate-900/80 rounded-xl border border-slate-800/80 space-y-3">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                            <span className="text-sm font-semibold text-slate-300 flex items-center">
                                <Icons.Award />
                                <span className="ml-1.5">Remuneração e Indexador da Oferta</span>
                            </span>
                            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getIndexerColorClass(offer.Indexador)}`}>
                                {offer.Indexador}
                            </span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                            <div>
                                <span className="text-xs text-slate-400 block">Indexador Encontrado</span>
                                <span className="text-sm font-semibold text-slate-200 mt-0.5 flex items-center">
                                    {offer.Indexador || "Não Informado"}
                                    {!offer.Indexador_Inferido || offer.Taxa_Declarada ? (
                                        <span className="ml-2 text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 inline-flex items-center">
                                            <Icons.Shield className="w-3 h-3 mr-1 inline" /> Oficial CVM / SRE
                                        </span>
                                    ) : (
                                        <span className="ml-2 text-[11px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                                            ESTIMADO
                                        </span>
                                    )}
                                </span>
                            </div>
                            <div>
                                <span className="text-xs text-slate-400 block">Status da Remuneração (Spread/Juros)</span>
                                <span className="text-sm font-semibold mt-0.5 block">
                                    {isTaxaConfirmada ? (
                                        <span className="text-emerald-400">{offer.Taxa_Juros}</span>
                                    ) : (
                                        <span className="text-amber-400 font-mono text-xs bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20 block inline-flex items-center">
                                            <Icons.Clock className="w-3.5 h-3.5 mr-1.5 inline" /> {offer.Taxa_Juros || "Spread a Definir em Bookbuilding"}
                                        </span>
                                    )}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Características do Valor Mobiliário (API REST Oficial CVM) */}
                    {offer.Caracteristicas_CVM && offer.Caracteristicas_CVM.length > 0 && (
                        <div className="space-y-3">
                            <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                                <Icons.FileText className="w-4 h-4 text-indigo-400" />
                                <span>Características do Valor Mobiliário</span>
                                <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">API REST SRE</span>
                            </h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 bg-slate-900/40 p-3 rounded-lg border border-slate-800/60 max-h-60 overflow-y-auto">
                                {offer.Caracteristicas_CVM.filter(c => c.visivel && c.campoValor).map((c, i) => (
                                    <div key={i} className="p-2 bg-slate-800/40 rounded border border-slate-800">
                                        <span className="text-[11px] text-slate-400 font-mono uppercase block">{c.campoNome}</span>
                                        <span className="text-xs font-medium text-slate-200 mt-0.5 block break-words">{c.campoValor}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Investor Demography Table (Official vs Imputed check) */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Alocação por Demografia (R$ Real e Share)</h4>
                            {offer.Alocacao_Pendente ? (
                                <span className="text-xs text-amber-400 font-mono bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 inline-flex items-center">
                                    <Icons.Clock className="w-3.5 h-3.5 mr-1 inline" /> Alocação Pendente (Bookbuilding)
                                </span>
                            ) : (
                                <span className="text-xs text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 inline-flex items-center">
                                    <Icons.CheckCircle className="w-3.5 h-3.5 mr-1 inline" /> 100% Confirmada CVM
                                </span>
                            )}
                        </div>

                        <div className="bg-slate-900/60 rounded-xl border border-slate-800 overflow-hidden">
                            <table className="w-full text-left text-xs">
                                <thead className="bg-slate-950 text-slate-400 uppercase font-mono text-[11px] border-b border-slate-800">
                                    <tr>
                                        <th className="p-3">Segmento do Investidor</th>
                                        <th className="p-3 text-right">Volume Alocado (R$)</th>
                                        <th className="p-3 text-right">Share (%)</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                                    <tr>
                                        <td className="p-3 font-medium flex items-center space-x-2">
                                            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                                            <span>Pessoas Físicas (Varejo / Qualificado)</span>
                                        </td>
                                        <td className="p-3 text-right font-mono">{formatCurrency(offer.Vol_Pessoa_Fisica)}</td>
                                        <td className="p-3 text-right font-mono text-emerald-400">
                                            {offer.Volume_Float > 0 ? `${((offer.Vol_Pessoa_Fisica / offer.Volume_Float) * 100).toFixed(1)}%` : "0,0%"}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="p-3 font-medium flex items-center space-x-2">
                                            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
                                            <span>Fundos de Investimento</span>
                                        </td>
                                        <td className="p-3 text-right font-mono">{formatCurrency(offer.Vol_Fundos)}</td>
                                        <td className="p-3 text-right font-mono text-indigo-400">
                                            {offer.Volume_Float > 0 ? `${((offer.Vol_Fundos / offer.Volume_Float) * 100).toFixed(1)}%` : "0,0%"}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="p-3 font-medium flex items-center space-x-2">
                                            <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                                            <span>Investidores Estrangeiros</span>
                                        </td>
                                        <td className="p-3 text-right font-mono">{formatCurrency(offer.Vol_Estrangeiro)}</td>
                                        <td className="p-3 text-right font-mono text-blue-400">
                                            {offer.Volume_Float > 0 ? `${((offer.Vol_Estrangeiro / offer.Volume_Float) * 100).toFixed(1)}%` : "0,0%"}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="p-3 font-medium flex items-center space-x-2">
                                            <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
                                            <span>Entidades de Previdência / Outros Institucionais</span>
                                        </td>
                                        <td className="p-3 text-right font-mono">{formatCurrency(offer.Vol_Previdencia)}</td>
                                        <td className="p-3 text-right font-mono text-purple-400">
                                            {offer.Volume_Float > 0 ? `${((offer.Vol_Previdencia / offer.Volume_Float) * 100).toFixed(1)}%` : "0,0%"}
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Institutional & Legal Metadata */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-slate-900/40 rounded-xl border border-slate-800 text-xs">
                        <div>
                            <span className="text-slate-500 block">ID Processo / Requerimento</span>
                            <span className="font-mono text-slate-300 font-semibold mt-0.5 block">{offer.Id_Processo}</span>
                        </div>
                        <div>
                            <span className="text-slate-500 block">Data de Registro / Entrada</span>
                            <span className="font-mono text-slate-300 mt-0.5 block">{formatDate(offer.Data_Clean)}</span>
                        </div>
                        <div>
                            <span className="text-slate-500 block">Coordenador Líder</span>
                            <span className="text-slate-300 font-medium mt-0.5 block truncate" title={offer.Lider}>{offer.Lider}</span>
                        </div>
                        <div>
                            <span className="text-slate-500 block">Processo SEI / Rito</span>
                            <span className="text-slate-300 mt-0.5 block">{offer.Processo_SEI || "Não informado"} ({offer.Rito})</span>
                        </div>
                        <div>
                            <span className="text-slate-500 block">Administrador / Gestor</span>
                            <span className="text-slate-300 mt-0.5 block truncate" title={`${offer.Administrador} / ${offer.Gestor}`}>{offer.Administrador || "-"} / {offer.Gestor || "-"}</span>
                        </div>
                        <div>
                            <span className="text-slate-500 block">Custodiante</span>
                            <span className="text-slate-300 mt-0.5 block truncate" title={offer.Custodiante}>{offer.Custodiante || "-"}</span>
                        </div>
                    </div>
                </div>

                {/* Drawer Footer */}
                <div className="p-4 bg-slate-950 border-t border-slate-800 flex justify-between items-center text-xs text-slate-400">
                    <span>Navegue com setas <kbd className="px-1.5 py-0.5 bg-slate-800 rounded font-mono">&uarr;</kbd> <kbd className="px-1.5 py-0.5 bg-slate-800 rounded font-mono">&darr;</kbd> ou feche com <kbd className="px-1.5 py-0.5 bg-slate-800 rounded font-mono">Esc</kbd></span>
                    <button 
                        onClick={onClose} 
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors shadow-lg shadow-indigo-600/20">
                        Concluir e Fechar
                    </button>
                </div>
            </div>
        </div>
    );
};

// Main App Component
const App = () => {
    // URL Search Params Hydration
    const getInitialUrlParams = () => new URLSearchParams(window.location.search);
    
    const [status, setStatus] = useState({ status: "loading", rows_count: 0, last_update: "Conectando..." });
    const [filters, setFilters] = useState({
        ano: getInitialUrlParams().get("ano") || "Recentes (2023-2026)",
        rito: getInitialUrlParams().get("rito") || "Todos",
        ativo: getInitialUrlParams().get("ativo") || "Todos",
        status: getInitialUrlParams().get("status") || "Todos",
        indexador: getInitialUrlParams().get("indexador") || "Todos",
        publico: getInitialUrlParams().get("publico") || "Todos",
        regime: getInitialUrlParams().get("regime") || "Todos",
        incluir_estimados: getInitialUrlParams().get("incluir_estimados") === "true" || false
    });

    const [searchQuery, setSearchQuery] = useState(getInitialUrlParams().get("busca") || "");
    const [pageSize, setPageSize] = useState(25);
    const [currentPage, setCurrentPage] = useState(parseInt(getInitialUrlParams().get("page") || "1", 10));
    const [activeTab, setActiveTab] = useState("explorer");
    
    const [kpis, setKpis] = useState(null);
    const [overviewCharts, setOverviewCharts] = useState(null);
    const [investorCharts, setInvestorCharts] = useState(null);
    const [rankings, setRankings] = useState(null);
    const [offersData, setOffersData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
    const [selectedOffer, setSelectedOffer] = useState(null);
    const [loading, setLoading] = useState(true);
    const [sortBy, setSortBy] = useState(getInitialUrlParams().get("sort_by") || "Data_Clean");
    const [sortOrder, setSortOrder] = useState(getInitialUrlParams().get("sort_order") || "desc");

    // Fetch System Status
    useEffect(() => {
        fetch(API_BASE + "/status")
            .then(r => r.json())
            .then(data => setStatus(data))
            .catch(() => setStatus({ status: "error", rows_count: 0, last_update: "Erro de Conexão CVM" }));
    }, []);

    // Synchronize filters & search with URL Query String via window.history.pushState
    useEffect(() => {
        const params = new URLSearchParams();
        if (searchQuery) params.set("busca", searchQuery);
        if (filters.ano !== "Recentes (2023-2026)") params.set("ano", filters.ano);
        if (filters.rito !== "Todos") params.set("rito", filters.rito);
        if (filters.ativo !== "Todos") params.set("ativo", filters.ativo);
        if (filters.indexador !== "Todos") params.set("indexador", filters.indexador);
        if (filters.status !== "Todos") params.set("status", filters.status);
        if (filters.publico !== "Todos") params.set("publico", filters.publico);
        if (filters.regime !== "Todos") params.set("regime", filters.regime);
        if (filters.incluir_estimados) params.set("incluir_estimados", "true");
        if (sortBy !== "Data_Clean") params.set("sort_by", sortBy);
        if (sortOrder !== "desc") params.set("sort_order", sortOrder);
        if (currentPage !== 1) params.set("page", currentPage);
        
        const newUrl = `${window.location.pathname}${params.toString() ? "?" + params.toString() : ""}`;
        window.history.pushState({ path: newUrl }, "", newUrl);
    }, [filters, searchQuery, sortBy, sortOrder, currentPage]);

    // Unified Debounced Data Fetch with AbortController
    useEffect(() => {
        const controller = new AbortController();
        const signal = controller.signal;
        setLoading(true);

        const timer = setTimeout(() => {
            const queryParams = new URLSearchParams({
                ano: filters.ano,
                rito: filters.rito,
                ativo: filters.ativo,
                status: filters.status,
                indexador: filters.indexador,
                publico: filters.publico,
                regime: filters.regime,
                busca: searchQuery,
                incluir_estimados: filters.incluir_estimados ? "true" : "false",
                page: currentPage,
                page_size: pageSize,
                sort_by: sortBy,
                sort_order: sortOrder
            }).toString();

            fetch(`${API_BASE}/kpis?${queryParams}`, { signal })
                .then(r => r.json())
                .then(res => setKpis(res))
                .catch(err => { if (err.name !== "AbortError") console.error("Erro em KPIs:", err); });

            fetch(`${API_BASE}/charts/overview?${queryParams}`, { signal })
                .then(r => r.json())
                .then(res => setOverviewCharts(res))
                .catch(err => { if (err.name !== "AbortError") console.error("Erro em charts overview:", err); });

            fetch(`${API_BASE}/charts/investors?${queryParams}`, { signal })
                .then(r => r.json())
                .then(res => setInvestorCharts(res))
                .catch(err => { if (err.name !== "AbortError") console.error("Erro em charts investors:", err); });

            fetch(`${API_BASE}/rankings?${queryParams}`, { signal })
                .then(r => r.json())
                .then(res => setRankings(res))
                .catch(err => { if (err.name !== "AbortError") console.error("Erro em rankings:", err); });

            fetch(`${API_BASE}/offers?${queryParams}`, { signal })
                .then(r => r.json())
                .then(res => {
                    setOffersData(res);
                    setLoading(false);
                })
                .catch(err => {
                    if (err.name !== "AbortError") {
                        console.error("Erro ao carregar ofertas:", err);
                        setLoading(false);
                    }
                });
        }, 350); // 350ms debounce

        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [filters, searchQuery, currentPage, pageSize, sortBy, sortOrder]);

    const handleFilterChange = (key, val) => {
        setFilters(prev => ({ ...prev, [key]: val }));
        setCurrentPage(1);
    };

    const toggleMultiSelectFilter = (field, value) => {
        setFilters(prev => {
            const current = prev[field] || "Todos";
            if (value === "Todos") {
                return { ...prev, [field]: "Todos" };
            }
            let selected = current === "Todos" ? [] : current.split(",").map(s => s.trim()).filter(Boolean);
            if (selected.includes(value)) {
                selected = selected.filter(s => s !== value);
            } else {
                selected.push(value);
            }
            return {
                ...prev,
                [field]: selected.length === 0 ? "Todos" : selected.join(",")
            };
        });
        setCurrentPage(1);
    };

    const handleClearFilters = () => {
        setFilters({
            ano: "Recentes (2023-2026)",
            rito: "Todos",
            ativo: "Todos",
            status: "Todos",
            indexador: "Todos",
            publico: "Todos",
            regime: "Todos",
            incluir_estimados: false
        });
        setSearchQuery("");
        setCurrentPage(1);
        setSortBy("Data_Clean");
        setSortOrder("desc");
    };

    const handleSort = (field) => {
        if (sortBy === field) {
            setSortOrder(sortOrder === "asc" ? "desc" : "asc");
        } else {
            setSortBy(field);
            setSortOrder("desc");
        }
    };

    const handleExport = () => {
        const queryParams = new URLSearchParams({
            ano: filters.ano,
            rito: filters.rito,
            ativo: filters.ativo,
            status: filters.status,
            indexador: filters.indexador,
            publico: filters.publico,
            regime: filters.regime,
            busca: searchQuery
        }).toString();
        window.open(`${API_BASE}/export?${queryParams}`, "_blank");
    };

    const handleDrawerNavigate = (direction) => {
        if (!selectedOffer || !offersData.items.length) return;
        const currentIdx = offersData.items.findIndex(o => o.Id_Processo === selectedOffer.Id_Processo);
        if (direction === "prev" && currentIdx > 0) {
            setSelectedOffer(offersData.items[currentIdx - 1]);
        } else if (direction === "next" && currentIdx < offersData.items.length - 1) {
            setSelectedOffer(offersData.items[currentIdx + 1]);
        }
    };

    const getIndexerColorClass = (idx) => {
        if (idx === "IPCA / Inflação") return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        if (idx === "CDI / DI") return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
        if (idx === "PRÉ (Prefixado)") return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        return "bg-slate-800 text-slate-300 border-slate-700";
    };

    return (
        <div className="min-h-screen flex flex-col">
            {/* Top Navigation Bar with Unified Search */}
            <header className="glass-header sticky top-0 z-40 px-6 py-4">
                <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                            <Icons.TrendingUp />
                        </div>
                        <div>
                            <div className="flex items-center space-x-2">
                                <h1 className="text-xl font-extrabold text-white font-display tracking-tight">CVM Primários Monitor PRO</h1>
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                                    Emissões
                                </span>
                            </div>
                            <p className="text-xs text-slate-400 flex items-center space-x-2 mt-0.5">
                                <span>Auditoria Oficial CVM</span>
                                <span>•</span>
                                <span className="font-mono text-indigo-300">{formatNumber(status.rows_count)} Ofertas no Banco</span>
                                <span>•</span>
                                <span className="text-slate-500">{status.last_update}</span>
                            </p>
                        </div>
                    </div>

                    {/* Unified Debounced Search Bar Header */}
                    <div className="flex items-center space-x-3 flex-1 max-w-md">
                        <div className="relative w-full">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                                <Icons.Search />
                            </div>
                            <input
                                type="text"
                                placeholder="Busque por Emissor, Coordenador, Ativo ou Processo..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-9 pr-8 py-2 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all shadow-inner"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => setSearchQuery("")}
                                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-white">
                                    <Icons.X />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Navigation Tabs */}
                    <nav className="flex items-center space-x-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
                        <button
                            onClick={() => setActiveTab("explorer")}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${activeTab === "explorer" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30" : "text-slate-400 hover:text-white"}`}>
                            <Icons.FileText />
                            <span>Mesa & Dossiê</span>
                        </button>
                        <button
                            onClick={() => setActiveTab("charts")}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${activeTab === "charts" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30" : "text-slate-400 hover:text-white"}`}>
                            <Icons.BarChart2 />
                            <span>Inteligência & Temporal</span>
                        </button>
                        <button
                            onClick={() => setActiveTab("investors")}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${activeTab === "investors" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30" : "text-slate-400 hover:text-white"}`}>
                            <Icons.PieChart />
                            <span>Demografia Varejo</span>
                        </button>
                    </nav>
                </div>
            </header>

            {/* Sticky Quick-Access Multi-Selection Chips Row */}
            <div className="sticky top-[73px] z-30 glass-header px-6 py-2.5 border-b border-slate-800/80 shadow-md">
                <div className="max-w-7xl mx-auto flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3 text-xs">
                    {/* Instrumentos (Ativos) Multi-Select Chips */}
                    <div className="flex flex-wrap items-center gap-1.5 flex-1">
                        <span className="text-[11px] font-mono uppercase text-slate-400 font-semibold mr-1 flex items-center">
                            <Icons.Filter /> <span className="ml-1">Ativo:</span>
                        </span>
                        {["Todos", "Debêntures", "CRI", "CRA", "FII", "Nota Comercial", "Ações", "FIDC"].map(item => {
                            const isAll = item === "Todos";
                            const currentArr = (filters.ativo || "Todos").split(",").map(s => s.trim());
                            const isSelected = isAll ? (filters.ativo === "Todos" || !filters.ativo) : currentArr.includes(item);
                            const label = isAll ? "Todos" : item;
                            return (
                                <button
                                    key={item}
                                    onClick={() => toggleMultiSelectFilter("ativo", item)}
                                    className={`px-2.5 py-1 rounded-lg font-mono text-[11px] font-medium transition-all flex items-center space-x-1 border ${
                                        isSelected
                                            ? "bg-indigo-600/25 text-indigo-300 border-indigo-500 shadow-sm"
                                            : "bg-slate-900/80 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700"
                                    }`}>
                                    <span>{label}</span>
                                    {isSelected && !isAll && <span className="text-indigo-400 font-bold ml-1">•</span>}
                                </button>
                            );
                        })}
                    </div>

                    {/* Indexadores & Estimated Toggle */}
                    <div className="flex flex-wrap items-center gap-1.5 border-t lg:border-t-0 pt-2 lg:pt-0 border-slate-800/60 w-full lg:w-auto justify-start lg:justify-end">
                        <span className="text-[11px] font-mono uppercase text-slate-400 font-semibold mr-1">
                            Indexador:
                        </span>
                        {["Todos", "CDI / DI", "IPCA / Inflação", "PRÉ (Prefixado)"].map(item => {
                            const isAll = item === "Todos";
                            const currentArr = (filters.indexador || "Todos").split(",").map(s => s.trim());
                            const isSelected = isAll ? (filters.indexador === "Todos" || !filters.indexador) : currentArr.includes(item);
                            const label = isAll ? "Todos" : (item === "PRÉ (Prefixado)" ? "PRÉ" : item.split(" ")[0]);
                            return (
                                <button
                                    key={item}
                                    onClick={() => toggleMultiSelectFilter("indexador", item)}
                                    className={`px-2.5 py-1 rounded-lg font-mono text-[11px] font-medium transition-all flex items-center space-x-1 border ${
                                        isSelected
                                            ? getIndexerColorClass(item) + " font-semibold shadow-sm"
                                            : "bg-slate-900/80 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700"
                                    }`}>
                                    <span>{label}</span>
                                    {isSelected && !isAll && <span className="font-bold ml-1">•</span>}
                                </button>
                            );
                        })}

                        <div className="h-4 w-px bg-slate-800 mx-1.5 hidden sm:block"></div>

                        {/* Estimated Volume Toggle */}
                        <button
                            onClick={() => handleFilterChange("incluir_estimados", !filters.incluir_estimados)}
                            title="Quando ativado, inclui volumes alvo de bookbuilding ainda em formação nos KPIs e rankings."
                            className={`px-2.5 py-1 rounded-lg font-mono text-[11px] font-medium transition-all flex items-center space-x-1 border ${
                                filters.incluir_estimados
                                    ? "bg-purple-500/20 text-purple-300 border-purple-500/50 shadow-sm"
                                    : "bg-slate-900/80 text-slate-400 border-slate-800 hover:text-slate-200"
                            }`}>
                            <span>Estimados:</span>
                            <strong className={filters.incluir_estimados ? "text-purple-300 font-bold" : "text-slate-500"}>
                                {filters.incluir_estimados ? "INCLUÍDOS" : "EXCLUÍDOS"}
                            </strong>
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
                {/* 4 Dedicated Credit Desk KPIs Row */}
                {kpis && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* KPI 1: Share de Volume por Indexador */}
                        <div className="glass-card rounded-2xl p-5 border-l-4 border-l-amber-500 flex flex-col justify-between">
                            <div className="flex justify-between items-start">
                                <div>
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Share de Volume por Indexador</span>
                                    <div className="flex items-baseline space-x-2 mt-2">
                                        <span className="text-2xl font-bold text-white font-display">{kpis.share_cdi}%</span>
                                        <span className="text-xs font-mono text-indigo-400">CDI/DI</span>
                                    </div>
                                </div>
                                <span className="p-2.5 bg-amber-500/10 rounded-xl text-amber-400 border border-amber-500/20">
                                    <Icons.Award />
                                </span>
                            </div>
                            <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-3 border-t border-slate-800/80 mt-3">
                                <span>IPCA: <strong className="text-amber-400">{kpis.share_ipca}%</strong></span>
                                <span>PRÉ: <strong className="text-emerald-400">{kpis.share_pre}%</strong></span>
                            </div>
                        </div>

                        {/* KPI 2: Pipeline em Bookbuilding */}
                        <div className="glass-card rounded-2xl p-5 border-l-4 border-l-indigo-500 flex flex-col justify-between">
                            <div className="flex justify-between items-start">
                                <div>
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Pipeline Bookbuilding (A Definir)</span>
                                    <h3 className="text-2xl font-bold text-white font-display mt-2">{formatCurrency(kpis.vol_bookbuilding)}</h3>
                                </div>
                                <span className="p-2.5 bg-indigo-500/10 rounded-xl text-indigo-400 border border-indigo-500/20">
                                    <Icons.TrendingUp />
                                </span>
                            </div>
                            <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-3 border-t border-slate-800/80 mt-3">
                                <span>Ofertas em Alvo/Spread:</span>
                                <strong className="text-indigo-400">{formatNumber(kpis.qtd_bookbuilding)} deals</strong>
                            </div>
                        </div>

                        {/* KPI 3: Ticket Médio / Varejo Real */}
                        <div className="glass-card rounded-2xl p-5 border-l-4 border-l-emerald-500 flex flex-col justify-between">
                            <div className="flex justify-between items-start">
                                <div>
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Ticket Médio / Alocação Varejo</span>
                                    <h3 className="text-2xl font-bold text-white font-display mt-2">{formatCurrency(kpis.ticket_medio)}</h3>
                                </div>
                                <span className="p-2.5 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
                                    <Icons.Shield />
                                </span>
                            </div>
                            <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-3 border-t border-slate-800/80 mt-3">
                                <span>Share Real PF (Confirmado):</span>
                                <strong className="text-emerald-400">{kpis.taxa_varejo}%</strong>
                            </div>
                        </div>

                        {/* KPI 4: Visão Geral de Juros / Volume Confirmado */}
                        <div className="glass-card rounded-2xl p-5 border-l-4 border-l-blue-500 flex flex-col justify-between">
                            <div className="flex justify-between items-start">
                                <div>
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Volume Confirmado & Rito Auto</span>
                                    <h3 className="text-2xl font-bold text-white font-display mt-2">{formatCurrency(kpis.vol_confirmado)}</h3>
                                </div>
                                <span className="p-2.5 bg-blue-500/10 rounded-xl text-blue-400 border border-blue-500/20">
                                    <Icons.BarChart2 />
                                </span>
                            </div>
                            <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-3 border-t border-slate-800/80 mt-3">
                                <span>Ofertas Rito Automático:</span>
                                <strong className="text-blue-400">{kpis.taxa_auto}%</strong>
                            </div>
                        </div>
                    </div>
                )}

                {/* Filter Bar Component */}
                <div className="glass-card rounded-2xl p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
                        <div className="flex items-center space-x-2 text-sm font-semibold text-white">
                            <Icons.Filter />
                            <span>Filtros Operacionais & Sincronização URL</span>
                        </div>
                        <div className="flex items-center space-x-3">
                            <button
                                onClick={handleClearFilters}
                                className="text-xs text-slate-400 hover:text-white transition-colors flex items-center space-x-1 py-1 px-2.5 rounded bg-slate-800/80 hover:bg-slate-700">
                                <Icons.RefreshCw />
                                <span>Limpar Filtros</span>
                            </button>
                            <button
                                onClick={handleExport}
                                className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-1.5 px-3 rounded-lg flex items-center space-x-1.5 transition-all shadow-lg shadow-emerald-600/20">
                                <Icons.Download />
                                <span>Exportar Planilha Excel/CSV</span>
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                        <div>
                            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Ano / Período</label>
                            <select
                                value={filters.ano}
                                onChange={(e) => handleFilterChange("ano", e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1.5 px-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono">
                                <option value="Recentes (2023-2026)">Recentes (2023-2026)</option>
                                <option value="Todos">Todos os Anos</option>
                                <option value="2026">2026</option>
                                <option value="2025">2025</option>
                                <option value="2024">2024</option>
                                <option value="2023">2023</option>
                            </select>
                        </div>

                        <div>
                            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Ativo Mobiliário</label>
                            <select
                                value={filters.ativo}
                                onChange={(e) => handleFilterChange("ativo", e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1.5 px-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                                <option value="Todos">Todos os Ativos</option>
                                <option value="Debêntures">Debêntures</option>
                                <option value="CRI,CRA">CRI & CRA (Securitização)</option>
                                <option value="CRI">CRI - Cert. Recebíveis Imob.</option>
                                <option value="CRA">CRA - Cert. Recebíveis Agron.</option>
                                <option value="FII">FII - Fundos Imobiliários</option>
                                <option value="Nota Comercial">Notas Comerciais</option>
                                <option value="Ações">Ações / Units</option>
                                <option value="FIDC">FIDC - Direitos Creditórios</option>
                            </select>
                        </div>

                        <div>
                            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Indexador / Juros</label>
                            <select
                                value={filters.indexador}
                                onChange={(e) => handleFilterChange("indexador", e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1.5 px-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                                <option value="Todos">Todos os Indexadores</option>
                                <option value="CDI / DI">CDI / DI (Índigo)</option>
                                <option value="IPCA / Inflação">IPCA / Inflação (Âmbar)</option>
                                <option value="PRÉ (Prefixado)">PRÉ Prefixado (Esmeralda)</option>
                            </select>
                        </div>

                        <div>
                            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Status na CVM</label>
                            <select
                                value={filters.status}
                                onChange={(e) => handleFilterChange("status", e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1.5 px-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                                <option value="Todos">Todos os Status</option>
                                <option value="Em Andamento (Bookbuilding)">Em Andamento / Bookbuilding</option>
                                <option value="Registrada">Registrada / Encerrada</option>
                                <option value="Dispensada">Dispensada</option>
                            </select>
                        </div>

                        <div>
                            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Público-Alvo</label>
                            <select
                                value={filters.publico}
                                onChange={(e) => handleFilterChange("publico", e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1.5 px-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                                <option value="Todos">Todos os Públicos</option>
                                <option value="Investidores Profissionais">Investidores Profissionais</option>
                                <option value="Investidores Qualificados">Investidores Qualificados</option>
                                <option value="Público em Geral">Público em Geral</option>
                            </select>
                        </div>

                        <div>
                            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Regime / Rito</label>
                            <select
                                value={filters.regime}
                                onChange={(e) => handleFilterChange("regime", e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1.5 px-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                                <option value="Todos">Todos os Regimes</option>
                                <option value="Resolução CVM 160">Resolução CVM 160</option>
                                <option value="ICVM 400">ICVM 400 (Antigo Varejo)</option>
                                <option value="ICVM 476">ICVM 476 (Antigo Restrito)</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Tab 1: Explorer & Table with Slide-over Drawer */}
                {activeTab === "explorer" && (
                    <div className="glass-card rounded-2xl overflow-hidden shadow-xl">
                        <div className="p-4 bg-slate-900/60 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
                            <div className="flex items-center space-x-3">
                                <h2 className="text-base font-bold text-white font-display">Tabela de Ofertas Primárias e Remuneração</h2>
                                <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded-full border border-slate-700">
                                    Página {offersData.page} de {offersData.total_pages} ({formatNumber(offersData.total)} ofertas)
                                </span>
                            </div>

                            <div className="flex items-center space-x-3">
                                <span className="text-xs text-slate-400 font-mono">Por página:</span>
                                <select
                                    value={pageSize}
                                    onChange={(e) => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
                                    className="bg-slate-900 border border-slate-700 rounded py-1 px-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500">
                                    <option value={15}>15</option>
                                    <option value={25}>25</option>
                                    <option value={50}>50</option>
                                    <option value={100}>100</option>
                                </select>
                            </div>
                        </div>

                        {loading ? (
                            <OffersTableSkeleton />
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse data-grid text-xs">
                                    <thead>
                                        <tr className="border-b border-slate-800 text-slate-400 font-mono uppercase text-[11px] select-none">
                                            <th className="p-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("Data_Clean")}>
                                                Data {sortBy === "Data_Clean" && (sortOrder === "asc" ? "\u2191" : "\u2193")}
                                            </th>
                                            <th className="p-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("Emissor")}>
                                                Emissor / Ofertante {sortBy === "Emissor" && (sortOrder === "asc" ? "\u2191" : "\u2193")}
                                            </th>
                                            <th className="p-3.5">Ativo / Tipo</th>
                                            <th className="p-3.5">Indexador</th>
                                            <th className="p-3.5">Remuneração (Spread/Juros)</th>
                                            <th className="p-3.5 text-right cursor-pointer hover:text-white" onClick={() => handleSort("Volume_Float")}>
                                                Volume Registrado {sortBy === "Volume_Float" && (sortOrder === "asc" ? "\u2191" : "\u2193")}
                                            </th>
                                            <th className="p-3.5 text-center">Vencimento (MM/AA)</th>
                                            <th className="p-3.5 text-center">Auditoria</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/50 text-slate-300">
                                        {offersData.items.map((r, i) => {
                                            const isSelected = selectedOffer && selectedOffer.Id_Processo === r.Id_Processo;
                                            return (
                                                <tr 
                                                    key={r.Id_Processo + i} 
                                                    onClick={() => setSelectedOffer(r)}
                                                    className={`cursor-pointer transition-colors ${isSelected ? "bg-indigo-600/15 border-l-4 border-l-indigo-500" : "hover:bg-slate-800/40"}`}>
                                                    <td className="p-3.5 font-mono text-slate-400 whitespace-nowrap">{formatDate(r.Data_Clean)}</td>
                                                    <td className="p-3.5 font-semibold text-white max-w-[240px] truncate" title={r.Emissor}>
                                                        {r.Emissor}
                                                        <span className="block text-[10px] text-slate-500 font-mono mt-0.5 truncate">{r.Lider}</span>
                                                    </td>
                                                    <td className="p-3.5">
                                                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/80 font-mono text-[11px]">
                                                            {r.Ativo}
                                                        </span>
                                                    </td>
                                                    <td className="p-3.5 whitespace-nowrap">
                                                        <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${getIndexerColorClass(r.Indexador)}`}>
                                                            {r.Indexador}
                                                        </span>
                                                    </td>
                                                    <td className="p-3.5 max-w-[200px]">
                                                        {(r.Taxa_Declarada || r.Taxa_Juros?.includes("*(Hist. Emissor)*") || (r.Taxa_Juros && !r.Taxa_Juros.includes("a Definir") && !r.Taxa_Juros.includes("Não Informado"))) ? (
                                                            <span className="text-emerald-400 font-semibold truncate block" title={r.Taxa_Juros}>{r.Taxa_Juros}</span>
                                                        ) : (
                                                            <span className="text-amber-400 text-[11px] font-mono bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 block truncate inline-flex items-center" title={r.Taxa_Juros || "Spread a Definir (Bookbuilding)"}>
                                                                <Icons.Clock className="w-3 h-3 inline mr-1 shrink-0" /> {r.Taxa_Juros?.replace(" (Bookbuilding)", "") || "Alvo (Bookbuilding)"}
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="p-3.5 text-right font-mono font-bold text-emerald-400 whitespace-nowrap">
                                                        {formatCurrency(r.Volume_Float)}
                                                        {r.Is_Estimated_Vol && (
                                                            <span className="ml-1.5 px-1.5 py-0.5 rounded text-[9px] font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30" title="Volume Estimado (Alvo inicial / bookbuilding)">
                                                                EST
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="p-3.5 whitespace-nowrap text-center font-mono text-slate-300">
                                                        {r.Vencimento && r.Vencimento !== "N/I" ? (
                                                            <span className="px-2.5 py-1 rounded-md bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-semibold text-[11px] block">{r.Vencimento}</span>
                                                        ) : (
                                                            <span className="text-slate-600">-</span>
                                                        )}
                                                    </td>
                                                    <td className="p-3.5 text-center">
                                                        <button 
                                                            onClick={(e) => { e.stopPropagation(); setSelectedOffer(r); }}
                                                            className="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded border border-indigo-500/30 transition-all text-xs font-mono">
                                                            Dossiê &rarr;
                                                        </button>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                        {!offersData.items.length && (
                                            <tr>
                                                <td colSpan={9} className="p-12 text-center text-slate-400">
                                                    <div className="max-w-md mx-auto">
                                                        <p className="text-base font-semibold text-slate-300 mb-1">Nenhuma oferta carregada ou conexão pendente na porta 8000</p>
                                                        <p className="text-xs text-slate-500">Certifique-se de que o backend Python (`python main.py` no terminal do backend) está ativo na porta 8000.</p>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Pagination Footer */}
                        <div className="p-4 bg-slate-900/60 border-t border-slate-800 flex items-center justify-between">
                            <span className="text-xs font-mono text-slate-400">
                                Exibindo {(offersData.page - 1) * pageSize + 1} a {Math.min(offersData.page * pageSize, offersData.total)} de {formatNumber(offersData.total)}
                            </span>
                            <div className="flex items-center space-x-2">
                                <button
                                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                    disabled={currentPage <= 1 || loading}
                                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded text-xs font-mono border border-slate-700">
                                    &larr; Anterior
                                </button>
                                <span className="px-3 py-1 bg-slate-950 rounded text-xs font-mono text-indigo-400 border border-slate-800">
                                    {currentPage} / {offersData.total_pages}
                                </span>
                                <button
                                    onClick={() => setCurrentPage(p => Math.min(offersData.total_pages, p + 1))}
                                    disabled={currentPage >= offersData.total_pages || loading}
                                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded text-xs font-mono border border-slate-700">
                                    Próxima &rarr;
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Tab 2: Charts & Monthly Stacked Bars */}
                {activeTab === "charts" && (
                    !overviewCharts ? (
                        <div className="p-16 text-center text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800">
                            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-4"></div>
                            <p className="font-semibold text-slate-300">Carregando Gráficos (Inteligência & Temporal)...</p>
                            <p className="text-xs text-slate-500 mt-1">Verificando API CVM na porta 8000...</p>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            {/* 1. Vencimento X Spread */}
                        {overviewCharts.vencimento_spread && (
                            <div className="glass-card rounded-2xl p-6 space-y-4 border border-slate-800/80 bg-gradient-to-br from-slate-900/90 to-slate-900/40">
                                <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800 pb-3 gap-2">
                                    <div>
                                        <h3 className="text-base font-bold text-white font-display flex items-center gap-2">
                                            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                                            Vencimento X Spread (% a.a.)
                                        </h3>
                                        <p className="text-xs text-slate-400">Correlação entre o ano de vencimento dos títulos e o spread médio indicativo (CDI+ e IPCA+)</p>
                                    </div>
                                    <div className="flex items-center space-x-4 text-xs font-mono">
                                        <span className="flex items-center space-x-1.5 text-indigo-400"><span className="w-3 h-3 rounded bg-indigo-500 inline-block"></span><span>CDI+ (% a.a.)</span></span>
                                        <span className="flex items-center space-x-1.5 text-amber-400"><span className="w-3 h-3 rounded bg-amber-500 inline-block"></span><span>IPCA+ (% a.a.)</span></span>
                                    </div>
                                </div>
                                <ChartWrapper
                                    type="bar"
                                    height={320}
                                    data={{
                                        labels: overviewCharts.vencimento_spread.labels,
                                        datasets: [
                                            { label: "CDI+ Spread (% a.a.)", data: overviewCharts.vencimento_spread.cdi_spread, backgroundColor: "#6366F1", borderRadius: 4 },
                                            { label: "IPCA+ Spread (% a.a.)", data: overviewCharts.vencimento_spread.ipca_spread, backgroundColor: "#F59E0B", borderRadius: 4 }
                                        ]
                                    }}
                                    options={{
                                        scales: {
                                            x: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                            y: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" }, callback: v => `${v}%` } }
                                        },
                                        plugins: { legend: { display: false } }
                                    }}
                                />
                            </div>
                        )}

                        {/* 2. Volume Emitido Indexado em cada B (NTN-B) */}
                        {overviewCharts.ntnb_volume && (
                            <div className="glass-card rounded-2xl p-6 space-y-4 border border-slate-800/80">
                                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                                    <div>
                                        <h3 className="text-base font-bold text-white font-display flex items-center gap-2">
                                            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                                            Volume Emitido Indexado por Referência NTN-B (R$ Bi)
                                        </h3>
                                        <p className="text-xs text-slate-400">Distribuição do volume de emissões atreladas à inflação (IPCA) por título público de referência (apuradas no Bookbuilding)</p>
                                    </div>
                                </div>
                                <ChartWrapper
                                    type="bar"
                                    height={280}
                                    data={{
                                        labels: overviewCharts.ntnb_volume.labels,
                                        datasets: [{
                                            label: "Volume Registrado (R$ Bi)",
                                            data: overviewCharts.ntnb_volume.volumes.map(v => (v / 1e9).toFixed(2)),
                                            backgroundColor: "#F59E0B",
                                            borderRadius: 6
                                        }]
                                    }}
                                    options={{
                                        scales: {
                                            x: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                            y: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" }, callback: v => `R$ ${v} Bi` } }
                                        },
                                        plugins: { legend: { display: false } }
                                    }}
                                />
                            </div>
                        )}

                        {/* 3. Histórico de volume de emissão mês a mês & Stacked Indexer */}
                        <div className="grid grid-cols-1 gap-6">
                            {overviewCharts.monthly_volume && (
                                <div className="glass-card rounded-2xl p-6 space-y-4">
                                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                                        <div>
                                            <h3 className="text-base font-bold text-white font-display">Histórico de Volume de Emissão Mês a Mês (R$ Bi)</h3>
                                            <p className="text-xs text-slate-400">Evolução mensal consolidada das ofertas públicas registradas</p>
                                        </div>
                                    </div>
                                    <ChartWrapper
                                        type="line"
                                        height={300}
                                        data={{
                                            labels: overviewCharts.monthly_volume.labels,
                                            datasets: [{
                                                label: "Volume Emitido (R$ Bi)",
                                                data: overviewCharts.monthly_volume.volumes.map(v => (v / 1e9).toFixed(2)),
                                                borderColor: "#3B82F6",
                                                backgroundColor: "rgba(59, 130, 246, 0.15)",
                                                fill: true,
                                                tension: 0.3,
                                                pointRadius: 4,
                                                pointBackgroundColor: "#3B82F6"
                                            }]
                                        }}
                                        options={{
                                            scales: {
                                                x: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                                y: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" }, callback: v => `R$ ${v} Bi` } }
                                            },
                                            plugins: { legend: { display: false } }
                                        }}
                                    />
                                </div>
                            )}

                            {/* Monthly Stacked Bar Chart */}
                            {overviewCharts.monthly_indexer && (
                                <div className="glass-card rounded-2xl p-6 space-y-4">
                                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                                        <div>
                                            <h3 className="text-base font-bold text-white font-display">Evolução Mensal do Volume por Indexador (R$ Bi)</h3>
                                            <p className="text-xs text-slate-400">Barras empilhadas exibindo a migração temporal entre CDI/DI, IPCA e PRÉ Prefixado</p>
                                        </div>
                                        <div className="flex items-center space-x-4 text-xs font-mono">
                                            <span className="flex items-center space-x-1.5 text-indigo-400"><span className="w-3 h-3 rounded bg-indigo-500 inline-block"></span><span>CDI/DI</span></span>
                                            <span className="flex items-center space-x-1.5 text-amber-400"><span className="w-3 h-3 rounded bg-amber-500 inline-block"></span><span>IPCA</span></span>
                                            <span className="flex items-center space-x-1.5 text-emerald-400"><span className="w-3 h-3 rounded bg-emerald-500 inline-block"></span><span>PRÉ</span></span>
                                        </div>
                                    </div>
                                    <ChartWrapper
                                        type="bar"
                                        height={340}
                                        data={{
                                            labels: overviewCharts.monthly_indexer.labels,
                                            datasets: [
                                                { label: "CDI / DI", data: overviewCharts.monthly_indexer.cdi.map(v => (v / 1e9).toFixed(2)), backgroundColor: "#6366F1", borderRadius: 4 },
                                                { label: "IPCA / Inflação", data: overviewCharts.monthly_indexer.ipca.map(v => (v / 1e9).toFixed(2)), backgroundColor: "#F59E0B", borderRadius: 4 },
                                                { label: "PRÉ (Prefixado)", data: overviewCharts.monthly_indexer.pre.map(v => (v / 1e9).toFixed(2)), backgroundColor: "#10B981", borderRadius: 4 }
                                            ]
                                        }}
                                        options={{
                                            scales: {
                                                x: { stacked: true, grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                                y: { stacked: true, grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" }, callback: v => `R$ ${v} Bi` } }
                                            },
                                            plugins: {
                                                legend: { display: false },
                                                tooltip: { mode: "index", intersect: false }
                                            }
                                        }}
                                    />
                                </div>
                            )}
                        </div>

                        {/* 4. Coordenadores e Emissores */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {overviewCharts.top_coordenadores && (
                                <div className="glass-card rounded-2xl p-6 space-y-4">
                                    <h3 className="text-base font-bold text-white font-display border-b border-slate-800 pb-3">Coordenadores Líderes por Volume Registrado (R$ Bi)</h3>
                                    <ChartWrapper
                                        type="bar"
                                        height={320}
                                        data={{
                                            labels: overviewCharts.top_coordenadores.labels,
                                            datasets: [{
                                                label: "Volume (R$ Bi)",
                                                data: overviewCharts.top_coordenadores.volumes.map(v => (v / 1e9).toFixed(2)),
                                                backgroundColor: "#8B5CF6",
                                                borderRadius: 6
                                            }]
                                        }}
                                        options={{
                                            indexAxis: "y",
                                            scales: {
                                                x: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                                y: { grid: { display: false }, ticks: { color: "#E2E8F0", font: { family: "Inter", size: 10 } } }
                                            },
                                            plugins: { legend: { display: false } }
                                        }}
                                    />
                                </div>
                            )}

                            {overviewCharts.top_emissores && (
                                <div className="glass-card rounded-2xl p-6 space-y-4">
                                    <h3 className="text-base font-bold text-white font-display border-b border-slate-800 pb-3">Maiores Emissores por Volume Registrado (R$ Bi)</h3>
                                    <ChartWrapper
                                        type="bar"
                                        height={320}
                                        data={{
                                            labels: overviewCharts.top_emissores.labels,
                                            datasets: [{
                                                label: "Volume (R$ Bi)",
                                                data: overviewCharts.top_emissores.volumes.map(v => (v / 1e9).toFixed(2)),
                                                backgroundColor: "#10B981",
                                                borderRadius: 6
                                            }]
                                        }}
                                        options={{
                                            indexAxis: "y",
                                            scales: {
                                                x: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                                y: { grid: { display: false }, ticks: { color: "#E2E8F0", font: { family: "Inter", size: 10 } } }
                                            },
                                            plugins: { legend: { display: false } }
                                        }}
                                    />
                                </div>
                            )}
                        </div>

                        {/* Top Ativos & Funil */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="glass-card rounded-2xl p-6 space-y-4">
                                <h3 className="text-base font-bold text-white font-display border-b border-slate-800 pb-3">Volume por Tipo de Ativo Mobiliário (R$ Bi)</h3>
                                <ChartWrapper
                                    type="bar"
                                    height={300}
                                    data={{
                                        labels: overviewCharts.top_ativos.labels,
                                        datasets: [{
                                            label: "Volume (R$ Bi)",
                                            data: overviewCharts.top_ativos.volumes.map(v => (v / 1e9).toFixed(2)),
                                            backgroundColor: "#3B82F6",
                                            borderRadius: 6
                                        }]
                                    }}
                                    options={{
                                        indexAxis: "y",
                                        scales: {
                                            x: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } },
                                            y: { grid: { display: false }, ticks: { color: "#E2E8F0", font: { family: "Inter" } } }
                                        },
                                        plugins: { legend: { display: false } }
                                    }}
                                />
                            </div>

                            <div className="glass-card rounded-2xl p-6 space-y-4">
                                <h3 className="text-base font-bold text-white font-display border-b border-slate-800 pb-3">Funil de Status das Ofertas na CVM</h3>
                                <ChartWrapper
                                    type="doughnut"
                                    height={300}
                                    data={{
                                        labels: overviewCharts.status_funnel.labels,
                                        datasets: [{
                                            data: overviewCharts.status_funnel.counts,
                                            backgroundColor: ["#6366F1", "#10B981", "#F59E0B", "#3B82F6", "#8B5CF6", "#64748B"]
                                        }]
                                    }}
                                    options={{
                                        plugins: {
                                            legend: { position: "right", labels: { color: "#E2E8F0", font: { family: "Inter", size: 11 }, usePointStyle: true } }
                                        }
                                    }}
                                />
                            </div>
                        </div>
                    </div>
                ))}

                {/* Tab 3: Investor Demographics */}
                {activeTab === "investors" && investorCharts && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="glass-card rounded-2xl p-6 space-y-4">
                            <h3 className="text-base font-bold text-white font-display border-b border-slate-800 pb-3">Demografia e Alocação de Investidores (R$ Bi)</h3>
                            <ChartWrapper
                                type="bar"
                                height={320}
                                data={{
                                    labels: investorCharts.demographics.labels,
                                    datasets: [{
                                        label: "Volume Alocado (R$ Bi)",
                                        data: investorCharts.demographics.values.map(v => (v / 1e9).toFixed(2)),
                                        backgroundColor: ["#10B981", "#6366F1", "#3B82F6", "#8B5CF6"],
                                        borderRadius: 8
                                    }]
                                }}
                                options={{
                                    scales: {
                                        x: { grid: { display: false }, ticks: { color: "#E2E8F0" } },
                                        y: { grid: { color: "#1E293B" }, ticks: { color: "#94A3B8", font: { family: "JetBrains Mono" } } }
                                    },
                                    plugins: { legend: { display: false } }
                                }}
                            />
                        </div>

                        <div className="glass-card rounded-2xl p-6 space-y-4">
                            <h3 className="text-base font-bold text-white font-display border-b border-slate-800 pb-3">Share (%) Real Confirmado no Varejo vs Fundos</h3>
                            <ChartWrapper
                                type="pie"
                                height={320}
                                data={{
                                    labels: investorCharts.demographics.labels,
                                    datasets: [{
                                        data: investorCharts.demographics.values,
                                        backgroundColor: ["#10B981", "#6366F1", "#3B82F6", "#8B5CF6"]
                                    }]
                                }}
                                options={{
                                    plugins: {
                                        legend: { position: "bottom", labels: { color: "#E2E8F0", usePointStyle: true } }
                                    }
                                }}
                            />
                        </div>
                    </div>
                )}
            </main>

            {/* Slide-over Drawer Dossier */}
            <DrawerLateralDossie
                offer={selectedOffer}
                onClose={() => setSelectedOffer(null)}
                onNavigate={handleDrawerNavigate}
                totalItems={offersData.items.length}
                currentIndex={selectedOffer ? offersData.items.findIndex(o => o.Id_Processo === selectedOffer.Id_Processo) : -1}
                onUpdateOffer={(updated) => {
                    setOffersData(prev => ({
                        ...prev,
                        items: prev.items.map(it => it.Id_Processo === updated.Id_Processo ? updated : it)
                    }));
                }}
            />

            {/* Footer */}
            <footer className="glass-header mt-auto py-6 px-6 text-center text-xs text-slate-500 font-mono">
                <p>CVM Primários Monitor PRO © 2026 • Auditoria em Tempo Real • Conforme Resoluções CVM 160, ICVM 400 e 476</p>
            </footer>
        </div>
    );
};

export default App;
