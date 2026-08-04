import logging

from fastapi import FastAPI

from app.routes import campanhas, descadastro, empresas

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MEI-MG Email API",
    description=(
        "API de controle para disparo de e-mail em lotes para MEIs de MG "
        "(dados abertos de CNPJ da Receita Federal). So cria/consulta "
        "campanhas -- o envio de verdade acontece no worker separado "
        "(worker/worker.py), que consome a fila de lotes."
    ),
    version="0.1.0",
)

app.include_router(campanhas.router)
app.include_router(descadastro.router)
app.include_router(empresas.router)


@app.get("/health")
def health():
    return {"status": "ok"}
