import os
import re
import csv
import zipfile
import io
import urllib.request
import ssl
import time
import json
import threading
from datetime import datetime, timedelta, date, time as dt_time, timezone
import unicodedata
from collections import defaultdict

ZIP_URL = "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache")
ZIP_PATH = os.path.join(CACHE_DIR, "oferta_distribuicao.zip")
SCRATCH_ZIP = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "oferta_distribuicao.zip"))
NTNB_VERTICES = [2026, 2027, 2028, 2029, 2030, 2032, 2035, 2040, 2045, 2050, 2055, 2060]

class CVMDataEngine:
    def __init__(self):
        self.rows = []
        self.last_update = None
        self.options_cache = {}
        self._scheduler_started = False

    def _ultimo_slot(self, agora=None):
        if agora is None:
            agora = datetime.now()
        try:
            import zoneinfo
            sp_tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
            agora_sp = agora.astimezone(sp_tz)
        except Exception:
            sp_tz = timezone(timedelta(hours=-3))
            if agora.tzinfo is None:
                agora_sp = agora.replace(tzinfo=sp_tz)
            else:
                agora_sp = agora.astimezone(sp_tz)
        
        if agora_sp.hour < 8:
            ontem = agora_sp.date() - timedelta(days=1)
            slot = datetime.combine(ontem, dt_time(12, 0), tzinfo=sp_tz)
        elif agora_sp.hour < 12:
            hoje = agora_sp.date()
            slot = datetime.combine(hoje, dt_time(8, 0), tzinfo=sp_tz)
        else:
            hoje = agora_sp.date()
            slot = datetime.combine(hoje, dt_time(12, 0), tzinfo=sp_tz)
        return slot

    def _proximo_slot(self, agora=None):
        if agora is None:
            agora = datetime.now()
        try:
            import zoneinfo
            sp_tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
            agora_sp = agora.astimezone(sp_tz)
        except Exception:
            sp_tz = timezone(timedelta(hours=-3))
            if agora.tzinfo is None:
                agora_sp = agora.replace(tzinfo=sp_tz)
            else:
                agora_sp = agora.astimezone(sp_tz)
        
        if agora_sp.hour < 8:
            hoje = agora_sp.date()
            slot = datetime.combine(hoje, dt_time(8, 0), tzinfo=sp_tz)
        elif agora_sp.hour < 12:
            hoje = agora_sp.date()
            slot = datetime.combine(hoje, dt_time(12, 0), tzinfo=sp_tz)
        else:
            amanha = agora_sp.date() + timedelta(days=1)
            slot = datetime.combine(amanha, dt_time(8, 0), tzinfo=sp_tz)
        return slot

    def needs_refresh(self):
        source_zip = ZIP_PATH if os.path.exists(ZIP_PATH) else (SCRATCH_ZIP if os.path.exists(SCRATCH_ZIP) else None)
        if not source_zip or not os.path.exists(source_zip):
            return True
        try:
            mtime = os.path.getmtime(source_zip)
            ultimo = self._ultimo_slot().timestamp()
            return mtime < ultimo
        except Exception:
            return False

    def _start_scheduler_worker(self):
        if self._scheduler_started:
            return
        self._scheduler_started = True
        
        def _schedule_loop():
            while True:
                try:
                    proximo = self._proximo_slot()
                    agora = datetime.now(proximo.tzinfo) if proximo.tzinfo else datetime.now()
                    diff = (proximo - agora).total_seconds()
                    sleep_time = max(diff + 10, 10)
                    print(f"[CVM SCHEDULER] Refresh agendado para {proximo.strftime('%H:%M')} (em {sleep_time/3600:.1f}h)")
                    time.sleep(sleep_time)
                    print("[CVM SCHEDULER] Slot alcançado! Verificando e atualizando base CVM...")
                    if self.needs_refresh():
                        try:
                            ctx = ssl.create_default_context()
                            req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                                content = resp.read()
                                os.makedirs(CACHE_DIR, exist_ok=True)
                                with open(ZIP_PATH, "wb") as f:
                                    f.write(content)
                            print("[CVM SCHEDULER] Download concluído! Recarregando dados e cache SRE...")
                            self.load_from_zip(ZIP_PATH)
                        except Exception as dl_err:
                            print(f"[CVM SCHEDULER] Erro no download do slot: {dl_err}. Agendando retry em 15 min...")
                            time.sleep(900)
                except Exception as e:
                    print(f"[CVM SCHEDULER] Erro no loop de agendamento: {e}")
                    time.sleep(60)
        
        threading.Thread(target=_schedule_loop, daemon=True).start()

    def _log_top_coordenadores(self):
        emissor_vol = defaultdict(float)
        for r in self.rows:
            l = r.get("Lider")
            if l and l != "Não Informado":
                emissor_vol[l] += r.get("Volume_Float", 0.0)
        top_c = sorted(emissor_vol.items(), key=lambda x: x[1], reverse=True)[:30]
        print("=== Top 30 Líderes Canônicos (pós-normalização) ===")
        for idx, (nome, vol) in enumerate(top_c, 1):
            print(f"{idx}. {nome} - R$ {vol/1e9:.2f} Bi")
        print("===================================================")

    def ensure_data(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        source_zip = None
        if not self.needs_refresh():
            if os.path.exists(ZIP_PATH):
                source_zip = ZIP_PATH
            elif os.path.exists(SCRATCH_ZIP):
                source_zip = SCRATCH_ZIP
        
        if not source_zip:
            print("Downloading latest CVM dataset from official API (or slot refresh needed)...")
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                    with open(ZIP_PATH, "wb") as f:
                        # Stream in 256KB chunks to avoid loading the full zip into RAM
                        while True:
                            chunk = resp.read(262144)
                            if not chunk:
                                break
                            f.write(chunk)
                source_zip = ZIP_PATH
            except Exception as e:
                print(f"Notice: Could not download fresh zip ({e}), falling back to existing cache if available.")
                if os.path.exists(ZIP_PATH):
                    source_zip = ZIP_PATH
                elif os.path.exists(SCRATCH_ZIP):
                    source_zip = SCRATCH_ZIP
        
        self.load_from_zip(source_zip)
        self._start_scheduler_worker()

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

    def _extract_coordenadores(self, r):
        lider_raw = r.get("Lider", "Não Informado")
        lider_norm = self._normalize_coordenador(lider_raw)
        candidates = []
        if lider_norm != "Não Informado":
            candidates.append(lider_norm)
        
        texts_to_scan = [
            str(lider_raw),
            str(r.get("Grupo_Coordenador", "")),
            str(r.get("Identificacao_devedores_coobrigados", "")),
            str(r.get("Descricao_garantias", "")),
            str(r.get("Destinacao_recursos", ""))
        ]
        
        split_regex = re.compile(r'\s*(?:;|\be\b|\b[Ee]\b|\+|,|\s+/\s+)\s*')
        for txt in texts_to_scan:
            if not txt or txt in ("Não Informado", "N/A", "Não informado", ""):
                continue
            whole_norm = self._normalize_coordenador(txt)
            if whole_norm != "Não Informado" and whole_norm != txt.upper() and whole_norm not in candidates:
                candidates.append(whole_norm)
                
            parts = split_regex.split(txt)
            for p in parts:
                p_clean = p.strip()
                if len(p_clean) > 3:
                    norm = self._normalize_coordenador(p_clean)
                    if norm != "Não Informado" and norm != lider_norm and len(norm) <= 60 and (norm != p_clean.upper() or any(w in norm.upper() for w in ("BANCO", "BBA", "BBI", "XP", "BTG", "SAFRA", "GENIAL", "UBS", "SANTANDER", "CITI", "MORGAN", "BRADESCO", "ITAU", "CORRETORA", "DISTRIBUIDORA", "DTVM", "CTVM"))):
                        if norm not in candidates:
                            candidates.append(norm)
        
        if not candidates and lider_norm != "Não Informado":
            candidates.append(lider_norm)
        consorcio_str = " / ".join(candidates) if len(candidates) > 1 else lider_norm
        return lider_norm, consorcio_str, candidates

    def _normalize_coordenador(self, nome):
        if not nome or str(nome).strip() in ("Não Informado", "", "None", "Não informado"):
            return "Não Informado"
        s = self._clean_text(str(nome)).upper()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = " ".join(s.split())
        
        blacklist_fragments = {
            "VALORES MOBILIARIOS", "TITULOS E VALORES MOBILIARIOS", "CORRETORA DE TITULOS E VALORES MOBILIARIOS",
            "DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS", "CAMBIO TITULOS E VALORES MOBILIARIOS",
            "CAMBIO, TITULOS E VALORES MOBILIARIOS", "TITULOS E VALORES MOBILIARIOS S.A.",
            "VALORES MOBILIARIOS S.A.", "VALORES", "TITULOS", "CAMBIO", "CORRETORA DE CAMBIO",
            "COORDENADOR PLENO", "SECURITIZADORA", "ADMINISTRADOR DE CARTEIRA", "NAO INFORMADO",
            "DISTRIBUIDORA DE TITULOS", "VALORES MOBILIARIOS SA"
        }
        if s in blacklist_fragments or s.startswith("VALORES MOBILIARIOS") or s == "VALORES MOBILIARIOS":
            return "Não Informado"
        
        if s.startswith("BANCO "):
            s = s[6:].strip()
            
        for suf in (" S.A.", " S/A", " LTDA.", " LTDA", " CTVM", " CCTVM", " DTVM", " DE INVESTIMENTO", " INVESTIMENTO", " INVESTIMENTOS", " S.A", " SA"):
            if s.endswith(suf):
                s = s[:-len(suf)].strip()
                
        aliases = {
            "ITAU BBA": "ITAÚ BBA",
            "BANCO ITAU BBA": "ITAÚ BBA",
            "ITAU UNIBANCO": "ITAÚ BBA",
            "ITAU": "ITAÚ BBA",
            "BTG PACTUAL": "BTG PACTUAL",
            "BTG INVESTMENT BANKING": "BTG PACTUAL",
            "BANCO BTG PACTUAL": "BTG PACTUAL",
            "BTG": "BTG PACTUAL",
            "BRADESCO BBI": "BRADESCO BBI",
            "BANCO BRADESCO BBI": "BRADESCO BBI",
            "BRADESCO": "BRADESCO BBI",
            "XP INVESTIMENTOS": "XP INVESTIMENTOS",
            "XP": "XP INVESTIMENTOS",
            "SANTANDER (BRASIL)": "BANCO SANTANDER (BRASIL)",
            "SANTANDER": "BANCO SANTANDER (BRASIL)",
            "BANCO SANTANDER": "BANCO SANTANDER (BRASIL)",
            "BANCO SANTANDER (BRASIL)": "BANCO SANTANDER (BRASIL)",
            "UBS BRASIL": "UBS BRASIL",
            "UBS BB": "UBS BRASIL",
            "UBS": "UBS BRASIL",
            "SAFRA": "BANCO SAFRA",
            "BANCO SAFRA": "BANCO SAFRA",
            "GENIAL": "GENIAL",
            "ORAMA": "ÓRAMA"
        }
        if s in aliases:
            return aliases[s]
        for k, v in aliases.items():
            if k == s or (len(k) > 4 and k in s and "BANCO" not in k and k not in ("ITAU", "BTG", "UBS", "XP")):
                return v
        return s

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

    def _build_demografia_detalhada(self, r, vol_f, qtde_f, is_hist=False):
        if not is_hist:
            pairs = [
                ("Pessoas naturais", r.get("Num_Invest_Pessoa_Natural"), r.get("Qtde_VM_Pessoa_Natural")),
                ("Clubes de investimento", r.get("Num_Invest_Clube_Investimento"), r.get("Qtde_VM_Clube_Investimento")),
                ("Fundos de investimento", r.get("Num_Invest_Fundos_Investimento"), r.get("Qtde_VM_Fundos_Investimento")),
                ("Entidades de previdência privada", r.get("Num_Invest_Entidade_Previdencia_Privada"), r.get("Qtde_VM_Entidade_Previdencia_Privada")),
                ("Companhias seguradoras", r.get("Num_Invest_Companhia_Seguradora"), r.get("Qtde_VM_Companhia_Seguradora")),
                ("Investidores estrangeiros", r.get("Num_Invest_Investidor_Estrangeiro"), r.get("Qtde_VM_Investidor_Estrangeiro")),
                ("Instituições Intermediárias participantes do consórcio de distribuição", r.get("Num_Invest_Instit_Intermed_Partic_Consorcio_Distrib"), r.get("Qtde_VM_Instit_Intermed_Partic_Consorcio_Distrib")),
                ("Instituições financeiras ligadas ao emissor e aos participantes do consórcio", r.get("Num_Invest_Instit_Financ_Emissora_Partic_Consorcio"), r.get("Qtde_VM_Instit_Financ_Emissora_Partic_Consorcio")),
                ("Demais instituições financeiras", r.get("Num_Invest_Demais_Instit_Financ"), r.get("Qtde_VM_Demais_Instit_Financ")),
                ("Demais pessoas jurídicas ligadas ao emissor e aos participantes do consórcio", r.get("Num_Invest_Demais_Pessoa_Juridica_Emissora_Partic_Consorcio"), r.get("Qtde_VM_Demais_Pessoa_Juridica_Emissora_Partic_Consorcio")),
                ("Demais pessoas jurídicas", r.get("Num_Invest_Demais_Pessoa_Juridica"), r.get("Qtde_VM_Demais_Pessoa_Juridica")),
                ("Sócios, administradores, empregados, prepostos e demais pessoas ligadas ao emissor e aos participantes do consórcio", r.get("Num_Invest_Soc_Adm_Emp_Prop_Demais_Pess_Jurid_Emiss_Partic_Consorcio"), r.get("Qdte_VM_Soc_Adm_Emp_Prop_Demais_Pess_Jurid_Emiss_Partic_Consorcio") or r.get("Qtde_VM_Soc_Adm_Emp_Prop_Demais_Pess_Jurid_Emiss_Partic_Consorcio")),
            ]
        else:
            pairs = [
                ("Pessoas naturais", r.get("Nr_Pessoa_Fisica"), r.get("Qtd_Pessoa_Fisica") or r.get("Qtd_Cli_Pessoa_Fisica")),
                ("Clubes de investimento", r.get("Nr_Clube_Investimento"), r.get("Qtd_Clube_Investimento")),
                ("Fundos de investimento", r.get("Nr_Fundos_Investimento"), r.get("Qtd_Fundos_Investimento")),
                ("Entidades de previdência privada", r.get("Nr_Entidade_Previdencia_Privada"), r.get("Qtd_Entidade_Previdencia_Privada")),
                ("Companhias seguradoras", r.get("Nr_Companhia_Seguradora"), r.get("Qtd_Companhia_Seguradora")),
                ("Investidores estrangeiros", r.get("Nr_Investidor_Estrangeiro"), r.get("Qtd_Investidor_Estrangeiro") or r.get("Qtd_Cli_Investidor_Estrangeiro")),
                ("Instituições Intermediárias participantes do consórcio de distribuição", r.get("Nr_Instit_Intermed_Partic_Consorcio_Distrib"), r.get("Qtd_Instit_Intermed_Partic_Consorcio_Distrib")),
                ("Instituições financeiras ligadas ao emissor e aos participantes do consórcio", r.get("Nr_Instit_Financ_Emissora_Partic_Consorcio"), r.get("Qtd_Instit_Financ_Emissora_Partic_Consorcio")),
                ("Demais instituições financeiras", r.get("Nr_Demais_Instit_Financ"), r.get("Qtd_Demais_Instit_Financ")),
                ("Demais pessoas jurídicas ligadas ao emissor e aos participantes do consórcio", r.get("Nr_Demais_Pessoa_Juridica_Emissora_Partic_Consorcio"), r.get("Qtd_Demais_Pessoa_Juridica_Emissora_Partic_Consorcio") or r.get("Qtd_Cli_Pessoa_Juridica_Ligada_Adm")),
                ("Demais pessoas jurídicas", r.get("Nr_Demais_Pessoa_Juridica"), r.get("Qtd_Demais_Pessoa_Juridica") or r.get("Qtd_Cli_Pessoa_Juridica") or r.get("QtD_Cli_Demais_Pessoa_Juridica")),
                ("Sócios, administradores, empregados, prepostos e demais pessoas ligadas ao emissor e aos participantes do consórcio", r.get("Nr_Soc_Adm_Emp_Prop_Demais_Pess_Jurid_Emiss_Partic_Consorcio"), r.get("Qdt_Soc_Adm_Emp_Prop_Demais_Pess_Jurid_Emiss_Partic_Consorcio") or r.get("Qtd_Cli_Soc_Adm_Emp_Prop_Demais_Pess_Jurid_Emiss_Partic_Consorcio")),
            ]
        
        raw_items = []
        for cat, inv_raw, qtde_raw in pairs:
            inv = self._parse_int(inv_raw)
            qtde = self._parse_float(qtde_raw)
            raw_items.append({"categoria": cat, "investidores": inv, "qtde_vm": round(qtde, 4)})
            
        s_det = sum(item["qtde_vm"] for item in raw_items)
        if s_det <= 0 or vol_f <= 0:
            scale = 0.0
        elif s_det <= qtde_f * 1.05 and qtde_f > 0:
            scale = vol_f / qtde_f
        elif s_det <= vol_f * 1.05:
            scale = 1.0
        else:
            scale = vol_f / s_det
            
        for item in raw_items:
            item["vol_alocado"] = round(item["qtde_vm"] * scale, 2)
        return raw_items


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

        # 3. Priority 3: Explicit Prefixado terms or Pure Percentage / Fixed Rate without floating index keywords
        if any(w in text for w in ("PREFIXAD", "PRÉ-FIXAD", "PRE-FIXAD", "TAXA PRÉ", "TAXA PRE ", "TAXA FIXA", "REMUNERAÇÃO FIXA", "JUROS FIXOS")):
            return "PRÉ (Prefixado)", False
        if re.search(r'\d+[\d,.]*\s*%', text) or any(k in text for k in ("INTEGRALIZAÇÃO", "INTEGRALIZACAO", "ESCRITURA DE EMISSÃO", "ESCRITURA DE EMISSAO", "TABELA CONSTANTE")):
            has_floating_or_infla = re.search(r'\b(?:CDI|DI|IPCA|INPC|IGP-M|IGPM|INCC|SELIC|TR|ANBID|TJLP|LIBOR|FLUTUANTE|FLUTUANTES|OVER)\b', text) or any(k in text for k in ("TAXA DI", " DI+", " DI-", "% DI", "DI %", "DI/"))
            if not has_floating_or_infla:
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
            m2 = re.search(r'(\d+[\d,.]*\s*%\s*(?:a\.a\.|aa|a\.m\.|am|ao ano|[\+\-]\s*(?:CDI|IPCA|DI))?)', text, re.I)
            if m2:
                val = m2.group(1).strip()
                if idx_type == "CDI / DI" and "CDI" not in val.upper() and "DI" not in val.upper():
                    return f"CDI + {val}", True
                elif idx_type == "IPCA / Inflação" and "IPCA" not in val.upper():
                    return f"IPCA + {val}", True
                return val, True
            
            st_upper = str(r.get("Status_Requerimento", "")).strip().upper()
            is_active = any(k in st_upper for k in ("ANDAMENTO", "ANÁLISE INICIAL", "AGUARDANDO BOOKBUILDING", "EM ANÁLISE"))
            
            ativo_val = str(r.get("Valor_Mobiliario", "")).upper()
            if "FIDC" in ativo_val or "CREDIT" in ativo_val:
                return "Retorno Subordinado / Alvo (Ver Regulamento FIDC)", False
            elif any(x in ativo_val for x in ("FII", "FIAGRO", "IMOBIL", "AGRONEG")):
                return "Rentabilidade Alvo (Ver Regulamento)", False
            elif any(x in ativo_val for x in ("AÇÕES", "ACOES", "BDR")):
                return "Não Aplicável (Renda Variável / Ações)", False
            
            if not is_active and st_upper:
                if idx_type == "CDI / DI":
                    return "CDI + Spread (Ver Dossiê / API CVM)", False
                elif idx_type == "IPCA / Inflação":
                    return "IPCA + Spread (Ver Dossiê / API CVM)", False
                elif idx_type == "PRÉ (Prefixado)":
                    return "Taxa Prefixada (Ver Dossiê / API CVM)", False
                return "Não Informado no CSV (Ver Dossiê / API CVM)", False

            if idx_type == "IPCA / Inflação":
                inc = str(r.get("Titulo_incentivado", "")).strip().upper() == "S" or "12.431" in text or "12431" in text
                return "IPCA + Spread a Definir (Lei 12.431)" if inc else "IPCA + Spread a Definir (Bookbuilding)", False
            elif idx_type == "CDI / DI":
                return "CDI + Spread a Definir (Bookbuilding)", False
            elif idx_type == "PRÉ (Prefixado)":
                return "Taxa Prefixada a Definir", False
            return "Não Informado (CVM)", False

    def _sync_row_indexador(self, r):
        import re
        taxa = str(r.get("Taxa_Juros", "")).strip()
        t_upper = taxa.upper()
        if not taxa or taxa in ("Não Informado (CVM)", "N/A", "-", "--", "Não Informado"):
            return
        
        has_cdi = any(k in t_upper for k in ("CDI", " DI ", " DI+", " DI-", "% DI", "SELIC", "FLUTUANTE", "DI %", "DI+", "TAXA DI")) or t_upper.startswith("DI ") or t_upper.endswith(" DI") or re.search(r'\b(?:CDI|DI|SELIC|FLUTUANTE|FLUTUANTES|OVER|ANBID|TJLP|LIBOR)\b', t_upper)
        has_ipca = any(k in t_upper for k in ("IPCA", "INPC", "IGP-M", "IGPM", "TR ", "INFLA")) or t_upper.startswith("IPCA") or t_upper.endswith(" IPCA") or re.search(r'\b(?:IPCA|INPC|IGP-M|IGPM|INCC|TR|INFLAÇÃO|INFLACAO|IPCR)\b', t_upper)
        has_pre_keyword = any(k in t_upper for k in ("PRÉ", "PRE ", "PREFIX", "TAXA PRÉ", "TAXA FIXA", "REMUNERAÇÃO FIXA", "JUROS FIXOS"))
        
        if has_cdi:
            r["Indexador"] = "CDI / DI"
            r["Indexador_Inferido"] = False
        elif has_ipca:
            r["Indexador"] = "IPCA / Inflação"
            r["Indexador_Inferido"] = False
        elif has_pre_keyword or re.search(r'\d+[\d,.]*\s*%', taxa) or any(k in t_upper for k in ("INTEGRALIZAÇÃO", "INTEGRALIZACAO", "ESCRITURA DE EMISSÃO", "ESCRITURA DE EMISSAO", "TABELA CONSTANTE", "VALOR NOMINAL UNITÁRIO", "VALOR NOMINAL UNITARIO")):
            if not has_cdi and not has_ipca:
                r["Indexador"] = "PRÉ (Prefixado)"
                r["Indexador_Inferido"] = False

    def _extract_vencimento(self, r, is_hist):
        import re
        if is_hist:
            raw = str(r.get("Data_Vencimento", "")).strip()
            if not raw or raw in ("-", "--", "00/00/0000", "N/A"):
                return "N/I"
            if len(raw) >= 10 and raw[4] == "-":
                parts = raw.split("-")
                return f"{parts[1]}/{parts[0][-2:]}"
            elif len(raw) >= 10 and raw[2] == "/":
                parts = raw.split("/")
                return f"{parts[1]}/{parts[2][-2:]}"
            return raw[:7] if len(raw) >= 7 else "N/I"
        else:
            campos = r.get("Caracteristicas_CVM", [])
            if isinstance(campos, list):
                for c in campos:
                    if isinstance(c, dict):
                        nm = str(c.get("campoNome", "")).lower()
                        val = str(c.get("campoValor", "")).strip()
                        if "venc" in nm or "data de vencimento" in nm:
                            if val and val not in ("-", "--", "00/00/0000", "Não Informado"):
                                if len(val) >= 10 and val[2] == "/":
                                    parts = val.split("/")
                                    return f"{parts[1]}/{parts[2][-2:]}"
                                elif len(val) >= 10 and val[4] == "-":
                                    parts = val.split("-")
                                    return f"{parts[1]}/{parts[0][-2:]}"
                                elif len(val) >= 7 and val[2] == "/":
                                    return f"{val[:2]}/{val[-2:]}"
                                return val[:7]
            text = f"{r.get('Descricao_lastro','')} {r.get('Destinacao_recursos','')} {r.get('Ativos_alvo','')}"
            m = re.search(r'\b(?:vencimento|vence|venc\.?)\s+(?:em|dia|até)?\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{4})\b', text, re.I)
            if m:
                raw = m.group(1)
                if len(raw) == 10 and raw[4] == "-":
                    p = raw.split("-")
                    return f"{p[1]}/{p[0][-2:]}"
                elif len(raw) == 10 and raw[2] == "/":
                    p = raw.split("/")
                    return f"{p[1]}/{p[2][-2:]}"
                elif len(raw) == 7 and raw[2] == "/":
                    return f"{raw[:2]}/{raw[-2:]}"
            m2 = re.search(r'\b(?:vencimento\s+em\s+)(\d{4})\b', text, re.I)
            if m2:
                return f"Anual/{m2.group(1)[-2:]}"
            return "N/I"

    @staticmethod
    def _closest_vertex(year):
        """Given a maturity year, find the closest standard NTN-B vertex. Ties go to the longer vertex."""
        if year < 2026:
            return year
        return min(NTNB_VERTICES, key=lambda v: (abs(v - year), -v))

    def _extract_ntnb_reference(self, r):
        texts = [
            str(r.get("Taxa_Juros", "")),
            str(r.get("Descricao_Lastro", "")),
            str(r.get("Destinacao_Recursos", "")),
            str(r.get("Ativos_Alvo", "")),
            str(r.get("Descricao_lastro", "")),
            str(r.get("Destinacao_recursos", "")),
            str(r.get("Ativos_alvo", ""))
        ]
        # Caracteristicas_CVM is a list of dicts [{"campoNome": ..., "campoValor": ...}, ...]
        campos = r.get("Caracteristicas_CVM", [])
        if isinstance(campos, list):
            for c in campos:
                if isinstance(c, dict):
                    texts.append(str(c.get("campoValor", "")))
        # Taxa_Declarada can be True/False or a string from API
        td = r.get("Taxa_Declarada", "")
        if isinstance(td, str) and td:
            texts.append(td)

        full_text = " ".join(texts).upper()

        def _valid_4digit(y):
            return 2026 <= y <= 2060

        def _valid_2digit(yy):
            return 26 <= yy <= 60

        def _format_ntnb(y, from_text=True):
            if from_text and y in NTNB_VERTICES:
                return (f"NTN-B {y}", "declarada")
            else:
                return (f"NTN-B {self._closest_vertex(y)}", "aproximada")

        # Pattern 1: short form 2-digit with optional parentheses – e.g., "NTN-B35", "NTNB 35", "NTN-B (35)", "NTN-B(35) + 2,50%" (with negative lookahead)
        m = re.search(r'NTN-?\s*B\s*\(?\s*(2[6-9]|[3-5]\d|60)\s*\)?\b(?![\d/.])', full_text)
        if m:
            yy = int(m.group(1))
            if _valid_2digit(yy):
                return _format_ntnb(2000 + yy, from_text=True)

        # Pattern 2: windowed check requiring VENC/MATUR/PRAZO keyword – e.g. "NTN-B com vencimento em 15/08/2030" or "vencimento da NTN-B em 2035"
        m = re.search(r'NTN-?\s*B\b.{0,60}?\b(?:VENC\w*|VENCE\w*|PRAZO|MATUR\w*)\b.{0,30}?(20[2-6]\d)\b', full_text)
        if not m:
            m = re.search(r'(?:VENC\w*|VENCE\w*|PRAZO|MATUR\w*)\b.{0,45}?\bNTN-?\s*B\b.{0,30}?(20[2-6]\d)\b', full_text)
        if m:
            year = int(m.group(1))
            if _valid_4digit(year):
                return _format_ntnb(year, from_text=True)

        # Pattern 3: direct NTN-B date or year form – e.g. "NTN-B 15/05/2035", "NTN-B 2035"
        m = re.search(r'NTN-?\s*B\s*(?:\d{1,2}/\d{1,2}/)?(20[2-6]\d)\b', full_text)
        if m:
            year = int(m.group(1))
            if _valid_4digit(year):
                return _format_ntnb(year, from_text=True)

        # Pattern 4: Tesouro IPCA – "Tesouro IPCA+ ... 2035"
        m = re.search(r'TESOURO\s+IPCA\+?\s*.*?(\d{4})', full_text)
        if m:
            year = int(m.group(1))
            if _valid_4digit(year):
                return _format_ntnb(year, from_text=True)

        # Pattern 5: loose B + year – "B35" or "B(35)" only if text also contains NTN or TESOURO
        if "NTN" in full_text or "TESOURO" in full_text:
            m = re.search(r'\bB\s*-?\s*\(?\s*(2[6-9]|[3-5]\d|60)\s*\)?\b(?![\d/.])', full_text)
            if m:
                yy = int(m.group(1))
                if _valid_2digit(yy):
                    return _format_ntnb(2000 + yy, from_text=True)

        # Fallback by maturity when indexer is IPCA or inflation-linked
        idx_val = str(r.get("Indexador", "")).upper()
        if any(k in idx_val for k in ("IPCA", "INFLA", "INPC", "IGP-M")):
            venc = str(r.get("Vencimento", ""))
            year_found = None
            if venc and venc != "N/I":
                m_v = re.search(r'\b(20[2-6]\d|199\d)\b', venc)
                if m_v:
                    year_found = int(m_v.group(1))
                else:
                    m_v2 = re.search(r'(\d{2})$', venc.strip())
                    if m_v2:
                        yy = int(m_v2.group(1))
                        year_found = 2000 + yy if yy < 80 else 1900 + yy
            if not year_found or not _valid_4digit(year_found):
                m_txt = re.findall(r'\b(202[6-9]|20[3-6]\d)\b', full_text)
                if m_txt:
                    year_found = max(int(y) for y in m_txt)
            if year_found and _valid_4digit(year_found):
                return _format_ntnb(year_found, from_text=False)

        return ("Outras / Não Espec.", "nenhuma")

    def _enter_degraded_mode(self):
        self.rows = []
        self.last_update = "Aguardando conexão com servidor CVM (Modo Degradado - Reconectando em background...)"
        self._build_options_cache()
        import threading
        def _retry_loop():
            time.sleep(30)
            print("[DEGRADED MODE] Attempting background download retry from CVM portal...")
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
                with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(ZIP_PATH, "wb") as f:
                        while True:
                            chunk = resp.read(262144)
                            if not chunk:
                                break
                            f.write(chunk)
                if os.path.exists(ZIP_PATH) and os.path.getsize(ZIP_PATH) > 100000:
                    print("[DEGRADED MODE] Background download successful! Reloading data engine...")
                    self.load_from_zip(ZIP_PATH)
            except Exception as e:
                print(f"[DEGRADED MODE] Retry failed: {e}. Will keep retrying on next cycle.")
        threading.Thread(target=_retry_loop, daemon=True).start()

    def load_from_zip(self, zip_filepath):
        if not zip_filepath or not os.path.exists(str(zip_filepath)):
            print(f"[WARN] No local zip file found ({zip_filepath}). Entering DEGRADED MODE with background retry loop...")
            self._enter_degraded_mode()
            return

        print(f"Loading CSV files from {zip_filepath}...")
        unified = []
        try:
            z = zipfile.ZipFile(zip_filepath, "r")
        except Exception as e:
            print(f"[ERROR] Could not open zip file {zip_filepath}: {e}. Entering DEGRADED MODE...")
            self._enter_degraded_mode()
            return

        try:
            # 1. Resolução 160 (Modern 2023+)
            # NOTA DE INVESTIGAÇÃO (Item 9 - Coordenadores do Consórcio):
            # A coluna 'Grupo_Coordenador' no CSV oferta_resolucao_160.csv não lista as instituições participantes do consórcio,
            # mas sim a categoria/papel societário do coordenador líder (ex: 'COORDENADOR PLENO', 'SECURITIZADORA', 'ADMINISTRADOR DE CARTEIRA').
            # Além disso, a API REST pública da CVM (/sre-publico-cvm/rest/sitePublico/pesquisar/requerimento/{id})
            # expõe em 'dadosColocacao' apenas contagens consolidadas sem a lista nominal dos bancos co-gerentes.
            # Conforme especificação 9.4, documentamos esta limitação oficial da fonte CVM e não exibiremos consórcio vazio.
            with z.open("oferta_resolucao_160.csv") as f:
                wrapper = io.TextIOWrapper(f, encoding="latin-1", errors="replace", newline="")
                reader = csv.DictReader(wrapper, delimiter=";")
                for r in reader:
                    data_clean = (r.get("Data_Registro") or r.get("Data_requerimento") or "")[:10]
                    ano = data_clean[:4]
                    if len(ano) != 4 or not ano.isdigit():
                        continue
                    
                    idx_type, idx_inferido = self._infer_indexador(r, is_hist=False)
                    taxa_juros, taxa_declarada = self._extract_taxa_juros(r, idx_type, is_hist=False)
                    venc_clean = self._extract_vencimento(r, is_hist=False)
                    
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
                    
                    row_dict = {
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
                        "Vencimento": venc_clean,
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
                        "Vol_Pessoa_Fisica": vol_pf,
                        "Vol_Fundos": vol_fd,
                        "Vol_Estrangeiro": vol_est,
                        "Vol_Previdencia": vol_prev,
                        "Vol_Seguradoras": vol_seg,
                        "Vol_Instituicoes": vol_inst,
                        "Qtd_Inv_Pessoa_Fisica": self._parse_int(r.get("Num_Invest_Pessoa_Natural")),
                        "Qtd_Inv_Fundos": self._parse_int(r.get("Num_Invest_Fundos_Investimento")),
                        "Qtd_Inv_Estrangeiro": self._parse_int(r.get("Num_Invest_Investidor_Estrangeiro")),
                        "Qtd_Inv_Previdencia": self._parse_int(r.get("Num_Invest_Entidade_Previdencia_Privada")),
                        "Qtd_Inv_Seguradoras": self._parse_int(r.get("Num_Invest_Companhia_Seguradora")),
                        "Qtd_Inv_Instituicoes": self._parse_int(r.get("Num_Invest_Instit_Intermed_Partic_Consorcio_Distrib")) + self._parse_int(r.get("Num_Invest_Demais_Instit_Financ")),
                        "Demografia_Detalhada": self._build_demografia_detalhada(r, vol_float, qtde_float, is_hist=False),
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
                    }
                    row_dict["Lider_Original"] = row_dict.get("Lider", "Não Informado")
                    lider_norm, consorcio_str, consorcio_list = self._extract_coordenadores(row_dict)
                    row_dict["Lider"] = lider_norm
                    row_dict["Consorcio"] = consorcio_str
                    row_dict["Consorcio_List"] = consorcio_list
                    self._sync_row_indexador(row_dict)
                    ref, fonte = self._extract_ntnb_reference(row_dict)
                    row_dict["Referencia_NTNB"] = ref
                    row_dict["NTNB_Fonte"] = fonte
                    unified.append(row_dict)

            # 2. Instrução 400/476 (Historical up to 2023)
            with z.open("oferta_distribuicao.csv") as f:
                wrapper = io.TextIOWrapper(f, encoding="latin-1", errors="replace", newline="")
                reader = csv.DictReader(wrapper, delimiter=";")
                for r in reader:
                    data_clean = (r.get("Data_Registro_Oferta") or r.get("Data_Inicio_Oferta") or "")[:10]
                    ano = data_clean[:4]
                    if len(ano) != 4 or not ano.isdigit():
                        continue
                    
                    idx_type, idx_inferido = self._infer_indexador(r, is_hist=True)
                    taxa_juros, taxa_declarada = self._extract_taxa_juros(r, idx_type, is_hist=True)
                    venc_clean = self._extract_vencimento(r, is_hist=True)
                    
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
                    
                    row_dict = {
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
                        "Vencimento": venc_clean,
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
                        "Demografia_Detalhada": self._build_demografia_detalhada(r, vol_float, qtde_float, is_hist=True),
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
                    }
                    row_dict["Lider_Original"] = row_dict.get("Lider", "Não Informado")
                    lider_norm, consorcio_str, consorcio_list = self._extract_coordenadores(row_dict)
                    row_dict["Lider"] = lider_norm
                    row_dict["Consorcio"] = consorcio_str
                    row_dict["Consorcio_List"] = consorcio_list
                    self._sync_row_indexador(row_dict)
                    ref, fonte = self._extract_ntnb_reference(row_dict)
                    row_dict["Referencia_NTNB"] = ref
                    row_dict["NTNB_Fonte"] = fonte
                    unified.append(row_dict)
            z.close()
        except Exception as e:
            try:
                z.close()
            except Exception:
                pass
            print(f"[ERROR] Could not read or unpack zip file {zip_filepath}: {e}. Entering DEGRADED MODE...")
            self._enter_degraded_mode()
            return

        # Build issuer historical average volume cache
        import hashlib
        issuer_vols = {}
        issuer_qtys = {}
        for r in unified:
            em = r["Emissor"]
            at_key = r["Ativo"]
            if r["Volume_Float"] > 0:
                issuer_vols.setdefault((em, at_key), []).append(r["Volume_Float"])
                issuer_vols.setdefault(em, []).append(r["Volume_Float"])
            if r["Qtde_Float"] > 0:
                issuer_qtys.setdefault((em, at_key), []).append(r["Qtde_Float"])
                issuer_qtys.setdefault(em, []).append(r["Qtde_Float"])

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

            # 2. Honestidade de Taxas e Status: se não estiver explicitamente informada, verificar status real (nunca marcar encerradas como Bookbuilding nem usar histórico do emissor)
            if not r.get("Taxa_Declarada") or any(w in r["Taxa_Juros"] for w in ("Spread", "Flutuante", "Não Informado", "a Definir")):
                st_upper = str(r.get("Status", "")).strip().upper()
                is_active = any(k in st_upper for k in ("ANDAMENTO", "ANÁLISE INICIAL", "AGUARDANDO BOOKBUILDING", "EM ANÁLISE"))
                at_upper = str(r.get("Ativo", "")).upper()
                
                if "FIDC" in at_upper or "CREDIT" in at_upper:
                    r["Taxa_Juros"] = "Retorno Subordinado / Alvo (Ver Regulamento FIDC)"
                elif any(x in at_upper for x in ("FII", "FIAGRO", "IMOBIL", "AGRONEG")):
                    r["Taxa_Juros"] = "Rentabilidade Alvo (Ver Regulamento)"
                elif any(x in at_upper for x in ("AÇÕES", "ACOES", "BDR")):
                    r["Taxa_Juros"] = "Não Aplicável (Renda Variável / Ações)"
                elif not is_active:
                    if idx == "CDI / DI":
                        r["Taxa_Juros"] = "CDI + Spread (Ver Dossiê / API CVM)"
                    elif idx == "IPCA / Inflação":
                        r["Taxa_Juros"] = "IPCA + Spread (Ver Dossiê / API CVM)"
                    elif idx == "PRÉ (Prefixado)":
                        r["Taxa_Juros"] = "Taxa Prefixada (Ver Dossiê / API CVM)"
                    else:
                        r["Taxa_Juros"] = "Não Informado no CSV (Ver Dossiê / API CVM)"
                else:
                    if idx == "CDI / DI":
                        r["Taxa_Juros"] = "CDI + Spread a Definir (Bookbuilding)"
                    elif idx == "IPCA / Inflação":
                        r["Taxa_Juros"] = "IPCA + Spread a Definir (Bookbuilding)"
                    elif idx == "PRÉ (Prefixado)":
                        r["Taxa_Juros"] = "Taxa Prefixada a Definir"
                    else:
                        r["Taxa_Juros"] = "Não Informado (CVM)"
            
            if r.get("Taxa_Declarada") and r.get("Taxa_Juros"):
                t_upper = str(r["Taxa_Juros"]).upper()
                if any(k in t_upper for k in ("CDI", " DI ", " DI+", " DI-", "% DI", "SELIC", "FLUTUANTE", "DI %")):
                    r["Indexador"] = "CDI / DI"
                    r["Indexador_Inferido"] = False
                elif any(k in t_upper for k in ("IPCA", "INPC", "IGP-M", "IGPM", "TR ")):
                    r["Indexador"] = "IPCA / Inflação"
                    r["Indexador_Inferido"] = False
                elif any(k in t_upper for k in ("PRÉ", "PRE ", "PREFIX")) or re.match(r'^\d+[\d,.]*\s*%', str(r["Taxa_Juros"])):
                    r["Indexador"] = "PRÉ (Prefixado)"
                    r["Indexador_Inferido"] = False

        # Sort descending by Data_Clean
        unified.sort(key=lambda x: x["Data_Clean"], reverse=True)
        self.rows = unified

        # Apply persistent SRE enrichment cache to loaded offerings
        sre_cache_path = os.path.join(CACHE_DIR, "sre_enrichment_cache.json")
        if os.path.exists(sre_cache_path):
            cached_sre = {}
            try:
                import json
                with open(sre_cache_path, "r", encoding="utf-8") as f:
                    cached_sre = json.load(f)
            except Exception as e:
                print(f"[ERROR] SRE Cache corrupted on load: {e}. Attempting automatic recovery...")
                try:
                    with open(sre_cache_path, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()
                    decoder = json.JSONDecoder()
                    obj, _ = decoder.raw_decode(txt)
                    if isinstance(obj, dict) and len(obj) > 10:
                        cached_sre = obj
                        print(f"[RECOVERY] Successfully recovered {len(cached_sre)} entries via raw_decode!")
                    else:
                        raise ValueError("raw_decode insufficient")
                except Exception:
                    matches = re.findall(r'("\d{3,7}")\s*:\s*(\{(?:[^{}]|\{[^{}]*\})*\})', txt)
                    for k_str, v_str in matches:
                        try:
                            cached_sre[json.loads(k_str)] = json.loads(v_str)
                        except Exception:
                            pass
                    if cached_sre:
                        print(f"[RECOVERY] Successfully recovered {len(cached_sre)} entries via regex salvage!")
                if cached_sre:
                    try:
                        tmp_p = sre_cache_path + ".tmp"
                        with open(tmp_p, "w", encoding="utf-8") as f:
                            json.dump(cached_sre, f, ensure_ascii=False)
                        os.replace(tmp_p, sre_cache_path)
                    except Exception:
                        pass

            if cached_sre:
                matches_count = 0
                for r in self.rows:
                    req_id = str(r.get("Numero_Requerimento") or r.get("Id_Processo") or "").strip()
                    if req_id and req_id in cached_sre:
                        matches_count += 1
                        c_data = cached_sre[req_id]
                        if c_data.get("Taxa_Juros"):
                            r["Taxa_Juros"] = c_data["Taxa_Juros"]
                            r["Taxa_Declarada"] = True
                            r["Remuneracao_API_CVM"] = c_data["Taxa_Juros"]
                        if c_data.get("Vencimento") and c_data.get("Vencimento") != "N/I":
                            r["Vencimento"] = c_data["Vencimento"]
                        if c_data.get("Caracteristicas_CVM"):
                            r["Caracteristicas_CVM"] = c_data["Caracteristicas_CVM"]
                        self._sync_row_indexador(r)
                        ref, fonte = self._extract_ntnb_reference(r)
                        r["Referencia_NTNB"] = ref
                        r["NTNB_Fonte"] = fonte
                total_rows = max(len(self.rows), 1)
                print(f"Applied {matches_count} cached SRE enrichments out of {len(cached_sre)} cache entries (match rate: {matches_count/total_rows*100:.1f}% of offerings).")

        for r in self.rows:
            self._sync_row_indexador(r)

        try:
            with zipfile.ZipFile(zip_filepath, "r") as z:
                dt = z.getinfo("oferta_resolucao_160.csv").date_time
                self.last_update = datetime(*dt).strftime("%d/%m/%Y %H:%M:%S") + " (CVM Oficial)"
        except Exception:
            mtime = os.path.getmtime(zip_filepath) if (zip_filepath and os.path.exists(str(zip_filepath))) else datetime.now().timestamp()
            self.last_update = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S") + " (CVM Oficial)"
        self._build_options_cache()
        self._start_sre_background_worker()
        print(f"Data engine loaded {len(self.rows)} offerings successfully.")
        self._log_top_coordenadores()

    def _build_options_cache(self):
        anos = sorted(list(set(r["Ano"] for r in self.rows)), reverse=True)
        ativos = sorted(list(set(r["Ativo"] for r in self.rows if r["Ativo"] != "Não Informado")))
        status_list = sorted(list(set(r["Status"] for r in self.rows if r["Status"] != "Não Informado")))
        indexadores = ["Todos", "CDI / DI", "IPCA / Inflação", "PRÉ (Prefixado)", "Outros / Não Informado"]
        
        valid_dates = sorted(list(set(str(r.get("Data_Clean", ""))[:7] for r in self.rows if len(str(r.get("Data_Clean", ""))) >= 7 and str(r.get("Data_Clean", ""))[:4].isdigit())))
        data_min = valid_dates[0] if valid_dates else "2023-01"
        data_max = valid_dates[-1] if valid_dates else "2026-07"
        
        std_ativos = ["Debêntures", "CRI", "CRA", "FIDC", "Nota Comercial", "CPR", "FII", "Ações"]
        ordered_ativos = ["Todos"] + std_ativos + [a for a in ativos if len(a) > 1 and a not in std_ativos][:35]
        
        self.options_cache = {
            "anos": ["Recentes (2023-2026)", "Todos"] + anos[:20],
            "ritos": ["Todos", "Automático", "Ordinário"],
            "ativos": ordered_ativos,
            "status": ["Todos"] + status_list[:15],
            "indexadores": indexadores,
            "publicos": ["Todos", "Profissional", "Qualificado", "Geral"],
            "data_min": data_min,
            "data_max": data_max
        }

    def _start_sre_background_worker(self):
        import threading
        if hasattr(self, "_worker_started") and self._worker_started:
            return
        self._worker_started = True
        
        def worker_loop():
            import time
            import json
            import urllib.request
            import ssl
            sre_cache_path = os.path.join(CACHE_DIR, "sre_enrichment_cache.json")
            cached_sre = {}
            if os.path.exists(sre_cache_path):
                try:
                    with open(sre_cache_path, "r", encoding="utf-8") as f:
                        cached_sre = json.load(f)
                except Exception:
                    pass
            
            candidates = [
                r for r in self.rows
                if r.get("Ano") in ("2026", "2025", "2024", "2023")
                and (not r.get("Taxa_Declarada") or not r.get("Vencimento") or r.get("Vencimento") == "N/I" or r.get("Referencia_NTNB") in ("Outras / Não Espec.", "N/I", ""))
                and (r.get("Numero_Requerimento") or r.get("Id_Processo"))
                and r.get("Indexador") in ("CDI / DI", "IPCA / Inflação", "PRÉ (Prefixado)")
            ]
            candidates.sort(key=lambda x: x.get("Volume_Float", 0), reverse=True)
            
            ctx = ssl.create_default_context()
            def _fetch_api_sre(req_id):
                try:
                    api_url = f"https://web.cvm.gov.br/sre-publico-cvm/rest/sitePublico/pesquisar/requerimento/{req_id}"
                    req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, context=ctx, timeout=2.0) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
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
                            return taxa_encontrada, campos_encontrados, venc_encontrado
                except Exception:
                    pass
                return None, [], None

            def _apply_row_update(r, taxa_e, campos_e, venc_e, req_id):
                updated = False
                if taxa_e or campos_e or venc_e:
                    if taxa_e:
                        r["Taxa_Juros"] = taxa_e
                        r["Taxa_Declarada"] = True
                        r["Remuneracao_API_CVM"] = taxa_e
                        updated = True
                    if campos_e:
                        r["Caracteristicas_CVM"] = campos_e
                        updated = True
                    if venc_e:
                        if len(venc_e) >= 10 and venc_e[2] == "/":
                            parts = venc_e.split("/")
                            r["Vencimento"] = f"{parts[1]}/{parts[2][-2:]}"
                        elif len(venc_e) >= 10 and venc_e[4] == "-":
                            parts = venc_e.split("-")
                            r["Vencimento"] = f"{parts[1]}/{parts[0][-2:]}"
                        elif len(venc_e) >= 7 and venc_e[2] == "/":
                            r["Vencimento"] = f"{venc_e[:2]}/{venc_e[-2:]}"
                        else:
                            r["Vencimento"] = venc_e[:7]
                        updated = True
                    self._sync_row_indexador(r)
                    ref, fonte = self._extract_ntnb_reference(r)
                    r["Referencia_NTNB"] = ref
                    r["NTNB_Fonte"] = fonte
                    cached_sre[req_id] = {
                        "Taxa_Juros": taxa_e,
                        "Vencimento": r.get("Vencimento"),
                        "Caracteristicas_CVM": campos_e
                    }
                return updated

            from concurrent.futures import ThreadPoolExecutor, as_completed
            def _save_sre_cache():
                try:
                    tmp_p = sre_cache_path + ".tmp"
                    with open(tmp_p, "w", encoding="utf-8") as f:
                        json.dump(cached_sre, f, ensure_ascii=False)
                    os.replace(tmp_p, sre_cache_path)
                except Exception:
                    pass

            top_batch = [r for r in candidates[:300] if str(r.get("Numero_Requerimento") or r.get("Id_Processo") or "").strip() not in cached_sre]
            updated_count = 0
            if top_batch:
                with ThreadPoolExecutor(max_workers=10) as ex:
                    futs = {}
                    for r in top_batch:
                        rid = str(r.get("Numero_Requerimento") or r.get("Id_Processo") or "").strip()
                        if rid and rid.isdigit():
                            futs[ex.submit(_fetch_api_sre, rid)] = (r, rid)
                    for f in as_completed(futs):
                        r, rid = futs[f]
                        tx, cp, vn = f.result()
                        if _apply_row_update(r, tx, cp, vn, rid):
                            updated_count += 1
                if updated_count > 0:
                    _save_sre_cache()

            for r in candidates[300:]:
                req_id = str(r.get("Numero_Requerimento") or r.get("Id_Processo") or "").strip()
                if not req_id or not req_id.isdigit() or req_id in cached_sre:
                    continue
                tx, cp, vn = _fetch_api_sre(req_id)
                if _apply_row_update(r, tx, cp, vn, req_id):
                    updated_count += 1
                    if updated_count % 15 == 0:
                        _save_sre_cache()
                time.sleep(0.04)

            if updated_count > 0:
                _save_sre_cache()
        
        t = threading.Thread(target=worker_loop, daemon=True)
        t.start()

    def get_filtered_rows(self, ano="Recentes (2023-2026)", rito="Todos", ativo="Todos", status="Todos", indexador="Todos", publico="Todos", regime="Todos", busca="", data_de="", data_ate=""):
        def _to_list(val):
            if isinstance(val, (list, tuple, set)):
                if not val:
                    return ["Todos"]
                items = []
                for v in val:
                    items.extend([i.strip() for i in str(v).split(",") if i.strip()])
                if not items or any(i == "Todos" or i.startswith("Todos os") for i in items):
                    return ["Todos"]
                return items
            if not val:
                return ["Todos"]
            items = [i.strip() for i in str(val).split(",") if i.strip()]
            if not items or any(i == "Todos" or i.startswith("Todos os") for i in items):
                return ["Todos"]
            return items

        ano_list = _to_list(ano)
        rito_list = _to_list(rito)
        ativo_list = _to_list(ativo)
        status_list = _to_list(status)
        idx_list = _to_list(indexador)
        pub_list = _to_list(publico)
        reg_list = _to_list(regime)
        busca_lower = busca.lower() if busca else ""
        
        has_date_range = bool((data_de and str(data_de).strip() not in ("Todos", "")) or (data_ate and str(data_ate).strip() not in ("Todos", "")))
        de_str = str(data_de).strip()[:7] if (data_de and str(data_de).strip() not in ("Todos", "")) else ""
        ate_str = str(data_ate).strip()[:7] if (data_ate and str(data_ate).strip() not in ("Todos", "")) else ""
        
        res = []
        for r in self.rows:
            if "Todos" not in reg_list:
                match_reg = False
                for reg_item in reg_list:
                    if reg_item == "160" and "160" in r["Regime"]: match_reg = True; break
                    elif reg_item == "hist" and "ICVM" in r["Regime"]: match_reg = True; break
                    elif reg_item.lower() in r["Regime"].lower(): match_reg = True; break
                if not match_reg: continue
            
            if has_date_range:
                r_dt = str(r.get("Data_Clean", ""))[:7]
                if len(r_dt) >= 7 and r_dt[:4].isdigit():
                    if de_str and r_dt < de_str: continue
                    if ate_str and r_dt > ate_str: continue
                else:
                    continue
            elif "Todos" not in ano_list:
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
                    elif ("CPR" in at_upper or "CÉDULA DE PRODUTO RURAL" in at_upper or "CEDULA DE PRODUTO RURAL" in at_upper or "PRODUTO RURAL" in at_upper) and ("CPR" in r_at_upper or "PRODUTO RURAL" in r_at_upper or "CÉDULA DE PRODUTO RURAL" in r_at_upper or "CEDULA DE PRODUTO RURAL" in r_at_upper): match_at = True; break
                    elif ("NOTA COMERCIAL" in at_upper or "NOTAS COMERCIAIS" in at_upper or "PROMISS" in at_upper or "NC" == at_upper) and ("NOTA COMERCIAL" in r_at_upper or "NOTAS COMERCIAIS" in r_at_upper or "PROMISS" in r_at_upper): match_at = True; break
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
                    busca_lower not in str(r.get("Consorcio", "")).lower() and
                    busca_lower not in r["Id_Processo"].lower() and
                    busca_lower not in r["Ativo"].lower() and
                    busca_lower not in r["Status"].lower()):
                    continue
            
            res.append(r)
        return res

engine = CVMDataEngine()
