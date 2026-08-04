from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CampanhaCreate(BaseModel):
    nome: str
    assunto: str
    corpo_template: str = Field(
        ...,
        description=(
            "Suporta {{razao_social}}, {{nome_fantasia}}, {{cnpj}} "
            "e {{unsubscribe_url}}. O template DEVE incluir "
            "{{unsubscribe_url}} em algum lugar -- a API rejeita a criacao "
            "da campanha se nao incluir (exigencia de anti-spam/LGPD)."
        ),
    )
    filtro_tipo_regime: str | None = Field(
        default="MEI",
        description="Filtra empresas por regime: MEI, SIMPLES ou OUTROS. Se None, seleciona todas.",
    )
    filtro_uf: str | None = Field(
        default="MG",
        description=(
            "Filtra empresas por estado. Default 'MG' -- toda campanha nova "
            "e MG-only a menos que o campo seja explicitamente sobrescrito "
            "nesta chamada (com outra UF, ex: 'SP', ou com null pra "
            "remover a restricao e pegar todos os estados). Nunca omita "
            "esse campo esperando 'todos os estados' por padrao -- omitir "
            "= MG."
        ),
    )
    tamanho_lote: int = 100


class CampanhaOut(BaseModel):
    id: str
    nome: str
    status: str
    total_empresas: int
    total_enviados: int
    total_falhas: int
    criado_em: datetime
    iniciado_em: datetime | None
    concluido_em: datetime | None


class DescadastroIn(BaseModel):
    email: str
    cnpj: str | None = None
    campanha_id: str | None = None
    origem: str = "link_email"
