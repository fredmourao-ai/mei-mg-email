from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scripts.ingest_estabelecimentos import (
    ler_empresas,
    ingerir_estabelecimentos,
    remover_emails_compartilhados,
    gravar_no_banco,
    BASE_DIR,
)

logger = logging.getLogger("mei_mg_email.empresas")
router = APIRouter(prefix="/empresas", tags=["empresas"])


class AtualizarBaseResponse(BaseModel):
    status: str
    total_linhas: int | None = None
    elegiveis: int
    mensagem: str


@router.post("/atualizar-base", response_model=AtualizarBaseResponse)
def atualizar_base(use_sample: bool = False):
    try:
        if use_sample:
            estabelecimentos = BASE_DIR / "data" / "sample" / "ESTABELECIMENTOS_fake.csv"
            empresas_arq = BASE_DIR / "data" / "sample" / "EMPRESAS_fake.csv"
        else:
            receita_dir = BASE_DIR / "data" / "receita"
            receita_dir.mkdir(parents=True, exist_ok=True)

            # Busca arquivos no diretório data/receita
            est_files = list(receita_dir.glob("ESTABELECIMENTOS*"))
            emp_files = list(receita_dir.glob("EMPRESAS*"))

            if not est_files:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Nenhum arquivo ESTABELECIMENTOS* encontrado em data/receita/. "
                        "Coloque os arquivos reais da Receita ou chame com use_sample=true para testar."
                    ),
                )

            # Pega o primeiro de cada um encontrado para ingestão (ou unifica se necessário)
            estabelecimentos = est_files[0]
            empresas_arq = emp_files[0] if emp_files else None

        razao_por_basico = ler_empresas(empresas_arq)

        empresas = ingerir_estabelecimentos(
            estabelecimentos,
            razao_por_basico,
        )
        remover_emails_compartilhados(empresas)
        gravar_no_banco(empresas)

        return AtualizarBaseResponse(
            status="sucesso",
            elegiveis=len(empresas),
            mensagem=f"Ingestão concluída com sucesso. Gravado/atualizado no banco: {len(empresas)} empresas.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falha interna durante a atualizacao da base")
        raise HTTPException(
            status_code=500,
            detail="Erro interno durante a atualizacao da base",
        )
