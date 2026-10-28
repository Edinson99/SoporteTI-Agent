"""Autoriza Gmail API y guarda las credenciales OAuth fuera del repositorio."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]


def _configured_path(variable: str, default: str) -> Path:
    path = Path(os.getenv(variable, default))
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    client_secrets = _configured_path(
        "GMAIL_OAUTH_CLIENT_SECRETS",
        ".secrets/gmail-oauth-client.json",
    )
    token_file = _configured_path(
        "GMAIL_OAUTH_TOKEN_FILE",
        ".secrets/gmail-token.json",
    )
    if not client_secrets.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo OAuth de Google: {client_secrets}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets),
        scopes=SCOPES,
    )
    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Autorización completada. Token guardado en: {token_file}")


if __name__ == "__main__":
    main()
