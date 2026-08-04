import sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.routes.campanhas import criar_campanha
from app.schemas import CampanhaCreate
from app.email_provider import get_email_provider
from worker.worker import pegar_proximo_lote, processar_lote

def disparar_295_mei_mg():
    print("=== INICIANDO CRIAÇÃO E DISPARO DE 295 E-MAILS (MEI MG MAIS RECENTES) ===", flush=True)
    
    payload = CampanhaCreate(
        nome="Campanha MEI MG 295 - Contabilidade Melo",
        assunto="Aviso Importante para MEI - Regularização Fiscal",
        corpo_template=(
            "Olá, {{razao_social}}.\n\n"
            "Identificamos que a sua empresa {{cnpj}} registrada em MG possui prazos e "
            "obrigações de regularização fiscal ativas.\n\n"
            "A equipe da Contabilidade Melo está à disposição para ajudar a manter seu MEI em dia:\n"
            "https://contabilidademelo.com.br\n\n"
            "Caso não deseje mais receber nossas mensagens, acesse: {{unsubscribe_url}}"
        ),
        filtro_tipo_regime="MEI",
        filtro_uf="MG",
        tamanho_lote=50
    )
    
    campanha = criar_campanha(payload)
    print(f"Campanha criada! ID: {campanha['id']} | Total Empresas Elegíveis: {campanha['total_empresas']}", flush=True)
    
    provider = get_email_provider(settings.email_provider)
    print(f"Provider Ativo: {provider.__class__.__name__}", flush=True)
    
    while True:
        with psycopg.connect(settings.database_url) as conn:
            lote = pegar_proximo_lote(conn)
            if not lote:
                print("Todos os lotes da fila foram processados.", flush=True)
                break
            
            print(f"\n[Worker] Processando Lote #{lote['numero']} (ID: {lote['id']})...", flush=True)
            processar_lote(conn, lote, provider)
            
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select count(*) from mei_email.envios
                     where status = 'enviado'
                       and enviado_em >= (now() at time zone 'America/Sao_Paulo')::date
                    """
                )
                enviados_hoje = cur.fetchone()[0]
                print(f"  -> Total de e-mails enviados hoje: {enviados_hoje}/{settings.max_envios_por_dia}", flush=True)
                if enviados_hoje >= settings.max_envios_por_dia:
                    print(f"\n=== LIMITE DIÁRIO ALCANÇADO: {enviados_hoje}/{settings.max_envios_por_dia} E-MAILS ENVIADOS COM SUCESSO! ===", flush=True)
                    break

if __name__ == "__main__":
    disparar_295_mei_mg()
