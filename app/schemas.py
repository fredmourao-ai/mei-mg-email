from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CampanhaCreate(BaseModel):
    nome: str
    assunto: str
    corpo_template: str = Field(
        ...,
        description=(
            "Suporta {{razao_social}}, {{nome_fantasia}}, {{municipio}}, "
            "{{cnpj}} e {{unsubscribe_url}}. O template DEVE incluir "
            "{{unsubscribe_url}} em algum lugar -- a API rejeita a criacao "
            "da campanha se nao incluir (exigencia de anti-spam/LGPD)."
        ),
    )
    filtro_municipio: str | None = None
    filtro_cnae: str | None = None
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
