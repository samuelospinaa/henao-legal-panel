"""Genera el token OAuth de Gmail (se corre una sola vez, en local).

Abre el navegador, pide consentimiento con el scope gmail.send y guarda el token
en GMAIL_TOKEN_FILE. En el droplet basta con copiar ese archivo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.mailer import SCOPES  # noqa: E402


def main() -> None:
    if not settings.gmail_credentials_file or not settings.gmail_token_file:
        raise SystemExit("Configura GMAIL_CREDENTIALS_FILE y GMAIL_TOKEN_FILE en el .env")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.gmail_credentials_file), SCOPES
    )
    creds = flow.run_local_server(port=0)
    destino = Path(settings.gmail_token_file)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(creds.to_json(), encoding="utf-8")
    print(f"Token guardado en {destino}")


if __name__ == "__main__":
    main()
