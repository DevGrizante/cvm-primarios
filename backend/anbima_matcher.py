import pandas as pd
import glob
import os
import sys
import re
import json
import datetime

def extract_date_from_filename(filepath):
    filename = os.path.basename(filepath)
    # expected format: titulos-privados-caracteristicas-DD-MM-YYYY-HH-MM-SS.xls
    m = re.search(r'(\d{2}-\d{2}-\d{4}-\d{2}-\d{2}-\d{2})', filename)
    if m:
        date_str = m.group(1)
        try:
            return datetime.datetime.strptime(date_str, "%d-%m-%Y-%H-%M-%S")
        except ValueError:
            pass
    # fallback to mtime if no valid date found in filename
    return datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

def normalize_name(name):
    name = str(name).upper().strip()
    name = re.sub(r'[^A-Z0-9 ]', '', name)
    name = re.sub(r'\b(SA|LTDA|PARTICIPACOES|S A|S|A)\b', '', name)
    return ' '.join(name.split())

def extract_exact_date(date_obj):
    if pd.isnull(date_obj): return ""
    try:
        return date_obj.strftime("%d_%m_%Y")
    except:
        s = str(date_obj).strip()
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
        if m:
            dd = m.group(1).zfill(2)
            mm = m.group(2).zfill(2)
            yy = m.group(3)
            if len(yy) == 2: yy = "20" + yy
            return f"{dd}_{mm}_{yy}"
        return ""

def extract_mm_yyyy(date_obj):
    if pd.isnull(date_obj): return ""
    try:
        return date_obj.strftime("%m_%Y")
    except:
        s = str(date_obj).strip()
        parts = s.split('/')
        if len(parts) >= 3:
            return f"{parts[1].zfill(2)}_{parts[2][-4:]}"
        elif len(parts) == 2:
            year = parts[1]
            if len(year) == 2: year = "20" + year
            return f"{parts[0].zfill(2)}_{year}"
        return s

def parse_series_number(text):
    if not text:
        return 1
    text = str(text).upper().strip()
    if 'U' in text or 'UNICA' in text or 'ÚNICA' in text:
        return 1
    m = re.search(r'(\d+)', text)
    if m:
        return int(m.group(1))
    return 1

def main():
    print("Iniciando ANBIMA Matcher...")
    
    anbima_folder = r'E:\programacao\Emissoes\Data_set\Anbima'
    anbima_files = glob.glob(os.path.join(anbima_folder, '*.xls'))
    if not anbima_files:
        print("Nenhum arquivo .xls encontrado na pasta ANBIMA.")
        return
        
    latest_anbima = max(anbima_files, key=extract_date_from_filename)
    print(f"Lendo base ANBIMA mais recente: {os.path.basename(latest_anbima)}")
    df = pd.read_excel(latest_anbima, skiprows=1, header=None)
    
    try:
        from data_engine import engine
    except ModuleNotFoundError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from data_engine import engine
        
    print("Carregando base da CVM...")
    engine.ensure_data()
    
    print("Normalizando Emissores da CVM...")
    cvm_issuers_exact = {}
    cvm_issuers_prefix = {}
    for r in engine.rows:
        em = normalize_name(r.get('Emissor', ''))
        cnpj = r.get('CNPJ_Emissor', '')
        if em and cnpj:
            if em not in cvm_issuers_exact:
                cvm_issuers_exact[em] = set()
            cvm_issuers_exact[em].add(cnpj)
            
            prefix = em.replace(' ', '')[:6]
            if prefix not in cvm_issuers_prefix:
                cvm_issuers_prefix[prefix] = set()
            cvm_issuers_prefix[prefix].add(em)
            
    mapping = {}
    matches = 0
    import difflib
    
    for idx, row in df.iterrows():
        em = normalize_name(row.get(3, ''))
        
        cnpjs = cvm_issuers_exact.get(em)
        if not cnpjs:
            prefix = em.replace(' ', '')[:6]
            candidates = list(cvm_issuers_prefix.get(prefix, []))
            if candidates:
                best_matches = difflib.get_close_matches(em, candidates, n=1, cutoff=0.85)
                if best_matches:
                    cnpjs = cvm_issuers_exact[best_matches[0]]
        
        if not cnpjs: continue
            
        venc_exact = extract_exact_date(row.get(11))
        venc_mm_yyyy = extract_mm_yyyy(row.get(11))
        serie = parse_series_number(row.get(8, ''))
        
        ticker = str(row.get(1, '')).strip()
        rentabilidade = str(row.get(6, '')).strip()
        isin = str(row.get(16, '')).strip()
        
        data_rentabilidade = row.get(12)
        if pd.notnull(data_rentabilidade):
            try:
                data_rentabilidade = data_rentabilidade.strftime('%d/%m/%Y')
            except:
                data_rentabilidade = str(data_rentabilidade)
        else:
            data_rentabilidade = ""
            
        if not ticker or ticker == 'nan' or not venc_mm_yyyy:
            continue
            
        data = {
            "ticker": ticker,
            "rentabilidade": rentabilidade,
            "isin": isin,
            "data_rentabilidade": data_rentabilidade,
            "serie_anbima": serie
        }
        
        for cnpj in cnpjs:
            if venc_exact:
                key_exact = f"{cnpj}_{venc_exact}_{serie}"
                mapping[key_exact] = data
            
            key_mmyyyy = f"{cnpj}_{venc_mm_yyyy}_{serie}"
            if key_mmyyyy not in mapping or not mapping[key_mmyyyy]: 
                mapping[key_mmyyyy] = data

        matches += 1
        
    print(f"Total de ofertas Anbima mapeadas com sucesso: {matches}")
    
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secondary_market.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)
        
    print(f"Mapeamento salvo em {out_path}")

if __name__ == '__main__':
    main()
