from __future__ import annotations

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scripts.ingest_estabelecimentos import (
    ler_empresas,
    ler_simples,
    ingerir_estabelecimentos,
    marcar_provaveis_terceiros,
    gravar_no_banco,
    BASE_DIR,
)

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
            simples_arq = BASE_DIR / "data" / "sample" / "SIMPLES_fake.csv"
        else:
            receita_dir = BASE_DIR / "data" / "receita"
            receita_dir.mkdir(parents=True, exist_ok=True)

            # Busca arquivos no diretório data/receita
            est_files = list(receita_dir.glob("ESTABELECIMENTOS*"))
            emp_files = list(receita_dir.glob("EMPRESAS*"))
            sim_files = list(receita_dir.glob("SIMPLES*"))

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
            simples_arq = sim_files[0] if sim_files else None

        razao_por_basico = ler_empresas(empresas_arq)
        mei_por_basico = ler_simples(simples_arq)

        empresas = ingerir_estabelecimentos(
            estabelecimentos,
            razao_por_basico,
            mei_por_basico,
            filtrar_mei=bool(simples_arq),
        )
        marcar_provaveis_terceiros(empresas)
        gravar_no_banco(empresas)

        return AtualizarBaseResponse(
            status="sucesso",
            elegiveis=len(empresas),
            mensagem=f"Ingestão concluída com sucesso. Gravado/atualizado no banco: {len(empresas)} empresas.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno durante a atualização da base: {str(e)}",
        )
