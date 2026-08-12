# CVM Monitor Pro

Dashboard web interativo para monitoramento e análise de ofertas públicas registradas na CVM (Debêntures, CRI, CRA, Notas Comerciais, Fiagro, FIDC e FII). 
Oferece filtros avançados por indexador, emissor, coordenador líder e visualizações de inteligência de negócios (YoY, spread vs vencimento, evolução anual por indexador).

```
cvm-monitor-pro/
├── backend/          Servidor Python (FastAPI) e processamento
│   ├── main.py       Entrypoint da API (serve a interface e dados)
│   ├── build_dataset.py Processamento de dados
│   ├── data/         Base de dados local (JSON, csv, parquet)
│   └── requirements.txt
├── frontend/         Frontend em React (Vite + TailwindCSS + Chart.js)
│   ├── src/          Código-fonte da UI (App.jsx, dataEngine.js)
│   ├── dist/         Build de produção (estático, consumido pelo backend)
│   ├── package.json
│   └── tailwind.config.js
├── Iniciar_CVM_Monitor.bat Atalho para inicialização
└── README.md
```

## Como rodar (Windows)

### 1. Build do Frontend (Interface)

O frontend é construído com React e Vite. Antes de iniciar o backend pela primeira vez ou sempre que fizer alterações visuais, é necessário compilar os arquivos estáticos:

```bat
cd frontend
npm install
npm run build
```

Isso irá popular a pasta `frontend/dist/`. O backend está configurado para servir estes arquivos diretamente na raiz `/`.

### 2. Backend (API)

O backend em FastAPI atua servindo os arquivos estáticos compilados e provendo a API de dados para o frontend.

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Acesse a aplicação em `http://localhost:8000`.

> **Dica Rápida:** Você pode utilizar o script `Iniciar_CVM_Monitor.bat` na raiz do projeto. Ele inicializa o ambiente virtual e sobe o servidor automaticamente.

## Arquitetura de Dados

- **Frontend (`src/dataEngine.js`)**: Grande parte da lógica de cálculo de KPIs, agrupamentos (Charts) e filtro dinâmico ocorre diretamente no cliente. Isso garante uma experiência de usuário sem atrasos de rede na transição de telas e aplicação de múltiplos filtros.
- **Backend (`main.py`)**: A API expõe rotas como `/api/bootstrap` que fornecem a URL do JSON de dados processados. O React faz o fetch inicial, guardando os dados em memória.

## Módulos Principais

- **Ofertas**: Tabela completa e paginada das ofertas de renda fixa, com busca textual rápida e suporte a visualização detalhada.
- **Inteligência e Temporal (Gráficos)**:
  - **Comparação YoY (Year over Year)**: Volume (R$ Bi) comparativo flexível entre 3 anos selecionáveis, com abertura detalhada por Indexador (CDI, IPCA, PRÉ).
  - **Histórico Empilhado**: Evolução ano a ano baseada nos mesmos indexadores.
  - **Spread de Taxa vs Vencimento**: Scatter/Bubble chart cruzando os vencimentos anuais com o prêmio de risco, separando CDI e IPCA.
  - **Market Share**: Ranking top 10 ou visão total dos Coordenadores e Emissores.
- **Filtro de Estimativas**: Toggle "Bookbuilding Estimado" permite consolidar os números de mercado incluindo ou não papéis ainda em pipeline de distribuição.
