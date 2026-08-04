from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import request


API_URL = os.getenv("API_URL", "http://localhost:8000")
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "mei-contabilidade-melo.html"


def main() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = {
        "nome": "Contabilidade Melo - Plano Basico MEI",
        "assunto": "MEI: Ganhe Certificado Digital + 10 Notas Fiscais por mes",
        "corpo_template": template,
        "filtro_tipo_regime": "MEI",
        "tamanho_lote": int(os.getenv("TAMANHO_LOTE", "100")),
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{API_URL.rstrip('/')}/campanhas",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        print(body)


if __name__ == "__main__":
    main()
