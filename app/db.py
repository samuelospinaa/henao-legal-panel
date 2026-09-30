from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _agregar_columnas_faltantes() -> None:
    """create_all() solo crea tablas nuevas: si la tabla ya existia (deploy
    previo a agregar una columna) hay que alterarla a mano. No usamos Alembic
    por el tamano del proyecto, asi que esto hace de migracion minima."""
    tipo_binario = "BYTEA" if engine.dialect.name == "postgresql" else "BLOB"
    inspector = inspect(engine)
    columnas_por_tabla = {
        "documentos": [("contenido", tipo_binario)],
        "documentos_adjuntos": [("contenido", tipo_binario)],
    }
    with engine.begin() as conn:
        for tabla, columnas in columnas_por_tabla.items():
            if tabla not in inspector.get_table_names():
                continue
            existentes = {c["name"] for c in inspector.get_columns(tabla)}
            for nombre, tipo in columnas:
                if nombre not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}"))


def _migrar_columna_path() -> None:
    """Versiones anteriores guardaban cada .docx en disco y su ruta en
    `path` (NOT NULL). Ahora el archivo vive en `contenido`, asi que en una
    base vieja todo INSERT falla por `path` sin valor. Se copia a `contenido`
    cada archivo que aun exista en disco y se elimina la columna."""
    inspector = inspect(engine)
    for tabla in ("documentos", "documentos_adjuntos"):
        if tabla not in inspector.get_table_names():
            continue
        if "path" not in {c["name"] for c in inspector.get_columns(tabla)}:
            continue
        with engine.begin() as conn:
            pendientes = conn.execute(
                text(f"SELECT id, path FROM {tabla} WHERE contenido IS NULL AND path IS NOT NULL")
            ).all()
            for fila_id, ruta in pendientes:
                archivo = Path(ruta)
                if archivo.is_file():
                    conn.execute(
                        text(f"UPDATE {tabla} SET contenido = :c WHERE id = :i"),
                        {"c": archivo.read_bytes(), "i": fila_id},
                    )
            conn.execute(text(f"ALTER TABLE {tabla} DROP COLUMN path"))


def init_db() -> None:
    from app import models  # noqa: F401  (registra los modelos en el metadata)

    Base.metadata.create_all(bind=engine)
    _agregar_columnas_faltantes()
    _migrar_columna_path()
