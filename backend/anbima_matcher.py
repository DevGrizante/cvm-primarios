import pandas as pd
import glob
import os
import sys
import re
import json

def normalize_name(name):
    name = str(name).upper().strip()
    name = re.sub(r'[^A-Z0-9 ]', '', name)
    name = re.sub(r'\b(SA|LTDA|PARTICIPACOES|S A|S|A)\b', '', name)
    return ' '.join(name.split())

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
        
    latest_anbima = max(anbima_files, key=os.path.getmtime)
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
    cvm_issuers_prefix = {}
    for r in engine.rows:
        em = normalize_name(r.get('Emissor', ''))
        cnpj = r.get('CNPJ_Emissor', '')
        if em and cnpj:
            prefix = em.replace(' ', '')[:6]
            if prefix not in cvm_issuers_prefix:
                cvm_issuers_prefix[prefix] = set()
            cvm_issuers_prefix[prefix].add(cnpj)
            
    mapping = {}
    matches = 0
    
    for idx, row in df.iterrows():
        em = normalize_name(row.get(3, ''))
        prefix = em.replace(' ', '')[:6]
        cnpjs = cvm_issuers_prefix.get(prefix)
        if not cnpjs: continue
            
        venc_mm_yyyy = extract_mm_yyyy(row.get(11))
        serie = parse_series_number(row.get(18, ''))
        
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
            
        for cnpj in cnpjs:
            key = f"{cnpj}_{venc_mm_yyyy}_{serie}"
            mapping[key] = {
                "ticker": ticker,
                "rentabilidade": rentabilidade,
                "isin": isin,
                "data_rentabilidade": data_rentabilidade,
                "serie_anbima": serie
            }
        matches += 1
        
    print(f"Total de ofertas Anbima mapeadas com sucesso: {matches}")
    
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secondary_market.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)
        
    print(f"Mapeamento salvo em {out_path}")

if __name__ == '__main__':
    main()
