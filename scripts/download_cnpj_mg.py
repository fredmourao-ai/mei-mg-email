import csv
import os
import sys
import zipfile
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RECEITA_DIR = BASE_DIR / "data" / "receita"
TEMP_ZIP = RECEITA_DIR / "temp.zip"

# URL base oficial/mirror alternativo da Receita Federal
BASE_URL = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"


def download_file(url: str, dest: Path) -> None:
    print(f"Baixando: {url} -> {dest.name}...")
    
    # Adiciona User-Agent para evitar bloqueios simples de crawler
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    
    with urllib.request.urlopen(req) as response, open(dest, "wb") as out_file:
        meta = response.info()
        file_size = int(meta.get("Content-Length", 0))
        downloaded = 0
        block_size = 8192
        last_pct = -1
        
        while True:
            buffer = response.read(block_size)
            if not buffer:
                break
            downloaded += len(buffer)
            out_file.write(buffer)
            
            if file_size > 0:
                pct = int(downloaded * 100 / file_size)
                if pct % 10 == 0 and pct != last_pct:
                    print(f"  Progresso: {pct}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)")
                    last_pct = pct
    print(f"Download concluído: {dest.name}")


def process_zip_csv(zip_path: Path, output_csv: Path, filter_func) -> int:
    matched_count = 0
    with zipfile.ZipFile(zip_path) as z:
        # Pega o primeiro arquivo dentro do ZIP (costuma ser o CSV)
        csv_filename = [name for name in z.namelist() if name.upper().endswith(".CSV") or not "." in name][0]
        print(f"  Lendo e filtrando arquivo {csv_filename}...")
        
        # Abre em modo binário e envelopa para decodificar como Latin-1
        with z.open(csv_filename) as f:
            # Lê em chunks para decodificar linha por linha
            import io
            reader = csv.reader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
            
            with open(output_csv, "a", encoding="latin-1", newline="") as out_f:
                writer = csv.writer(out_f, delimiter=";")
                for row in reader:
                    if not row:
                        continue
                    if filter_func(row):
                        writer.writerow(row)
                        matched_count += 1
                        
    print(f"  Filtro aplicado. {matched_count} linhas gravadas em {output_csv.name}")
    return matched_count


def main() -> None:
    RECEITA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. ESTABELECENTOS (0 a 9)
    est_output = RECEITA_DIR / "ESTABELECIMENTOS_mg.csv"
    if est_output.exists():
        print(f"Arquivo {est_output.name} já existe. Pulando etapa de estabelecimentos.")
        # Se o arquivo já existe, lê os CNPJs básicos para as etapas seguintes
        mg_cnpj_basicos = set()
        with open(est_output, encoding="latin-1", newline="") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if row:
                    mg_cnpj_basicos.add(row[0].zfill(8))
    else:
        mg_cnpj_basicos = set()
        print("=== ETAPA 1: ESTABELECIMENTOS (MG) ===")
        for i in range(10):
            filename = f"Estabelecimentos{i}.zip"
            url = f"{BASE_URL}{filename}"
            try:
                download_file(url, TEMP_ZIP)
                
                def filter_mg(row):
                    # UF está na coluna index 19 (Estabelecimentos)
                    if len(row) > 19 and row[19] == "MG":
                        cnpj_basico = row[0].zfill(8)
                        mg_cnpj_basicos.add(cnpj_basico)
                        return True
                    return False
                
                process_zip_csv(TEMP_ZIP, est_output, filter_mg)
            except Exception as e:
                print(f"Erro ao processar {filename}: {e}")
            finally:
                if TEMP_ZIP.exists():
                    TEMP_ZIP.unlink()
                    
    print(f"Total de CNPJs básicos em MG encontrados: {len(mg_cnpj_basicos)}")
    
    if not mg_cnpj_basicos:
        print("Nenhuma empresa de MG encontrada. Abortando.")
        return

    # 2. EMPRESAS (0 a 9)
    emp_output = RECEITA_DIR / "EMPRESAS_mg.csv"
    if emp_output.exists():
        print(f"Arquivo {emp_output.name} já existe. Pulando etapa de empresas.")
    else:
        print("=== ETAPA 2: EMPRESAS (Razão Social de MG) ===")
        for i in range(10):
            filename = f"Empresas{i}.zip"
            url = f"{BASE_URL}{filename}"
            try:
                download_file(url, TEMP_ZIP)
                
                def filter_empresas(row):
                    # CNPJ básico está na coluna index 0 (Empresas)
                    if row and row[0].zfill(8) in mg_cnpj_basicos:
                        return True
                    return False
                
                process_zip_csv(TEMP_ZIP, emp_output, filter_empresas)
            except Exception as e:
                print(f"Erro ao processar {filename}: {e}")
            finally:
                if TEMP_ZIP.exists():
                    TEMP_ZIP.unlink()

    # 3. SIMPLES
    sim_output = RECEITA_DIR / "SIMPLES_mg.csv"
    if sim_output.exists():
        print(f"Arquivo {sim_output.name} já existe. Pulando etapa de Simples/MEI.")
    else:
        print("=== ETAPA 3: SIMPLES (MEI de MG) ===")
        filename = "Simples.zip"
        url = f"{BASE_URL}{filename}"
        try:
            download_file(url, TEMP_ZIP)
            
            def filter_simples(row):
                # CNPJ básico está na coluna index 0 (Simples)
                if row and row[0].zfill(8) in mg_cnpj_basicos:
                    return True
                return False
            
            process_zip_csv(TEMP_ZIP, sim_output, filter_simples)
        except Exception as e:
            print(f"Erro ao processar {filename}: {e}")
        finally:
            if TEMP_ZIP.exists():
                TEMP_ZIP.unlink()

    print("\n=== DOWNLOAD E FILTRAGEM FINALIZADOS COM SUCESSO! ===")
    print("Os seguintes arquivos foram gerados em data/receita/:")
    print(f"  - {est_output.name}")
    print(f"  - {emp_output.name}")
    print(f"  - {sim_output.name}")
    print("\nVocê agora pode rodar a ingestão dos dados com o comando:")
    print("  python scripts/ingest_estabelecimentos.py \\")
    print(f"      --estabelecimentos data/receita/{est_output.name} \\")
    print(f"      --empresas data/receita/{emp_output.name} \\")
    print(f"      --simples data/receita/{sim_output.name}")


if __name__ == "__main__":
    main()
