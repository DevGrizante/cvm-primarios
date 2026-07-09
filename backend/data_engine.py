import os
import csv
import zipfile
import io
import urllib.request
import ssl
from datetime import datetime
from collections import defaultdict

ZIP_URL = "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
ZIP_PATH = os.path.join(CACHE_DIR, "oferta_distribuicao.zip")
SCRATCH_ZIP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "oferta_distribuicao.zip"))

class CVMDataEngine:
    def __init__(self):
        self.rows = []
        self.last_update = None
        self.options_cache = {}

    def ensure_data(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        source_zip = None
        if os.path.exists(ZIP_PATH):
            source_zip = ZIP_PATH
        elif os.path.exists(SCRATCH_ZIP):
            source_zip = SCRATCH_ZIP
        
        if not source_zip:
            print("Downloading CVM dataset from official API...")
            ctx = ssl.create_default_context()
            req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=ctx) as resp:
                content = resp.read()
                with open(ZIP_PATH, "wb") as f:
                    f.write(content)
            source_zip = ZIP_PATH
        
        self.load_from_zip(source_zip)

    def _clean_text(self, text):
        if not text or text == "N/A" or text == "" or text == "---" or text == "--":
            return "Não Informado"
        t = str(text).strip()
        replacements = {
            "Debntures": "Debêntures",
            "DEBNTURES": "Debêntures",
            "Certificados de Recebveis Imobilirios": "CRI",
            "Certificados de Recebíveis Imobiliários": "CRI",
            "CERTIFICADOS DE RECEBVEIS IMOBILIRIOS - CRI": "CRI",
            "CERTIFICADO DE RECEBVEIS IMOBILIRIOS": "CRI",
            "Certificados de Recebveis do Agronegcio": "CRA",
            "Certificados de Recebíveis do Agronegócio": "CRA",
            "CERTIFICADOS DE RECEBVEIS DO AGRONEGCIO - CRA": "CRA",
            "Cotas de FII": "FII",
            "QUOTAS DE FUNDO IMOBILIRIO": "FII",
            "AES ORDINRIAS": "Ações Ordinárias",
            "AES PREFERENCIAIS": "Ações Preferenciais",
            "Aes": "Ações",
            "Automtico": "Automático",
            "Ordinrio": "Ordinário",
            "PRIMRIA": "Primária",
            "SECUNDRIA": "Secundária",
            "MISTA": "Mista",
            "PRIMARIA": "Primária",
            "SECUNDARIA": "Secundária",
            "Direitos creditrios": "Direitos Creditórios"
        }
        for k, v in replacements.items():
            t = t.replace(k, v)
        return t

    def _parse_float(self, val):
        if not val or val == "N/A":
            return 0.0
        try:
            return float(str(val).replace(",", "."))
        except:
            return 0.0

    def _parse_int(self, val):
        if not val or val == "N/A":
            return 0
        try:
            return int(float(str(val).replace(",", ".")))
        except:
            return 0

    def _normalize_demography(self, vol_f, qtde_f, raw_pf, raw_fd, raw_est, raw_prev, raw_seg, raw_inst):
        s = raw_pf + raw_fd + raw_est + raw_prev + raw_seg + raw_inst
        if s <= 0 or vol_f <= 0:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        if s <= qtde_f * 1.05:
            scale = (vol_f / qtde_f) if qtde_f > 0 else 1.0
        elif s <= vol_f * 1.05:
            scale = 1.0
        else:
            scale = vol_f / s
        return (
            round(raw_pf * scale, 2),
            round(raw_fd * scale, 2),
            round(raw_est * scale, 2),
            round(raw_prev * scale, 2),
            round(raw_seg * scale, 2),
            round(raw_inst * scale, 2)
        )

    def _infer_indexador(self, row_dict, is_hist=False):
        import re
        if is_hist:
            text = f"{row_dict.get('Atualizacao_Monetaria','')} {row_dict.get('Juros','')} {row_dict.get('Caracteristica_Ativo','')} {row_dict.get('Tipo_Ativo','')}".upper()
        else:
            text = f"{row_dict.get('Descricao_lastro','')} {row_dict.get('Destinacao_recursos','')} {row_dict.get('Descricao_garantias','')} {row_dict.get('Valor_Mobiliario','')} {row_dict.get('Tipo_lastro','')} {row_dict.get('Ativos_alvo','')}".upper()
        
        ativo = str(row_dict.get("Valor_Mobiliario") if not is_hist else row_dict.get("Tipo_Ativo") or "").upper()
        
        # 1. Priority 1: Explicit IPCA/Inflation terms
        if any(w in text for w in ("IPCA", "INPC", "IGP-M", "IGPM", "INCC", "INFLAÇÃO", "IPCR", "VARIACAO DO IGPM", "VARIAÇÃO DO IGPM")):
            return "IPCA / Inflação", False
            
        # 2. Priority 2: Explicit CDI/DI terms
        if "CDI" in text or re.search(r'\b(?:SELIC|ANBID|LIBOR)\b', text) or "TAXA DI" in text or "100% DI" in text or "FLUTUANTE" in text:
            return "CDI / DI", False
        if is_hist and (" DI " in f" {row_dict.get('Juros','')} ".upper() or " CD" in f" {row_dict.get('Juros','')} ".upper() or row_dict.get('Juros','').strip().upper() == "DI"):
            return "CDI / DI", False
        if re.search(r'\b(?:100%|99%|101%|102%|105%|\+\s*|\-\s*)\s*DI\b', text) or re.search(r'\bDI\s*\+', text):
            return "CDI / DI", False

        # 3. Priority 3: Explicit Prefixado terms
        if any(w in text for w in ("PREFIXAD", "PRÉ-FIXAD", "PRE-FIXAD", "TAXA PRÉ", "TAXA PRE ", "TAXA FIXA", "REMUNERAÇÃO FIXA", "JUROS FIXOS")):
            return "PRÉ (Prefixado)", False
        if re.search(r'\b\d+[\d,.]*\s*%\s*(?:A\.A\.|AA|AO ANO|A\.M\.|AM|AO MÊS)\b', text):
            return "PRÉ (Prefixado)", False

        # 4. Domain Inference based on statutory market structure (marked as inferred/heuristic)
        if "DEB" in ativo:
            inc = str(row_dict.get("Titulo_incentivado", "")).strip().upper() == "S"
            esg = str(row_dict.get("Titulo_classificado_como_sustentavel", "")).strip().upper() == "S"
            if inc or esg or any(w in text for w in ("12.431", "12431", "ARTIGO 2", "ART. 2", "DECRETO", "INFRAESTRUTURA", "EÓLIC", "SOLAR", "RODOVIA", "FERROVIA", "SANEAMENTO", "TRANSMISSÃO")):
                return "IPCA / Inflação", True
            else:
                return "CDI / DI", True
                
        elif any(x in ativo for x in ("CRI", "IMOBIL", "FII")):
            return "IPCA / Inflação", True
            
        elif any(x in ativo for x in ("CRA", "AGRONEG", "FIAGRO")):
            return "CDI / DI", True
            
        elif "FIDC" in ativo or "CREDIT" in ativo:
            return "CDI / DI", True
            
        elif "NOTA COMERCIAL" in ativo or "PROMISS" in ativo:
            return "CDI / DI", True

        return "Outros / Não Informado", False

    def _extract_taxa_juros(self, r, idx_type, is_hist=False):
        if is_hist:
            atualiz = self._clean_text(r.get("Atualizacao_Monetaria"))
            juros = self._clean_text(r.get("Juros"))
            if atualiz in ("Não Informado", "-", "--", "---", "NAO", "NÃO", ""):
                atualiz = ""
            if juros in ("Não Informado", "-", "--", "---", "NAO", "NÃO", "", "0", "0%"):
                juros = ""
            
            if atualiz and juros:
                if atualiz.upper() in juros.upper() or "+" in juros:
                    return juros, True
                elif juros.strip().endswith(("%", "a.a.", "A.A.", "a.m.", "A.M.", "AA")) and atualiz.upper() in ("CDI", "DI", "IPCA", "INPC", "IGP-M", "IGPM", "TR", "SELIC"):
                    return f"{atualiz} + {juros}", True
                else:
                    return f"{atualiz} ({juros})", True
            elif juros:
                if juros.strip().endswith(("%", "a.a.", "A.A.", "a.m.", "A.M.", "AA")) and idx_type in ("CDI / DI", "IPCA / Inflação"):
                    base = "CDI" if idx_type == "CDI / DI" else "IPCA" if idx_type == "IPCA / Inflação" else ""
                    if base and base not in juros.upper() and "+" not in juros:
                        return f"{base} + {juros}", True
                return juros, True
            elif atualiz:
                return atualiz, True
            else:
                if idx_type == "IPCA / Inflação": return "IPCA + Spread a Definir", False
                if idx_type == "CDI / DI": return "CDI + Spread a Definir", False
                if idx_type == "PRÉ (Prefixado)": return "Taxa Prefixada a Definir", False
                return "Não Informado (CVM)", False
        else:
            import re
            text = f"{r.get('Destinacao_recursos','')} {r.get('Descricao_lastro','')} {r.get('Ativos_alvo','')}"
            m = re.search(r'((?:CDI|DI|IPCA|INPC|IGP-M|SELIC|PRÉ|TAXA)\s*(?:\+|e|ou|\/)?\s*\d+[\d,.]*\s*(?:%\s*(?:a\.a\.|aa|a\.m\.|am|ao ano)?)?)', text, re.I)
            if m:
                val = m.group(1).strip()
                if not val.upper().startswith(("CDI", "DI", "IPCA", "INPC", "IGP-M", "SELIC", "PRÉ")) and idx_type in ("CDI / DI", "IPCA / Inflação"):
                    base = "CDI" if idx_type == "CDI / DI" else "IPCA"
                    return f"{base} + {val}", True
                return val, True
            m2 = re.search(r'(\d+[\d,.]*\s*%\s*(?:a\.a\.|aa|a\.m\.|am|ao ano|[\+\-]\s*(?:CDI|IPCA|DI)))', text, re.I)
            if m2:
                val = m2.group(1).strip()
                if idx_type == "CDI / DI" and "CDI" not in val.upper() and "DI" not in val.upper():
                    return f"CDI + {val}", True
                elif idx_type == "IPCA / Inflação" and "IPCA" not in val.upper():
                    return f"IPCA + {val}", True
                return val, True
            
            if idx_type == "IPCA / Inflação":
                inc = str(r.get("Titulo_incentivado", "")).strip().upper() == "S" or "12.431" in text or "12431" in text
                return "IPCA + Spread a Definir (Lei 12.431)" if inc else "IPCA + Spread a Definir", False
            elif idx_type == "CDI / DI":
                return "CDI + Spread a Definir (Bookbuilding)", False
            elif idx_type == "PRÉ (Prefixado)":
                return "Taxa Prefixada a Definir", False
            return "Não Informado (CVM)", False

    def load_from_zip(self, zip_filepath):
        print(f"Loading CSV files from {zip_filepath}...")
        unified = []
        with zipfile.ZipFile(zip_filepath, "r") as z:
            # 1. Resolução 160 (Modern 2023+)
            with z.open("oferta_resolucao_160.csv") as f:
                lines = [line.decode("latin-1", errors="replace") for line in f]
                reader = csv.DictReader(lines, delimiter=";")
                for r in reader:
                    data_clean = (r.get("Data_Registro") or r.get("Data_requerimento") or "")[:10]
                    ano = data_clean[:4]
                    if len(ano) != 4 or not ano.isdigit():
                        continue
                    
                    idx_type, idx_inferido = self._infer_indexador(r, is_hist=False)
                    taxa_juros, taxa_declarada = self._extract_taxa_juros(r, idx_type, is_hist=False)
                    
                    vol_float = self._parse_float(r.get("Valor_Total_Registrado"))
                    qtde_float = self._parse_float(r.get("Qtde_Total_Registrada"))
                    vol_pf, vol_fd, vol_est, vol_prev, vol_seg, vol_inst = self._normalize_demography(
                        vol_float, qtde_float,
                        self._parse_float(r.get("Qtde_VM_Pessoa_Natural")),
                        self._parse_float(r.get("Qtde_VM_Fundos_Investimento")),
                        self._parse_float(r.get("Qtde_VM_Investidor_Estrangeiro")),
                        self._parse_float(r.get("Qtde_VM_Entidade_Previdencia_Privada")),
                        self._parse_float(r.get("Qtde_VM_Companhia_Seguradora")),
                        self._parse_float(r.get("Qtde_VM_Instit_Intermed_Partic_Consorcio_Distrib")) + self._parse_float(r.get("Qtde_VM_Demais_Instit_Financ"))
                    )
                    
                    unified.append({
                        "Id_Processo": r.get("Numero_Processo") or r.get("Numero_Requerimento") or "N/A",
                        "Numero_Requerimento": r.get("Numero_Requerimento", "N/A"),
                        "Regime": "Resolução 160 (Moderno)",
                        "Ano": ano,
                        "Data_Clean": data_clean,
                        "Rito": self._clean_text(r.get("Rito_Requerimento")),
                        "Status": self._clean_text(r.get("Status_Requerimento")),
                        "Ativo": self._clean_text(r.get("Valor_Mobiliario")),
                        "Indexador": idx_type,
                        "Indexador_Inferido": idx_inferido,
                        "Taxa_Juros": taxa_juros,
                        "Taxa_Declarada": taxa_declarada,
                        "Tipo_Oferta_Clean": self._clean_text(r.get("Tipo_Oferta")),
                        "Emissor": self._clean_text(r.get("Nome_Emissor")),
                        "CNPJ_Emissor": r.get("CNPJ_Emissor", "Não Informado"),
                        "Lider": self._clean_text(r.get("Nome_Lider")),
                        "CNPJ_Lider": r.get("CNPJ_Lider", "Não Informado"),
                        "Grupo_Coordenador": self._clean_text(r.get("Grupo_Coordenador")),
                        "Publico_Alvo": self._clean_text(r.get("Publico_alvo")),
                        "ESG": "Sim" if str(r.get("Titulo_classificado_como_sustentavel")).strip().upper() == "S" else "Não",
                        "Volume_Float": vol_float,
                        "Qtde_Float": qtde_float,
                        
                        # Alocação Volume R$ Real (corrigido unidade)
                        "Vol_Pessoa_Fisica": vol_pf,
                        "Vol_Fundos": vol_fd,
                        "Vol_Estrangeiro": vol_est,
                        "Vol_Previdencia": vol_prev,
                        "Vol_Seguradoras": vol_seg,
                        "Vol_Instituicoes": vol_inst,
                        
                        # Alocação Quantidade Investidores
                        "Qtd_Inv_Pessoa_Fisica": self._parse_int(r.get("Num_Invest_Pessoa_Natural")),
                        "Qtd_Inv_Fundos": self._parse_int(r.get("Num_Invest_Fundos_Investimento")),
                        "Qtd_Inv_Estrangeiro": self._parse_int(r.get("Num_Invest_Investidor_Estrangeiro")),
                        "Qtd_Inv_Previdencia": self._parse_int(r.get("Num_Invest_Entidade_Previdencia_Privada")),
                        "Qtd_Inv_Seguradoras": self._parse_int(r.get("Num_Invest_Companhia_Seguradora")),
                        "Qtd_Inv_Instituicoes": self._parse_int(r.get("Num_Invest_Instit_Intermed_Partic_Consorcio_Distrib")) + self._parse_int(r.get("Num_Invest_Demais_Instit_Financ")),
                        
                        # Extra deep governance details for detailed tab
                        "Processo_SEI": r.get("Processo_SEI", "Não informado"),
                        "Administrador": self._clean_text(r.get("Administrador")),
                        "Gestor": self._clean_text(r.get("Gestor")),
                        "Agente_Fiduciario": self._clean_text(r.get("Agente_fiduciario")),
                        "Custodiante": self._clean_text(r.get("Custodiante")),
                        "Escriturador": self._clean_text(r.get("Escriturador")),
                        "Avaliador_Risco": self._clean_text(r.get("Avaliador_Risco")),
                        "Mercado_Negociacao": self._clean_text(r.get("Mercado_negociacao")),
                        "Bookbuilding": "Sim" if str(r.get("Bookbuilding", "")).strip().upper() == "S" else "Não",
                        "Tipo_Lastro": self._clean_text(r.get("Tipo_lastro")),
                        "Ativos_Alvo": self._clean_text(r.get("Ativos_alvo")),
                        "Destinacao_Recursos": self._clean_text(r.get("Destinacao_recursos")),
                        "Descricao_Garantias": self._clean_text(r.get("Descricao_garantias")),
                        "Descricao_Lastro": self._clean_text(r.get("Descricao_lastro")),
                        "Regime_Fiduciario": self._clean_text(r.get("Regime_fiduciario")),
                        "Possibilidade_Revolvencia": "Sim" if str(r.get("Possibilidade_revolvencia", "")).strip().upper() == "S" else "Não",
                        "Titulo_Incentivado": "Sim" if str(r.get("Titulo_incentivado", "")).strip().upper() == "S" else "Não",
                        "Coobrigados": self._clean_text(r.get("Identificacao_devedores_coobrigados"))
                    })

            # 2. Instrução 400/476 (Historical up to 2023)
            with z.open("oferta_distribuicao.csv") as f:
                lines = [line.decode("latin-1", errors="replace") for line in f]
                reader = csv.DictReader(lines, delimiter=";")
                for r in reader:
                    data_clean = (r.get("Data_Registro_Oferta") or r.get("Data_Inicio_Oferta") or "")[:10]
                    ano = data_clean[:4]
                    if len(ano) != 4 or not ano.isdigit():
                        continue
                    
                    idx_type, idx_inferido = self._infer_indexador(r, is_hist=True)
                    taxa_juros, taxa_declarada = self._extract_taxa_juros(r, idx_type, is_hist=True)
                    
                    vol_float = self._parse_float(r.get("Valor_Total"))
                    qtde_float = self._parse_float(r.get("Quantidade_Total"))
                    vol_pf, vol_fd, vol_est, vol_prev, vol_seg, vol_inst = self._normalize_demography(
                        vol_float, qtde_float,
                        self._parse_float(r.get("Qtd_Cli_Pessoa_Fisica")),
                        0.0,
                        self._parse_float(r.get("Qtd_Cli_Investidor_Estrangeiro")),
                        0.0,
                        0.0,
                        self._parse_float(r.get("Qtd_Cli_Pessoa_Juridica"))
                    )
                    
                    unified.append({
                        "Id_Processo": r.get("Numero_Processo") or "N/A",
                        "Numero_Requerimento": r.get("Numero_Registro_Oferta", "N/A"),
                        "Regime": "ICVM 400/476 (Histórico)",
                        "Ano": ano,
                        "Data_Clean": data_clean,
                        "Rito": "Ordinário (ICVM 400/476)",
                        "Status": self._clean_text(r.get("Modalidade_Registro") or "Registrada"),
                        "Ativo": self._clean_text(r.get("Tipo_Ativo")),
                        "Indexador": idx_type,
                        "Indexador_Inferido": idx_inferido,
                        "Taxa_Juros": taxa_juros,
                        "Taxa_Declarada": taxa_declarada,
                        "Tipo_Oferta_Clean": self._clean_text(r.get("Tipo_Oferta")),
                        "Emissor": self._clean_text(r.get("Nome_Emissor")),
                        "CNPJ_Emissor": r.get("CNPJ_Emissor", "Não Informado"),
                        "Lider": self._clean_text(r.get("Nome_Lider")),
                        "CNPJ_Lider": r.get("CNPJ_Lider", "Não Informado"),
                        "Grupo_Coordenador": "Não informado",
                        "Publico_Alvo": "Geral/Qualificado (Histórico)",
                        "ESG": "Não Informado",
                        "Volume_Float": vol_float,
                        "Qtde_Float": qtde_float,
                        
                        "Vol_Pessoa_Fisica": vol_pf,
                        "Vol_Fundos": vol_fd,
                        "Vol_Estrangeiro": vol_est,
                        "Vol_Previdencia": vol_prev,
                        "Vol_Seguradoras": vol_seg,
                        "Vol_Instituicoes": vol_inst,
                        
                        "Qtd_Inv_Pessoa_Fisica": self._parse_int(r.get("Nr_Pessoa_Fisica")),
                        "Qtd_Inv_Fundos": self._parse_int(r.get("Nr_Fundos_Investimento")),
                        "Qtd_Inv_Estrangeiro": self._parse_int(r.get("Nr_Investidor_Estrangeiro")),
                        "Qtd_Inv_Previdencia": self._parse_int(r.get("Nr_Entidade_Previdencia_Privada")),
                        "Qtd_Inv_Seguradoras": self._parse_int(r.get("Nr_Companhia_Seguradora")),
                        "Qtd_Inv_Instituicoes": self._parse_int(r.get("Nr_Demais_Pessoa_Juridica")),
                        
                        "Processo_SEI": "N/A",
                        "Administrador": "Não informado",
                        "Gestor": "Não informado",
                        "Agente_Fiduciario": "Não informado",
                        "Custodiante": "Não informado",
                        "Escriturador": "Não informado",
                        "Avaliador_Risco": "Não informado",
                        "Mercado_Negociacao": "B3 / OTC (Histórico)",
                        "Bookbuilding": "Não Informado",
                        "Tipo_Lastro": self._clean_text(r.get("Atualizacao_Monetaria")),
                        "Ativos_Alvo": self._clean_text(r.get("Juros")),
                        "Destinacao_Recursos": f"Remuneração / Juros declarados: {self._clean_text(r.get('Juros'))}. Atualização: {self._clean_text(r.get('Atualizacao_Monetaria'))}",
                        "Descricao_Garantias": self._clean_text(r.get("Oferta_Regime_Fiduciario")),
                        "Descricao_Lastro": self._clean_text(r.get("Atualizacao_Monetaria")),
                        "Regime_Fiduciario": self._clean_text(r.get("Oferta_Regime_Fiduciario")),
                        "Possibilidade_Revolvencia": "Não Informado",
                        "Titulo_Incentivado": "Sim" if str(r.get("Oferta_Incentivo_Fiscal", "")).strip().upper() == "S" else "Não",
                        "Coobrigados": "Não informado"
                    })

        # Build issuer historical average volume & rate cache
        import hashlib
        issuer_vols = {}
        issuer_qtys = {}
        issuer_rates = {}
        for r in unified:
            em = r["Emissor"]
            at_key = r["Ativo"]
            if r["Volume_Float"] > 0:
                issuer_vols.setdefault((em, at_key), []).append(r["Volume_Float"])
                issuer_vols.setdefault(em, []).append(r["Volume_Float"])
            if r["Qtde_Float"] > 0:
                issuer_qtys.setdefault((em, at_key), []).append(r["Qtde_Float"])
                issuer_qtys.setdefault(em, []).append(r["Qtde_Float"])
            if r.get("Taxa_Declarada") and r["Taxa_Juros"] and not any(w in r["Taxa_Juros"] for w in ("Spread", "Flutuante", "Não Informado", "Taxa Prefixada", "a Definir")):
                issuer_rates.setdefault((em, r["Indexador"]), r["Taxa_Juros"])
                cnpj_clean = r.get("CNPJ_Emissor", "").strip()
                is_spv = any(x in em.upper() for x in ("SECURITIZADORA", "TRUST", "DISTRIBUIDORA", "FIDC", "FINANCEIRA"))
                if cnpj_clean and cnpj_clean != "Não Informado" and not is_spv:
                    issuer_rates.setdefault((cnpj_clean, r["Indexador"]), r["Taxa_Juros"])

        # Pass 2: Identificar ofertas com volume em bookbuilding e aplicar honestidade em taxas/alocações
        for r in unified:
            em = r["Emissor"]
            at = r["Ativo"].upper()
            at_key = r["Ativo"]
            idx = r["Indexador"]
            
            # 1. Volume alvo em ofertas em Bookbuilding ou com volume zerado na CVM
            r["Is_Estimated_Vol"] = False
            r["Alocacao_Pendente"] = False
            
            if r["Volume_Float"] <= 0 or r["Qtde_Float"] <= 0 or r.get("Bookbuilding") == "Sim":
                if r["Volume_Float"] <= 0 or r["Qtde_Float"] <= 0:
                    r["Is_Estimated_Vol"] = True
                    if (em, at_key) in issuer_vols and len(issuer_vols[(em, at_key)]) > 0:
                        est_vol = round(sum(issuer_vols[(em, at_key)]) / len(issuer_vols[(em, at_key)]), 2)
                        est_qty = round(sum(issuer_qtys[(em, at_key)]) / len(issuer_qtys[(em, at_key)]), 0) if (em, at_key) in issuer_qtys and len(issuer_qtys[(em, at_key)]) > 0 else round(est_vol / 1000.0, 0)
                    elif em in issuer_vols and len(issuer_vols[em]) > 0:
                        est_vol = round(sum(issuer_vols[em]) / len(issuer_vols[em]), 2)
                        est_qty = round(sum(issuer_qtys[em]) / len(issuer_qtys[em]), 0) if em in issuer_qtys and len(issuer_qtys[em]) > 0 else round(est_vol / 1000.0, 0)
                    else:
                        if "DEB" in at: est_vol, est_qty = 500000000.0, 500000.0
                        elif any(x in at for x in ("CRI", "IMOBIL", "FII")): est_vol, est_qty = 150000000.0, 150000.0
                        elif any(x in at for x in ("CRA", "AGRONEG", "FIAGRO")): est_vol, est_qty = 150000000.0, 150000.0
                        elif "FIDC" in at or "CREDIT" in at: est_vol, est_qty = 100000000.0, 100000.0
                        elif "AÇÃO" in at or "ACOES" in at: est_vol, est_qty = 800000000.0, 40000000.0
                        else: est_vol, est_qty = 200000000.0, 200000.0
                    r["Volume_Float"] = est_vol
                    r["Qtde_Float"] = est_qty
                
                # Para ofertas sem alocação confirmada pela CVM, zerar alocações e sinalizar como pendente
                if r["Vol_Pessoa_Fisica"] <= 0 and r["Vol_Fundos"] <= 0 and r["Vol_Instituicoes"] <= 0:
                    r["Alocacao_Pendente"] = True
                    r["Vol_Pessoa_Fisica"] = 0.0
                    r["Vol_Fundos"] = 0.0
                    r["Vol_Estrangeiro"] = 0.0
                    r["Vol_Previdencia"] = 0.0
                    r["Vol_Seguradoras"] = 0.0
                    r["Vol_Instituicoes"] = 0.0
                    r["Qtd_Inv_Pessoa_Fisica"] = 0
                    r["Qtd_Inv_Fundos"] = 0
                    r["Qtd_Inv_Estrangeiro"] = 0
                    r["Qtd_Inv_Previdencia"] = 0
                    r["Qtd_Inv_Seguradoras"] = 0
                    r["Qtd_Inv_Instituicoes"] = 0

            # 2. Honestidade de Taxas: se a taxa não foi informada ou está a definir, usar histórico do emissor ou explicitar "a Definir"
            if not r.get("Taxa_Declarada") or any(w in r["Taxa_Juros"] for w in ("Spread", "Flutuante", "Não Informado", "a Definir")):
                cnpj = r.get("CNPJ_Emissor", "").strip()
                is_spv = any(x in em.upper() for x in ("SECURITIZADORA", "TRUST", "DISTRIBUIDORA", "FIDC", "FINANCEIRA"))
                found_rate = None
                if (em, idx) in issuer_rates:
                    found_rate = issuer_rates[(em, idx)]
                elif cnpj and cnpj != "Não Informado" and not is_spv and (cnpj, idx) in issuer_rates:
                    found_rate = issuer_rates[(cnpj, idx)]
                elif (em, "CDI / DI") in issuer_rates and idx == "CDI / DI":
                    found_rate = issuer_rates[(em, "CDI / DI")]
                elif cnpj and cnpj != "Não Informado" and not is_spv and (cnpj, "CDI / DI") in issuer_rates and idx == "CDI / DI":
                    found_rate = issuer_rates[(cnpj, "CDI / DI")]
                elif (em, "IPCA / Inflação") in issuer_rates and idx == "IPCA / Inflação":
                    found_rate = issuer_rates[(em, "IPCA / Inflação")]
                elif cnpj and cnpj != "Não Informado" and not is_spv and (cnpj, "IPCA / Inflação") in issuer_rates and idx == "IPCA / Inflação":
                    found_rate = issuer_rates[(cnpj, "IPCA / Inflação")]

                if found_rate and ((idx == "CDI / DI" and any(k in found_rate.upper() for k in ("CDI", "DI", "%"))) or (idx == "IPCA / Inflação" and any(k in found_rate.upper() for k in ("IPCA", "%")))):
                    r["Taxa_Juros"] = f"{found_rate} *(Hist. Emissor)*"
                    r["Taxa_Declarada"] = True
                else:
                    if idx == "CDI / DI":
                        r["Taxa_Juros"] = "CDI + Spread a Definir (Bookbuilding)"
                    elif idx == "IPCA / Inflação":
                        r["Taxa_Juros"] = "IPCA + Spread a Definir (Bookbuilding)"
                    elif idx == "PRÉ (Prefixado)":
                        r["Taxa_Juros"] = "Taxa Prefixada a Definir"
                    else:
                        r["Taxa_Juros"] = "Não Informado (CVM)"

        # Sort descending by Data_Clean
        unified.sort(key=lambda x: x["Data_Clean"], reverse=True)
        self.rows = unified
        try:
            with zipfile.ZipFile(zip_filepath, "r") as z:
                dt = z.getinfo("oferta_resolucao_160.csv").date_time
                self.last_update = datetime(*dt).strftime("%d/%m/%Y %H:%M:%S") + " (CVM Oficial)"
        except Exception:
            mtime = os.path.getmtime(zip_filepath) if os.path.exists(zip_filepath) else datetime.now().timestamp()
            self.last_update = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S") + " (CVM Oficial)"
        self._build_options_cache()
        print(f"Data engine loaded {len(self.rows)} offerings successfully.")

    def _build_options_cache(self):
        anos = sorted(list(set(r["Ano"] for r in self.rows)), reverse=True)
        ativos = sorted(list(set(r["Ativo"] for r in self.rows if r["Ativo"] != "Não Informado")))
        status_list = sorted(list(set(r["Status"] for r in self.rows if r["Status"] != "Não Informado")))
        indexadores = ["Todos", "CDI / DI", "IPCA / Inflação", "PRÉ (Prefixado)", "Outros / Não Informado"]
        
        self.options_cache = {
            "anos": ["Recentes (2023-2026)", "Todos"] + anos[:20],
            "ritos": ["Todos", "Automático", "Ordinário"],
            "ativos": ["Todos"] + [a for a in ativos if len(a) > 1][:35],
            "status": ["Todos"] + status_list[:15],
            "indexadores": indexadores,
            "publicos": ["Todos", "Profissional", "Qualificado", "Geral"]
        }

    def get_filtered_rows(self, ano="Recentes (2023-2026)", rito="Todos", ativo="Todos", status="Todos", indexador="Todos", publico="Todos", regime="Todos", busca=""):
        def _to_list(val):
            if isinstance(val, (list, tuple, set)):
                items = []
                for v in val:
                    items.extend([i.strip() for i in str(v).split(",") if i.strip()])
                return items if items else ["Todos"]
            if not val: return ["Todos"]
            items = [i.strip() for i in str(val).split(",") if i.strip()]
            return items if items else ["Todos"]

        ano_list = _to_list(ano)
        rito_list = _to_list(rito)
        ativo_list = _to_list(ativo)
        status_list = _to_list(status)
        idx_list = _to_list(indexador)
        pub_list = _to_list(publico)
        reg_list = _to_list(regime)
        busca_lower = busca.lower() if busca else ""
        
        res = []
        for r in self.rows:
            if "Todos" not in reg_list:
                match_reg = False
                for reg_item in reg_list:
                    if reg_item == "160" and "160" in r["Regime"]: match_reg = True; break
                    elif reg_item == "hist" and "ICVM" in r["Regime"]: match_reg = True; break
                    elif reg_item.lower() in r["Regime"].lower(): match_reg = True; break
                if not match_reg: continue
            
            if "Todos" not in ano_list:
                match_ano = False
                for a in ano_list:
                    if a == "Recentes (2023-2026)" and r["Ano"] in ("2023", "2024", "2025", "2026"): match_ano = True; break
                    elif r["Ano"] == str(a): match_ano = True; break
                if not match_ano: continue
            
            if "Todos" not in rito_list:
                if not any(rit.lower() in r["Rito"].lower() for rit in rito_list): continue
                
            if "Todos" not in ativo_list:
                match_at = False
                r_at_upper = str(r["Ativo"]).upper()
                for at in ativo_list:
                    at_upper = str(at).upper()
                    if "DEB" in at_upper and "DEB" in r_at_upper: match_at = True; break
                    elif ("CRI" in at_upper or "IMOBILI" in at_upper) and ("CRI" in r_at_upper or "IMOBILI" in r_at_upper): match_at = True; break
                    elif ("CRA" in at_upper or "AGRONEG" in at_upper) and ("CRA" in r_at_upper or "AGRONEG" in r_at_upper): match_at = True; break
                    elif ("FIDC" in at_upper or "CREDIT" in at_upper) and ("FIDC" in r_at_upper or "CREDIT" in r_at_upper): match_at = True; break
                    elif r["Ativo"] == at or at_upper in r_at_upper: match_at = True; break
                if not match_at: continue
                
            if "Todos" not in status_list:
                if not any(st.lower() in r["Status"].lower() for st in status_list): continue
                
            if "Todos" not in idx_list:
                if not any(r["Indexador"] == ix or ix.lower() in r["Indexador"].lower() for ix in idx_list): continue
                
            if "Todos" not in pub_list:
                if not any(pb.lower() in r["Publico_Alvo"].lower() for pb in pub_list): continue
            
            if busca_lower:
                if (busca_lower not in r["Emissor"].lower() and 
                    busca_lower not in r["Lider"].lower() and 
                    busca_lower not in r["Id_Processo"].lower() and
                    busca_lower not in r["Ativo"].lower() and
                    busca_lower not in r["Status"].lower()):
                    continue
            
            res.append(r)
        return res

engine = CVMDataEngine()
