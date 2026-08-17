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
├── Iniciar_CVM_Monitor.bat Inicializador autossuficiente (venv + deps + porta)
└── README.md
```

## Como rodar (Windows)

### Caminho normal: duplo clique em `Iniciar_CVM_Monitor.bat`

A única exigência é **Python 3.10+ instalado**. O script cuida do resto: acha o
interpretador (inclusive via `py -3`, e rejeitando o atalho da Microsoft Store,
que não executa nada), cria o ambiente virtual, instala as dependências, escolhe
a porta, sobe o servidor e abre o navegador quando ele começa a responder.

Aplicação em `http://localhost:8080`; a API e as docs ficam no mesmo endereço,
em `/docs`.

**Não é preciso Node.js nem npm para rodar.** A pasta `frontend/dist/` é
versionada justamente para isso — o backend serve o build estático direto na
raiz `/`. O npm só entra quando você for *alterar* a interface (ver abaixo).

O `pip install` só roda quando o `requirements.txt` muda: o script guarda uma
cópia dele dentro do venv e compara. Cliques seguintes sobem em segundos.

**Rodando junto com o `Captacao_Resgate`:** os dois convivem na mesma máquina.
As portas padrão não se cruzam (aqui 8080, lá 8000/5500), cada projeto tem o seu
próprio ambiente virtual dentro da própria pasta, e se a 8080 estiver ocupada o
script anda para a próxima livre em vez de subir por cima de um servidor alheio.

### Alterando a interface (aí sim precisa de Node)

```bat
cd frontend
npm install
npm run build
```

Isso repopula `frontend/dist/`, que é o que o backend serve. Commite o `dist`
junto com a alteração — é ele que mantém o "só Python" válido para quem apenas
usa o sistema.

### Subindo o backend na mão

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

A porta vem da variável de ambiente `PORT` (padrão 8080).

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
