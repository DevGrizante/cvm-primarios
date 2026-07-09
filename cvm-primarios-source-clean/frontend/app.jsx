const { useState, useEffect, useRef } = React;

// Helper to format currency
const formatCurrency = (val) => {
    if (!val || val === 0) return "R$ 0,00";
    if (val >= 1e12) return `R$ ${(val / 1e12).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Tri`;
    if (val >= 1e9) return `R$ ${(val / 1e9).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Bi`;
    if (val >= 1e6) return `R$ ${(val / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Mi`;
    return `R$ ${val.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatNumber = (val) => {
    if (!val && val !== 0) return "0";
    return val.toLocaleString("pt-BR");
};

// Chart.js Component Wrapper
const ChartWrapper = ({ type, data, options, height = 300 }) => {
    const canvasRef = useRef(null);
    const chartInstance = useRef(null);

    useEffect(() => {
        if (!canvasRef.current) return;
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
    }, [type, JSON.stringify(data), JSON.stringify(options)]);

    return (
        <div style={{ height: `${height}px`, width: '100%' }}>
            <canvas ref={canvasRef}></canvas>
        </div>
    );
};

// React Error Boundary to prevent black screens (tela preta) during tab switching or rendering
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }
    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }
    componentDidCatch(error, errorInfo) {
        console.error("Tab ErrorBoundary caught error:", error, errorInfo);
    }
    render() {
        if (this.state.hasError) {
            return (
                <div className="glass-card rounded-2xl p-8 border border-red-500/40 bg-red-950/20 text-center max-w-xl mx-auto my-12 space-y-4 shadow-2xl animate-fadeIn">
                    <span className="text-4xl block">⚠️</span>
                    <h3 className="font-display font-bold text-lg text-white">Ocorreu um imprevisto ao renderizar os dados desta aba</h3>
                    <p className="text-xs text-red-300 font-mono bg-slate-950/80 p-3 rounded-xl border border-red-500/20 overflow-x-auto text-left">
                        {this.state.error?.toString() || "Erro de execução de script."}
                    </p>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg transition"
                    >
                        Tentar Recarregar Aba 🔄
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

// Main App
const App = () => {
    const [status, setStatus] = useState({ status: "loading", rows_count: 0, last_update: "", options: {} });
    const [filters, setFilters] = useState({
        ano: "Recentes (2023-2026)",
        rito: "Todos",
        ativo: "Todos",
        status: "Todos",
        indexador: "Todos",
        publico: "Todos",
        busca: ""
    });
    const [tableSearch, setTableSearch] = useState("");
    const [pageSize, setPageSize] = useState(25);
    const [currentPage, setCurrentPage] = useState(1);
    const [activeTab, setActiveTab] = useState("explorer"); // Defaulting to Explorer/Tabela Completa to match user priority
    const [kpis, setKpis] = useState(null);
    const [overviewCharts, setOverviewCharts] = useState(null);
    const [investorCharts, setInvestorCharts] = useState(null);
    const [rankings, setRankings] = useState(null);
    const [offersData, setOffersData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
    const [selectedOffer, setSelectedOffer] = useState(null);
    const [loading, setLoading] = useState(true);

    // Initial status fetch
    useEffect(() => {
        fetch("/api/status")
            .then(r => r.json())
            .then(data => {
                setStatus(data);
            })
            .catch(e => console.error("Error loading status:", e));
    }, []);

    // Fetch data when filters or pagination change
    useEffect(() => {
        setLoading(true);
        const effectiveSearch = filters.busca || tableSearch;
        const queryParams = new URLSearchParams({
            ano: filters.ano,
            rito: filters.rito,
            ativo: filters.ativo,
            status: filters.status,
            indexador: filters.indexador,
            publico: filters.publico,
            busca: effectiveSearch
        }).toString();

        Promise.all([
            fetch(`/api/kpis?${queryParams}`).then(r => r.json()),
            fetch(`/api/charts/overview?${queryParams}`).then(r => r.json()),
            fetch(`/api/charts/investors?${queryParams}`).then(r => r.json()),
            fetch(`/api/rankings?${queryParams}&limit=15`).then(r => r.json()),
            fetch(`/api/offers?${queryParams}&page=${currentPage}&page_size=${pageSize}`).then(r => r.json())
        ]).then(([kpisData, overviewData, investorsData, rankingsData, offersResp]) => {
            setKpis(kpisData);
            setOverviewCharts(overviewData);
            setInvestorCharts(investorsData);
            setRankings(rankingsData);
            setOffersData(offersResp);
            
            // If no offer is currently selected for the details tab, pick the first item
            if (!selectedOffer && offersResp.items && offersResp.items.length > 0) {
                setSelectedOffer(offersResp.items[0]);
            }
            setLoading(false);
        }).catch(e => {
            console.error("Error loading dashboard data:", e);
            setLoading(false);
        });
    }, [filters, currentPage, pageSize, tableSearch]);

    const handleFilterChange = (key, val) => {
        setCurrentPage(1);
        setFilters(prev => ({ ...prev, [key]: val }));
    };

    const handleClearFilters = () => {
        setCurrentPage(1);
        setTableSearch("");
        setFilters({
            ano: "Recentes (2023-2026)",
            rito: "Todos",
            ativo: "Todos",
            status: "Todos",
            indexador: "Todos",
            publico: "Todos",
            busca: ""
        });
    };

    const handleExport = () => {
        const effectiveSearch = filters.busca || tableSearch;
        const queryParams = new URLSearchParams({
            ano: filters.ano,
            rito: filters.rito,
            ativo: filters.ativo,
            status: filters.status,
            indexador: filters.indexador,
            publico: filters.publico,
            busca: effectiveSearch
        }).toString();
        window.location.href = `/api/export?${queryParams}`;
    };

    const openDetailsTab = (offer) => {
        setSelectedOffer(offer);
        setActiveTab("details");
    };

    // Indexer badge color formatting
    const getIndexerBadge = (idx) => {
        if (idx === "IPCA / Inflação") return "bg-amber-500/15 text-amber-400 border border-amber-500/30";
        if (idx === "CDI / DI") return "bg-indigo-500/15 text-indigo-400 border border-indigo-500/30";
        if (idx === "PRÉ (Prefixado)") return "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30";
        return "bg-slate-800 text-slate-400 border border-slate-700";
    };

    return (
        <div className="min-h-screen flex flex-col">
            {/* Header / Navbar */}
            <header className="glass-header sticky top-0 z-50 px-6 py-4">
                <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cvm-indigo to-cvm-blue flex items-center justify-center text-white font-display font-bold text-lg shadow-lg shadow-cvm-indigo/30">
                            CVM
                        </div>
                        <div>
                            <h1 className="font-display font-bold text-xl tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                                Primários Monitor <span className="text-cvm-indigo font-extrabold">PRO</span>
                            </h1>
                            <p className="text-xs text-slate-400 flex items-center gap-2">
                                <span className="inline-block w-2 h-2 rounded-full bg-cvm-emerald animate-pulse"></span>
                                Base Oficial da CVM ({formatNumber(status.rows_count)} emissões cadastradas)
                                {status.last_update && <span className="text-slate-500">• Atualizado em {status.last_update}</span>}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <input
                                type="text"
                                placeholder="Buscar emissor, líder ou processo..."
                                value={filters.busca}
                                onChange={(e) => handleFilterChange("busca", e.target.value)}
                                className="bg-slate-900/80 border border-slate-700/60 rounded-lg px-3 py-1.5 pl-8 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cvm-indigo focus:ring-1 focus:ring-cvm-indigo transition w-64"
                            />
                            <svg className="w-4 h-4 text-slate-500 absolute left-2.5 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                            </svg>
                        </div>

                        <button
                            onClick={handleClearFilters}
                            className="glass-pill px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white flex items-center gap-1.5 transition"
                            title="Limpar todos os filtros"
                        >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                            </svg>
                            Limpar
                        </button>

                        <button
                            onClick={handleExport}
                            className="bg-gradient-to-r from-cvm-indigo to-cvm-blue hover:from-cvm-indigo/90 hover:to-cvm-blue/90 text-white font-medium text-xs px-4 py-2 rounded-lg shadow-lg shadow-cvm-indigo/20 flex items-center gap-1.5 transition active:scale-95"
                        >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                            </svg>
                            Exportar CSV
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 space-y-6">
                
                {/* Filter Bar with new IPCA / CDI / PRÉ quick filter */}
                <section className="glass-card rounded-2xl p-4 border border-slate-800/80">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="flex flex-wrap items-center gap-2.5">
                            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                <svg className="w-3.5 h-3.5 text-cvm-indigo" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                                </svg>
                                Filtros:
                            </span>

                            {/* Ano */}
                            <div className="flex items-center gap-1 bg-slate-900/60 rounded-lg p-1 border border-slate-800">
                                <span className="text-xs text-slate-500 px-2 font-medium">Período:</span>
                                <select
                                    value={filters.ano}
                                    onChange={(e) => handleFilterChange("ano", e.target.value)}
                                    className="bg-transparent text-xs font-medium text-slate-200 focus:outline-none cursor-pointer pr-4"
                                >
                                    {(status.options?.anos || ["Recentes (2023-2026)", "Todos"]).map(a => (
                                        <option key={a} value={a} className="bg-cvm-dark text-slate-200">{a}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Rito */}
                            <div className="flex items-center gap-1 bg-slate-900/60 rounded-lg p-1 border border-slate-800">
                                <span className="text-xs text-slate-500 px-2 font-medium">Rito:</span>
                                <select
                                    value={filters.rito}
                                    onChange={(e) => handleFilterChange("rito", e.target.value)}
                                    className="bg-transparent text-xs font-medium text-slate-200 focus:outline-none cursor-pointer pr-4"
                                >
                                    {(status.options?.ritos || ["Todos", "Automático", "Ordinário"]).map(r => (
                                        <option key={r} value={r} className="bg-cvm-dark text-slate-200">{r}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Ativo */}
                            <div className="flex items-center gap-1 bg-slate-900/60 rounded-lg p-1 border border-slate-800 max-w-xs">
                                <span className="text-xs text-slate-500 px-2 font-medium">Ativo:</span>
                                <select
                                    value={filters.ativo}
                                    onChange={(e) => handleFilterChange("ativo", e.target.value)}
                                    className="bg-transparent text-xs font-medium text-slate-200 focus:outline-none cursor-pointer pr-4 truncate max-w-[150px]"
                                >
                                    {(status.options?.ativos || ["Todos"]).map(at => (
                                        <option key={at} value={at} className="bg-cvm-dark text-slate-200 truncate">{at}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Status */}
                            <div className="flex items-center gap-1 bg-slate-900/60 rounded-lg p-1 border border-slate-800">
                                <span className="text-xs text-slate-500 px-2 font-medium">Status:</span>
                                <select
                                    value={filters.status}
                                    onChange={(e) => handleFilterChange("status", e.target.value)}
                                    className="bg-transparent text-xs font-medium text-slate-200 focus:outline-none cursor-pointer pr-4"
                                >
                                    {(status.options?.status || ["Todos"]).map(s => (
                                        <option key={s} value={s} className="bg-cvm-dark text-slate-200">{s}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Painel de Filtros Rápidos - Remuneração e Tipo de Emissão */}
                        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/60">
                            {/* Rápido: Tipo da Emissão (DEB / CRI / CRA / FIDC) */}
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[11px] font-semibold text-slate-400 mr-1 flex items-center gap-1">
                                    🏷️ Tipo Rápido:
                                </span>
                                <button
                                    onClick={() => handleFilterChange("ativo", filters.ativo === "DEB" ? "Todos" : "DEB")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition flex items-center gap-1 ${filters.ativo === "DEB" ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30 border border-indigo-400" : "bg-slate-900 text-indigo-300 border border-indigo-500/30 hover:bg-slate-800"}`}
                                >
                                    DEB
                                </button>
                                <button
                                    onClick={() => handleFilterChange("ativo", filters.ativo === "CRI" ? "Todos" : "CRI")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition flex items-center gap-1 ${filters.ativo === "CRI" ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30 border border-indigo-400" : "bg-slate-900 text-indigo-300 border border-indigo-500/30 hover:bg-slate-800"}`}
                                >
                                    CRI
                                </button>
                                <button
                                    onClick={() => handleFilterChange("ativo", filters.ativo === "CRA" ? "Todos" : "CRA")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition flex items-center gap-1 ${filters.ativo === "CRA" ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30 border border-indigo-400" : "bg-slate-900 text-indigo-300 border border-indigo-500/30 hover:bg-slate-800"}`}
                                >
                                    CRA
                                </button>
                                <button
                                    onClick={() => handleFilterChange("ativo", filters.ativo === "FIDC" ? "Todos" : "FIDC")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition flex items-center gap-1 ${filters.ativo === "FIDC" ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30 border border-indigo-400" : "bg-slate-900 text-indigo-300 border border-indigo-500/30 hover:bg-slate-800"}`}
                                >
                                    FIDC
                                </button>
                                {filters.ativo !== "Todos" && (
                                    <button
                                        onClick={() => handleFilterChange("ativo", "Todos")}
                                        className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 hover:text-white transition"
                                        title="Limpar filtro de tipo"
                                    >
                                        ✕ Limpar Tipo
                                    </button>
                                )}
                            </div>

                            {/* Rápido: Remuneração / Indexador (CDI / IPCA / PRÉ) */}
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[11px] font-semibold text-slate-400 mr-1 flex items-center gap-1">
                                    ⚡ Remuneração Rápida:
                                </span>
                                <button
                                    onClick={() => handleFilterChange("indexador", filters.indexador === "CDI / DI" ? "Todos" : "CDI / DI")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition ${filters.indexador === "CDI / DI" ? "bg-blue-600 text-white shadow-md shadow-blue-600/30 border border-blue-400" : "bg-slate-900 text-blue-400 border border-blue-500/30 hover:bg-slate-800"}`}
                                >
                                    CDI
                                </button>
                                <button
                                    onClick={() => handleFilterChange("indexador", filters.indexador === "IPCA / Inflação" ? "Todos" : "IPCA / Inflação")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition ${filters.indexador === "IPCA / Inflação" ? "bg-amber-600 text-white shadow-md shadow-amber-600/30 border border-amber-400" : "bg-slate-900 text-amber-400 border border-amber-500/30 hover:bg-slate-800"}`}
                                >
                                    IPCA
                                </button>
                                <button
                                    onClick={() => handleFilterChange("indexador", filters.indexador === "PRÉ (Prefixado)" ? "Todos" : "PRÉ (Prefixado)")}
                                    className={`px-2.5 py-1 rounded text-xs font-bold transition ${filters.indexador === "PRÉ (Prefixado)" ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/30 border border-emerald-400" : "bg-slate-900 text-emerald-400 border border-emerald-500/30 hover:bg-slate-800"}`}
                                >
                                    PRÉ
                                </button>
                                {filters.indexador !== "Todos" && (
                                    <button
                                        onClick={() => handleFilterChange("indexador", "Todos")}
                                        className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 hover:text-white transition"
                                        title="Limpar filtro de indexador"
                                    >
                                        ✕ Limpar Taxa
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </section>

                {/* KPI Cards */}
                {kpis && (
                    <section className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                        <div className="glass-card rounded-2xl p-5 border border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-24 h-24 bg-cvm-indigo/10 rounded-full blur-xl group-hover:bg-cvm-indigo/20 transition"></div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Volume Registrado</p>
                            <h3 className="font-display font-bold text-2xl text-white tracking-tight">
                                {formatCurrency(kpis.volume_total)}
                            </h3>
                            <p className="text-xs text-cvm-emerald font-medium mt-2 flex items-center gap-1">
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                                100% de cobertura oficial CVM
                            </p>
                        </div>

                        <div className="glass-card rounded-2xl p-5 border border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-24 h-24 bg-cvm-blue/10 rounded-full blur-xl group-hover:bg-cvm-blue/20 transition"></div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Qtd. de Ofertas</p>
                            <h3 className="font-display font-bold text-2xl text-white tracking-tight">
                                {formatNumber(kpis.qtd_ofertas)} <span className="text-sm font-normal text-slate-400">emissões</span>
                            </h3>
                            <p className="text-xs text-slate-400 mt-2">
                                {filters.indexador !== "Todos" ? `Filtrado por: ${filters.indexador}` : "Filtradas no período atual"}
                            </p>
                        </div>

                        <div className="glass-card rounded-2xl p-5 border border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-24 h-24 bg-cvm-emerald/10 rounded-full blur-xl group-hover:bg-cvm-emerald/20 transition"></div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Rito Automático</p>
                            <h3 className="font-display font-bold text-2xl text-cvm-emerald tracking-tight">
                                {kpis.taxa_auto}%
                            </h3>
                            <p className="text-xs text-slate-400 mt-2">
                                Agilidade no registro (RCVM 160)
                            </p>
                        </div>

                        <div className="glass-card rounded-2xl p-5 border border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-24 h-24 bg-cvm-purple/10 rounded-full blur-xl group-hover:bg-cvm-purple/20 transition"></div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Ticket Médio</p>
                            <h3 className="font-display font-bold text-2xl text-white tracking-tight">
                                {formatCurrency(kpis.ticket_medio)}
                            </h3>
                            <p className="text-xs text-slate-400 mt-2">
                                Por oferta registrada
                            </p>
                        </div>

                        <div className="glass-card rounded-2xl p-5 border border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-24 h-24 bg-cvm-gold/10 rounded-full blur-xl group-hover:bg-cvm-gold/20 transition"></div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Alocação Varejo (PF)</p>
                            <h3 className="font-display font-bold text-2xl text-cvm-gold tracking-tight">
                                {kpis.taxa_varejo}%
                            </h3>
                            <p className="text-xs text-slate-400 mt-2">
                                Participação de Pessoas Físicas
                            </p>
                        </div>
                    </section>
                )}

                {/* Navigation Tabs including dedicated Detalhes da Emissão */}
                <div className="flex flex-wrap border-b border-slate-800 gap-6 px-2">
                    <button
                        onClick={() => setActiveTab("explorer")}
                        className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 transition ${activeTab === "explorer" ? "active text-cvm-indigo" : "text-slate-400 hover:text-slate-200"}`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        📋 Tabela Completa (Explorer)
                    </button>
                    
                    <button
                        onClick={() => setActiveTab("details")}
                        className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 transition ${activeTab === "details" ? "active text-cvm-emerald" : "text-slate-400 hover:text-slate-200"}`}
                    >
                        <svg className="w-4 h-4 text-cvm-emerald animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        📑 Detalhes Específicos da Emissão
                    </button>

                    <button
                        onClick={() => setActiveTab("overview")}
                        className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 transition ${activeTab === "overview" ? "active text-cvm-indigo" : "text-slate-400 hover:text-slate-200"}`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                        Visão Geral & Tendências
                    </button>

                    <button
                        onClick={() => setActiveTab("investors")}
                        className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 transition ${activeTab === "investors" ? "active text-cvm-indigo" : "text-slate-400 hover:text-slate-200"}`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                        Demografia de Investidores
                    </button>

                    <button
                        onClick={() => setActiveTab("rankings")}
                        className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 transition ${activeTab === "rankings" ? "active text-cvm-indigo" : "text-slate-400 hover:text-slate-200"}`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path></svg>
                        Rankings (Coordenadores & Emissores)
                    </button>
                </div>

                <ErrorBoundary key={activeTab}>
                {/* Tab 1: Tabela Completa (Explorer) exactly styled like the user screenshot */}
                {activeTab === "explorer" && (
                    <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-5 animate-fadeIn">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                            <div>
                                <h3 className="font-display font-bold text-xl text-white flex items-center gap-2.5">
                                    <span className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">📋</span>
                                    Tabela Completa
                                </h3>
                                <p className="text-xs text-slate-400 mt-1">
                                    Clique em uma linha para ver os detalhes completos da emissão (ou na aba 📑 Detalhes Específicos da Emissão).
                                </p>
                            </div>

                            <div className="flex items-center gap-3">
                                <span className="text-xs font-mono bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800 text-slate-300">
                                    Total filtrado: <strong className="text-white">{formatNumber(offersData.total)}</strong> registros
                                </span>
                            </div>
                        </div>

                        {/* Search Input matching screenshot */}
                        <div className="relative">
                            <input
                                type="text"
                                placeholder="Buscar (emissor, coordenador, status... Ex: Bradesco, Debêntures, Concluído...)"
                                value={tableSearch}
                                onChange={(e) => {
                                    setCurrentPage(1);
                                    setTableSearch(e.target.value);
                                }}
                                className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-3 pl-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition shadow-inner"
                            />
                            <svg className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                            </svg>
                            {tableSearch && (
                                <button onClick={() => setTableSearch("")} className="absolute right-3.5 top-3.5 text-slate-500 hover:text-white text-xs">
                                    ✕ Limpar
                                </button>
                            )}
                        </div>

                        {/* Pagination Bar top matching screenshot */}
                        <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/50 p-3 rounded-xl border border-slate-800/80">
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-slate-400 font-medium">Página (de {offersData.total_pages})</span>
                                <div className="flex items-center bg-slate-950 rounded-lg border border-slate-800">
                                    <button
                                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                                        disabled={currentPage <= 1}
                                        className="px-2.5 py-1 text-slate-400 hover:text-white disabled:opacity-30 border-r border-slate-800 transition text-sm font-bold"
                                    >
                                        −
                                    </button>
                                    <span className="px-3 py-1 text-xs font-mono font-bold text-indigo-400">{currentPage}</span>
                                    <button
                                        onClick={() => setCurrentPage(prev => Math.min(offersData.total_pages, prev + 1))}
                                        disabled={currentPage >= offersData.total_pages}
                                        className="px-2.5 py-1 text-slate-400 hover:text-white disabled:opacity-30 border-l border-slate-800 transition text-sm font-bold"
                                    >
                                        +
                                    </button>
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <span className="text-xs text-slate-400">Registros por página:</span>
                                <select
                                    value={pageSize}
                                    onChange={(e) => {
                                        setPageSize(Number(e.target.value));
                                        setCurrentPage(1);
                                    }}
                                    className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1 text-xs text-slate-200 focus:outline-none cursor-pointer"
                                >
                                    <option value={15}>15</option>
                                    <option value={25}>25</option>
                                    <option value={50}>50</option>
                                    <option value={100}>100</option>
                                </select>
                            </div>
                        </div>

                        {/* Table */}
                        <div className="overflow-x-auto max-h-[650px] border border-slate-800 rounded-xl shadow-xl">
                            <table className="w-full text-left text-xs data-grid">
                                <thead>
                                    <tr className="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/90">
                                        <th className="py-3.5 px-3 whitespace-nowrap">Data</th>
                                        <th className="py-3.5 px-3">Emissor</th>
                                        <th className="py-3.5 px-3 whitespace-nowrap">Ativo</th>
                                        <th className="py-3.5 px-3 whitespace-nowrap text-center">Indexador / Taxa</th>
                                        <th className="py-3.5 px-3 text-right whitespace-nowrap">Volume</th>
                                        <th className="py-3.5 px-3">Coordenador</th>
                                        <th className="py-3.5 px-3 text-center whitespace-nowrap">Status</th>
                                        <th className="py-3.5 px-3 text-center whitespace-nowrap">Processo / Rito</th>
                                        <th className="py-3.5 px-3 text-center whitespace-nowrap">Raio-X</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/60">
                                    {offersData.items.map((offer, idx) => (
                                        <tr
                                            key={idx}
                                            className="hover:bg-indigo-950/30 transition cursor-pointer"
                                            onClick={() => openDetailsTab(offer)}
                                        >
                                            <td className="py-3.5 px-3 font-mono text-slate-400 whitespace-nowrap">{offer.Data_Clean}</td>
                                            <td className="py-3.5 px-3 font-medium text-white max-w-[220px] truncate" title={offer.Emissor}>{offer.Emissor}</td>
                                            <td className="py-3.5 px-3 text-indigo-400 font-semibold whitespace-nowrap">{offer.Ativo}</td>
                                            
                                            {/* INDEXADOR BADGE IN TABLE */}
                                            <td className="py-3.5 px-3 text-center whitespace-nowrap">
                                                <span className={`px-2.5 py-1 rounded-md text-[11px] font-bold shadow-sm inline-flex items-center gap-1 ${getIndexerBadge(offer.Indexador)}`} title={offer.Taxa_Juros || offer.Indexador}>
                                                    {offer.Taxa_Juros && offer.Taxa_Juros.includes("+") && <span className="text-[10px]">⚡</span>}
                                                    {offer.Taxa_Juros && offer.Taxa_Juros !== "Outros / Não Informado" ? (offer.Taxa_Juros.length > 24 ? offer.Taxa_Juros.slice(0, 24) + '...' : offer.Taxa_Juros) : (offer.Indexador === "Outros / Não Informado" ? "Outros/Flutuante" : offer.Indexador)}
                                                </span>
                                            </td>

                                            <td className="py-3.5 px-3 text-right font-mono font-bold text-emerald-400 whitespace-nowrap">
                                                <span>{formatCurrency(offer.Volume_Float)}</span>
                                                {offer.Is_Estimated_Vol && (
                                                    <span className="block text-[9px] text-amber-300 font-sans tracking-tight" title="Volume Alvo estimado - Oferta em Bookbuilding / Análise CVM">
                                                        ⚡ Alvo (Bookbuilding)
                                                    </span>
                                                )}
                                            </td>
                                            <td className="py-3.5 px-3 text-slate-300 max-w-[190px] truncate" title={offer.Lider}>{offer.Lider}</td>
                                            
                                            <td className="py-3.5 px-3 text-center whitespace-nowrap">
                                                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900 text-slate-300 border border-slate-700">
                                                    {offer.Status}
                                                </span>
                                            </td>

                                            <td className="py-3.5 px-3 text-center whitespace-nowrap text-slate-400">
                                                <span className="block font-mono text-[11px]" title={offer.Id_Processo}>
                                                    {offer.Id_Processo.length > 15 ? offer.Id_Processo.slice(0, 15) + '...' : offer.Id_Processo}
                                                </span>
                                                <span className="text-[10px] text-slate-500">{offer.Rito}</span>
                                            </td>

                                            <td className="py-3.5 px-3 text-center whitespace-nowrap" onClick={(e) => { e.stopPropagation(); openDetailsTab(offer); }}>
                                                <button className="text-white bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 rounded-md text-[11px] font-bold shadow-md transition flex items-center gap-1 mx-auto">
                                                    Ver Detalhes 📑
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Bottom pagination info matching screenshot footer */}
                        <div className="flex items-center justify-between text-xs text-slate-400 px-1 pt-1">
                            <span>
                                Página <strong className="text-white">{currentPage}</strong>/{offersData.total_pages} — registros {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, offersData.total)} de {formatNumber(offersData.total)}
                            </span>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                                    disabled={currentPage <= 1}
                                    className="px-3 py-1 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 disabled:opacity-30 text-slate-300 transition"
                                >
                                    ← Anterior
                                </button>
                                <button
                                    onClick={() => setCurrentPage(prev => Math.min(offersData.total_pages, prev + 1))}
                                    disabled={currentPage >= offersData.total_pages}
                                    className="px-3 py-1 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 disabled:opacity-30 text-slate-300 transition"
                                >
                                    Próxima →
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Tab 2: DEDICATED TAB FOR SPECIFIC EMISSION DETAILS (📑 Detalhes Específicos da Emissão) */}
                {activeTab === "details" && (
                    <div className="space-y-6 animate-fadeIn">
                        {/* Selector / Search inside Details tab */}
                        <div className="glass-card rounded-2xl p-5 border border-slate-800 flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-indigo-950/20 to-slate-900">
                            <div className="flex items-center gap-3">
                                <span className="w-11 h-11 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xl font-bold shadow-inner">
                                    📑
                                </span>
                                <div>
                                    <h3 className="font-display font-bold text-lg text-white">Dossiê e Raio-X Específico da Emissão</h3>
                                    <p className="text-xs text-slate-400">Inspecione os parâmetros jurídicos, fiduciários, lastro, indexador e alocação de investidores</p>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <span className="text-xs text-slate-400">Emissão Inspecionada:</span>
                                <select
                                    value={selectedOffer ? selectedOffer.Id_Processo : ""}
                                    onChange={(e) => {
                                        const found = offersData.items.find(it => it.Id_Processo === e.target.value);
                                        if (found) setSelectedOffer(found);
                                    }}
                                    className="bg-slate-950 border border-indigo-500/50 rounded-xl px-4 py-2 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 max-w-sm truncate"
                                >
                                    {offersData.items.map((it, idx) => (
                                        <option key={idx} value={it.Id_Processo} className="bg-slate-900 text-white">
                                            {it.Emissor} ({it.Ativo} — {formatCurrency(it.Volume_Float)})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {selectedOffer ? (
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                {/* Left Column: Identity & Financial Summary */}
                                <div className="space-y-6 lg:col-span-1">
                                    <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-4">
                                        <div className="border-b border-slate-800 pb-4">
                                            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-full border border-indigo-500/20">
                                                {selectedOffer.Regime}
                                            </span>
                                            <h2 className="font-display font-bold text-xl text-white mt-3 leading-snug">
                                                {selectedOffer.Emissor}
                                            </h2>
                                            <p className="text-xs font-mono text-slate-400 mt-1">CNPJ: {selectedOffer.CNPJ_Emissor}</p>
                                        </div>

                                        <div className="space-y-3 text-xs">
                                            <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                                                <span className="text-slate-400">Processo CVM:</span>
                                                <span className="font-mono font-bold text-white">{selectedOffer.Id_Processo}</span>
                                            </div>
                                            <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                                                <span className="text-slate-400">Processo SEI:</span>
                                                <span className="font-mono text-slate-200">{selectedOffer.Processo_SEI}</span>
                                            </div>
                                            <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                                                <span className="text-slate-400">Data do Registro:</span>
                                                <span className="font-mono font-semibold text-slate-200">{selectedOffer.Data_Clean}</span>
                                            </div>
                                            <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                                                <span className="text-slate-400">Rito / Procedimento:</span>
                                                <span className="font-semibold text-emerald-400">{selectedOffer.Rito}</span>
                                            </div>
                                            <div className="flex justify-between items-center py-1">
                                                <span className="text-slate-400">Status CVM:</span>
                                                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-800 text-slate-200 border border-slate-700">
                                                    {selectedOffer.Status}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Financial & Indexer Card */}
                                    <div className="glass-card rounded-2xl p-6 border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 space-y-4">
                                        <h4 className="font-display font-bold text-sm text-white uppercase tracking-wider flex items-center gap-2">
                                            <span>💰</span> Estrutura Financeira & Indexador
                                        </h4>

                                        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                                            <div>
                                                <span className="text-[11px] text-slate-400">Tipo do Ativo / Título:</span>
                                                <p className="font-display font-bold text-base text-indigo-400 mt-0.5">{selectedOffer.Ativo}</p>
                                            </div>

                                            <div className="pt-2 border-t border-slate-800/80">
                                                <span className="text-[11px] text-slate-400">Indexador / Remuneração da Emissão:</span>
                                                <div className="mt-1 flex items-center gap-2 flex-wrap">
                                                    <span className={`px-3.5 py-1.5 rounded-lg text-xs font-extrabold shadow-md inline-flex items-center gap-1.5 ${getIndexerBadge(selectedOffer.Indexador)}`} title="Taxa ou Remuneração declarada">
                                                        <span>⚡</span>
                                                        <span>{selectedOffer.Taxa_Juros && selectedOffer.Taxa_Juros !== "Outros / Não Informado" ? selectedOffer.Taxa_Juros : selectedOffer.Indexador}</span>
                                                    </span>
                                                    {selectedOffer.Is_Estimated_Vol && (
                                                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                                            Aguardando Bookbuilding (Est. CVM)
                                                        </span>
                                                    )}
                                                </div>
                                                {selectedOffer.Taxa_Juros && selectedOffer.Taxa_Juros.includes("+") && (
                                                    <p className="text-[11px] text-slate-400 mt-1.5 bg-slate-900/90 p-2 rounded-lg border border-slate-800/80 font-sans">
                                                        💡 <strong className="text-slate-200">Estrutura de Remuneração:</strong> Taxa base atrelada ao <span className="text-indigo-400 font-semibold">{selectedOffer.Indexador}</span> acrescida do spread/sobretaxa (<span className="text-emerald-400 font-bold font-mono">{selectedOffer.Taxa_Juros.split('+')[1]?.trim() || 'Spread'}</span>).
                                                    </p>
                                                )}
                                            </div>

                                            <div className="pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-3">
                                                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-[10px] text-slate-400">Volume Total da Oferta</span>
                                                        {selectedOffer.Is_Estimated_Vol && <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/30 text-amber-200 font-bold">ALVO</span>}
                                                    </div>
                                                    <p className="font-mono font-bold text-sm text-emerald-400 mt-0.5">{formatCurrency(selectedOffer.Volume_Float)}</p>
                                                </div>
                                                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
                                                    <span className="text-[10px] text-slate-400">Quantidade Registrada</span>
                                                    <p className="font-mono font-bold text-sm text-slate-200 mt-0.5">{formatNumber(selectedOffer.Qtde_Float)} <span className="text-[10px] font-normal text-slate-400">títulos</span></p>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                            <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                <span className="text-[10px] text-slate-400 block">Selo Sustentável / ESG</span>
                                                <span className={`font-bold ${selectedOffer.ESG === "Sim" ? "text-emerald-400" : "text-slate-300"}`}>
                                                    {selectedOffer.ESG === "Sim" ? "🌿 Sim (Green Bond)" : "Não"}
                                                </span>
                                            </div>
                                            <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                <span className="text-[10px] text-slate-400 block">Título Incentivado</span>
                                                <span className={`font-bold ${selectedOffer.Titulo_Incentivado === "Sim" ? "text-amber-400" : "text-slate-300"}`}>
                                                    {selectedOffer.Titulo_Incentivado === "Sim" ? "⚡ Sim (Lei 12.431)" : "Não"}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Right Column: Deep Governance, Consórcio and Legal Texts */}
                                <div className="space-y-6 lg:col-span-2">
                                    {/* Consórcio & Governança */}
                                    <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-4">
                                        <h4 className="font-display font-bold text-base text-white flex items-center gap-2 border-b border-slate-800 pb-3">
                                            <span>🏛️</span> Consórcio de Distribuição, Fiduciário & Prestadores
                                        </h4>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                                            <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 space-y-1">
                                                <span className="text-[11px] font-semibold text-indigo-400 uppercase">Coordenador Líder</span>
                                                <p className="font-bold text-white text-sm">{selectedOffer.Lider}</p>
                                                <p className="text-slate-500 font-mono">CNPJ: {selectedOffer.CNPJ_Lider}</p>
                                            </div>

                                            <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 space-y-1">
                                                <span className="text-[11px] font-semibold text-emerald-400 uppercase">Administrador Fiduciário</span>
                                                <p className="font-bold text-white text-sm">{selectedOffer.Administrador}</p>
                                            </div>

                                            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/60">
                                                <span className="text-slate-400 block">Gestor do Portfólio / Emissão:</span>
                                                <span className="font-semibold text-slate-200 mt-0.5 block">{selectedOffer.Gestor}</span>
                                            </div>

                                            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/60">
                                                <span className="text-slate-400 block">Agente Fiduciário:</span>
                                                <span className="font-semibold text-slate-200 mt-0.5 block">{selectedOffer.Agente_Fiduciario}</span>
                                            </div>

                                            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/60">
                                                <span className="text-slate-400 block">Custodiante & Escriturador:</span>
                                                <span className="font-semibold text-slate-200 mt-0.5 block">{selectedOffer.Custodiante} • {selectedOffer.Escriturador}</span>
                                            </div>

                                            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/60">
                                                <span className="text-slate-400 block">Bookbuilding & Mercado:</span>
                                                <span className="font-semibold text-slate-200 mt-0.5 block">Bookbuilding: {selectedOffer.Bookbuilding} • {selectedOffer.Mercado_Negociacao}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Investor Demographics Breakdown for this specific offering */}
                                    <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-4">
                                        <h4 className="font-display font-bold text-base text-white flex items-center gap-2 border-b border-slate-800 pb-3">
                                            <span>👥</span> Raio-X de Subscrição por Perfil do Investidor (Nesta Emissão)
                                        </h4>

                                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-slate-400 block">Fundos de Investimento</span>
                                                <p className="font-mono font-bold text-indigo-400 text-sm mt-1">{formatCurrency(selectedOffer.Vol_Fundos)}</p>
                                            </div>
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-slate-400 block">Pessoas Físicas (Varejo)</span>
                                                <p className="font-mono font-bold text-emerald-400 text-sm mt-1">{formatCurrency(selectedOffer.Vol_Pessoa_Fisica)}</p>
                                            </div>
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-slate-400 block">Investidores Estrangeiros</span>
                                                <p className="font-mono font-bold text-blue-400 text-sm mt-1">{formatCurrency(selectedOffer.Vol_Estrangeiro)}</p>
                                            </div>
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-slate-400 block">Instituições & Intermediários</span>
                                                <p className="font-mono font-bold text-purple-400 text-sm mt-1">{formatCurrency(selectedOffer.Vol_Instituicoes)}</p>
                                            </div>
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-slate-400 block">Previdência Privada</span>
                                                <p className="font-mono font-bold text-amber-400 text-sm mt-1">{formatCurrency(selectedOffer.Vol_Previdencia)}</p>
                                            </div>
                                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                                                <span className="text-slate-400 block">Companhias Seguradoras</span>
                                                <p className="font-mono font-bold text-pink-400 text-sm mt-1">{formatCurrency(selectedOffer.Vol_Seguradoras)}</p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Legal Texts / Destinação / Garantias */}
                                    <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-5">
                                        <h4 className="font-display font-bold text-base text-white flex items-center gap-2 border-b border-slate-800 pb-3">
                                            <span>📜</span> Dossiê Jurídico Integral: Destinação, Lastro e Garantias
                                        </h4>

                                        <div className="space-y-4 text-xs">
                                            <div className="space-y-1.5">
                                                <h5 className="font-bold text-indigo-400 flex items-center gap-1.5 text-sm">
                                                    📌 Destinação Oficial dos Recursos (`Destinacao_Recursos`)
                                                </h5>
                                                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 text-slate-300 leading-relaxed max-h-36 overflow-y-auto font-mono text-[11px]">
                                                    {selectedOffer.Destinacao_Recursos || "Não informado pela instituição emissora."}
                                                </div>
                                            </div>

                                            <div className="space-y-1.5">
                                                <h5 className="font-bold text-amber-400 flex items-center gap-1.5 text-sm">
                                                    🛡️ Garantias Oferecidas & Coobrigados (`Descricao_Garantias`)
                                                </h5>
                                                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 text-slate-300 leading-relaxed max-h-36 overflow-y-auto font-mono text-[11px]">
                                                    {selectedOffer.Descricao_Garantias || "Emissão quirografária / sem garantias informadas."}
                                                </div>
                                            </div>

                                            <div className="space-y-1.5">
                                                <h5 className="font-bold text-emerald-400 flex items-center gap-1.5 text-sm">
                                                    📦 Ativos-Alvo & Lastro (`Descricao_Lastro` / `Ativos_Alvo`)
                                                </h5>
                                                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 text-slate-300 leading-relaxed max-h-32 overflow-y-auto font-mono text-[11px]">
                                                    {selectedOffer.Descricao_Lastro || selectedOffer.Ativos_Alvo || selectedOffer.Tipo_Lastro || "Não se aplica / Não informado."}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="glass-card rounded-2xl p-12 text-center text-slate-400 border border-slate-800">
                                <p>Carregando ou selecione uma oferta para visualizar o dossiê completo...</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Tab 3: Overview */}
                {activeTab === "overview" && overviewCharts && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
                        <div className="glass-card rounded-2xl p-6 border border-slate-800 lg:col-span-2">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h3 className="font-display font-bold text-lg text-white">Evolução Temporal de Volume (R$)</h3>
                                    <p className="text-xs text-slate-400">Comparativo Rito Automático (RCVM 160) vs. Rito Ordinário</p>
                                </div>
                            </div>
                            <ChartWrapper
                                type="bar"
                                height={320}
                                data={{
                                    labels: overviewCharts.temporal.labels,
                                    datasets: [
                                        {
                                            label: "Rito Automático (Ágil)",
                                            data: overviewCharts.temporal.automatico,
                                            backgroundColor: "rgba(16, 185, 129, 0.8)",
                                            borderColor: "#10B981",
                                            borderWidth: 1,
                                            borderRadius: 4
                                        },
                                        {
                                            label: "Rito Ordinário (Análise prévia)",
                                            data: overviewCharts.temporal.ordinario,
                                            backgroundColor: "rgba(99, 102, 241, 0.8)",
                                            borderColor: "#6366F1",
                                            borderWidth: 1,
                                            borderRadius: 4
                                        }
                                    ]
                                }}
                                options={{
                                    scales: {
                                        x: { stacked: true, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94A3B8" } },
                                        y: {
                                            stacked: true,
                                            grid: { color: "rgba(255,255,255,0.05)" },
                                            ticks: {
                                                color: "#94A3B8",
                                                callback: (v) => formatCurrency(v)
                                            }
                                        }
                                    },
                                    plugins: {
                                        legend: { labels: { color: "#E2E8F0", font: { family: "Inter", size: 12 } } },
                                        tooltip: {
                                            callbacks: {
                                                label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.raw)}`
                                            }
                                        }
                                    }
                                }}
                            />
                        </div>

                        <div className="glass-card rounded-2xl p-6 border border-slate-800">
                            <h3 className="font-display font-bold text-lg text-white mb-1">Status das Ofertas</h3>
                            <p className="text-xs text-slate-400 mb-4">Situação atual dos registros na CVM</p>
                            <ChartWrapper
                                type="doughnut"
                                height={320}
                                data={{
                                    labels: overviewCharts.status_funnel.labels,
                                    datasets: [{
                                        data: overviewCharts.status_funnel.counts,
                                        backgroundColor: [
                                            "#10B981", "#3B82F6", "#F59E0B", "#8B5CF6", "#EF4444", "#64748B", "#EC4899"
                                        ],
                                        borderWidth: 0
                                    }]
                                }}
                                options={{
                                    plugins: {
                                        legend: { position: "bottom", labels: { color: "#CBD5E1", font: { size: 11 }, boxWidth: 12 } }
                                    }
                                }}
                            />
                        </div>

                        <div className="glass-card rounded-2xl p-6 border border-slate-800 lg:col-span-3">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h3 className="font-display font-bold text-lg text-white">Top Tipos de Ativos Captados (`Valor_Mobiliario`)</h3>
                                    <p className="text-xs text-slate-400">Volume captado em R$ e quantidade de emissões por modalidade de ativo (FIDC, Debêntures, CRI, FII, CRA...)</p>
                                </div>
                            </div>
                            <ChartWrapper
                                type="bar"
                                height={280}
                                data={{
                                    labels: overviewCharts.top_ativos.labels,
                                    datasets: [{
                                        label: "Volume Registrado (R$)",
                                        data: overviewCharts.top_ativos.volumes,
                                        backgroundColor: "rgba(59, 130, 246, 0.85)",
                                        borderColor: "#3B82F6",
                                        borderWidth: 1,
                                        borderRadius: 6
                                    }]
                                }}
                                options={{
                                    indexAxis: 'y',
                                    scales: {
                                        x: {
                                            grid: { color: "rgba(255,255,255,0.05)" },
                                            ticks: { color: "#94A3B8", callback: (v) => formatCurrency(v) }
                                        },
                                        y: { grid: { display: false }, ticks: { color: "#E2E8F0", font: { weight: "500" } } }
                                    },
                                    plugins: {
                                        legend: { display: false },
                                        tooltip: {
                                            callbacks: {
                                                label: (ctx) => `Volume: ${formatCurrency(ctx.raw)} (${overviewCharts.top_ativos.counts[ctx.dataIndex]} emissões)`
                                            }
                                        }
                                    }
                                }}
                            />
                        </div>
                    </div>
                )}

                {/* Tab 4: Investors Demographics */}
                {activeTab === "investors" && investorCharts && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="glass-card rounded-2xl p-6 border border-slate-800 lg:col-span-2">
                            <h3 className="font-display font-bold text-lg text-white mb-1">Alocação de Liquidez por Perfil do Investidor (R$)</h3>
                            <p className="text-xs text-slate-400 mb-6">De onde vem o capital que subscreve as ofertas primárias</p>
                            <ChartWrapper
                                type="bar"
                                height={340}
                                data={{
                                    labels: investorCharts.labels,
                                    datasets: [{
                                        label: "Volume Alocado (R$)",
                                        data: investorCharts.values,
                                        backgroundColor: [
                                            "#6366F1", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EC4899"
                                        ],
                                        borderRadius: 6
                                    }]
                                }}
                                options={{
                                    scales: {
                                        x: { grid: { display: false }, ticks: { color: "#E2E8F0", font: { size: 11 } } },
                                        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94A3B8", callback: (v) => formatCurrency(v) } }
                                    },
                                    plugins: {
                                        legend: { display: false },
                                        tooltip: {
                                            callbacks: {
                                                label: (ctx) => `Volume: ${formatCurrency(ctx.raw)}`
                                            }
                                        }
                                    }
                                }}
                            />
                        </div>

                        <div className="space-y-4">
                            <div className="glass-card rounded-2xl p-5 border border-slate-800">
                                <h4 className="font-semibold text-sm text-cvm-indigo flex items-center gap-2 mb-2">
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                                    Institucional vs. Varejo
                                </h4>
                                <p className="text-xs text-slate-300 leading-relaxed">
                                    A maior parcela do volume financeiro das ofertas primárias sob a Resolução CVM 160 é absorvida por **Fundos de Investimento** e **Investidores Estrangeiros**, enquanto as Pessoas Físicas (Varejo) têm forte presença no número de investidores individuais e em ativos incentivados (como Debêntures de Infraestrutura e CRIs/CRAs).
                                </p>
                            </div>

                            <div className="glass-card rounded-2xl p-5 border border-slate-800">
                                <h4 className="font-semibold text-sm text-cvm-emerald flex items-center gap-2 mb-2">
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                    Transparência Demográfica
                                </h4>
                                <p className="text-xs text-slate-300 leading-relaxed">
                                    Os dados são compilados do fechamento oficial dos relatórios de distribuição remetidos à CVM (antigos Anexos 400/476 e novos informes RCVM 160).
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Tab 5: Rankings / League Tables */}
                {activeTab === "rankings" && rankings && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="glass-card rounded-2xl p-6 border border-slate-800">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h3 className="font-display font-bold text-lg text-white flex items-center gap-2">
                                        <svg className="w-5 h-5 text-cvm-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                                        Ranking de Coordenadores Líderes
                                    </h3>
                                    <p className="text-xs text-slate-400">Top Instituições Financeiras por Volume Registrado</p>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs data-grid">
                                    <thead>
                                        <tr className="border-b border-slate-800 text-slate-400">
                                            <th className="py-2.5 px-3">#</th>
                                            <th className="py-2.5 px-3">Instituição Líder</th>
                                            <th className="py-2.5 px-3 text-right">Volume Captado</th>
                                            <th className="py-2.5 px-3 text-right">Qtd</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/60">
                                        {rankings.top_lideres.map((item, idx) => (
                                            <tr key={idx} className="hover:bg-slate-800/40">
                                                <td className="py-3 px-3 font-mono font-bold text-slate-400">{idx + 1}</td>
                                                <td className="py-3 px-3 font-medium text-slate-200 truncate max-w-[200px]" title={item.nome}>
                                                    {item.nome}
                                                </td>
                                                <td className="py-3 px-3 text-right font-mono font-semibold text-cvm-emerald">
                                                    {formatCurrency(item.volume)}
                                                </td>
                                                <td className="py-3 px-3 text-right font-mono text-slate-400">
                                                    {item.qtd}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="glass-card rounded-2xl p-6 border border-slate-800">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h3 className="font-display font-bold text-lg text-white flex items-center gap-2">
                                        <svg className="w-5 h-5 text-cvm-indigo" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                                        Ranking de Emissores / Fundos
                                    </h3>
                                    <p className="text-xs text-slate-400">Maiores emissores e securitizadoras por volume captado</p>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs data-grid">
                                    <thead>
                                        <tr className="border-b border-slate-800 text-slate-400">
                                            <th className="py-2.5 px-3">#</th>
                                            <th className="py-2.5 px-3">Nome do Emissor</th>
                                            <th className="py-2.5 px-3 text-right">Volume Captado</th>
                                            <th className="py-2.5 px-3 text-right">Qtd</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/60">
                                        {rankings.top_emissores.map((item, idx) => (
                                            <tr key={idx} className="hover:bg-slate-800/40">
                                                <td className="py-3 px-3 font-mono font-bold text-slate-400">{idx + 1}</td>
                                                <td className="py-3 px-3 font-medium text-slate-200 truncate max-w-[200px]" title={item.nome}>
                                                    {item.nome}
                                                </td>
                                                <td className="py-3 px-3 text-right font-mono font-semibold text-cvm-blue">
                                                    {formatCurrency(item.volume)}
                                                </td>
                                                <td className="py-3 px-3 text-right font-mono text-slate-400">
                                                    {item.qtd}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}
                </ErrorBoundary>
            </main>

            {/* Footer */}
            <footer className="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-500">
                CVM Primários Monitor PRO • Desenvolvido com inteligência analítica baseada no portal de Dados Abertos CVM (`dados.cvm.gov.br`)
            </footer>
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
