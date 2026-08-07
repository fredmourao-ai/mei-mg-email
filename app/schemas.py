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
            "Filtra empresas por estado. Default 'MG'. Use outra UF ou null "
            "explicitamente quando quiser alterar esse escopo."
        ),
    )
    tamanho_lote: int = Field(default=100, ge=1, le=1000)
    limite_empresas: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description=(
            "Limite maximo de contatos enfileirados nesta campanha. Para Exchange Online, "
            "nao use mais de 10000 destinatarios em uma janela movel de 24 horas."
        ),
    )


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
