import subprocess
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON_EXEC = BASE_DIR / ".venv" / "Scripts" / "python.exe"
DOWNLOAD_SCRIPT = BASE_DIR / "scripts" / "download_cnpj_mg.py"
INGEST_SCRIPT = BASE_DIR / "scripts" / "ingest_estabelecimentos.py"

def run_step(cmd: list[str]) -> bool:
    try:
        print(f"\n[retry-wrapper] Executando: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[retry-wrapper] Falha ao executar: {e}")
        return False

def main():
    print("=== MONITOR DE DOWNLOAD E INGESTÃO AUTOMÁTICO INICIADO ===")
    
    # 1. Tentar baixar e filtrar os dados
    backoff_seconds = 180  # 3 minutos de espera entre tentativas
    success = False
    
    while not success:
        print(f"\n[retry-wrapper] Tentando iniciar download...")
        # Executa o downloader
        download_success = run_step([str(PYTHON_EXEC), "-u", str(DOWNLOAD_SCRIPT)])
        
        # Verifica se os arquivos foram gerados no diretório data/receita/
        est_file = BASE_DIR / "data" / "receita" / "ESTABELECIMENTOS_mg.csv"
        emp_file = BASE_DIR / "data" / "receita" / "EMPRESAS_mg.csv"
        sim_file = BASE_DIR / "data" / "receita" / "SIMPLES_mg.csv"
        
        if download_success and est_file.exists() and emp_file.exists() and sim_file.exists():
            print("\n[retry-wrapper] Download e filtragem de MG concluídos com sucesso!")
            success = True
        else:
            print(f"\n[retry-wrapper] Servidor da Receita retornou erro ou arquivos ausentes.")
            print(f"[retry-wrapper] Próxima tentativa em {backoff_seconds} segundos...")
            time.sleep(backoff_seconds)
            
    # 2. Rodar a Ingestão no Postgres local
    print("\n[retry-wrapper] Iniciando ingestão dos dados no banco...")
    ingest_success = run_step([
        str(PYTHON_EXEC),
        str(INGEST_SCRIPT),
        "--estabelecimentos", str(est_file),
        "--empresas", str(emp_file),
        "--simples", str(sim_file)
    ])
    
    if ingest_success:
        print("\n[retry-wrapper] TODO O PROCESSO DE DOWNLOAD E INGESTÃO FOI CONCLUÍDO COM SUCESSO!")
    else:
        print("\n[retry-wrapper] Download feito com sucesso, mas a ingestão falhou. Verifique os logs do Postgres.")

if __name__ == "__main__":
    main()
