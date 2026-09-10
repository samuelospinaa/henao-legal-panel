"""Crea o actualiza un usuario del panel.

    python scripts/crear_usuario.py                 # usa ADMIN_USERNAME/ADMIN_PASSWORD del .env
    python scripts/crear_usuario.py abogado s3creta abogado
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Rol, User  # noqa: E402
from app.security import hash_password  # noqa: E402


def main() -> None:
    args = sys.argv[1:]
    username = args[0] if args else settings.admin_username
    password = args[1] if len(args) > 1 else settings.admin_password
    rol = Rol(args[2]) if len(args) > 2 else Rol.admin

    init_db()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.password_hash = hash_password(password)
            user.rol = rol
            accion = "actualizado"
        else:
            db.add(
                User(username=username, password_hash=hash_password(password), rol=rol)
            )
            accion = "creado"
        db.commit()
    print(f"Usuario '{username}' {accion} con rol {rol.value}.")


if __name__ == "__main__":
    main()
