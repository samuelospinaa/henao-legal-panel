# Panel interno HENAO LEGAL

Panel de uso interno (2-3 usuarios) que reúne el diagnóstico legal con IA, la
generación de contratos/poderes y el envío por correo con aprobación manual.

FastAPI + Jinja2 servidos por el mismo proceso, SQLite, sin frontend aparte.

## Flujo

```
pendiente ──generar diagnóstico──▶ diagnóstico generado ──▶ en revisión ──▶ aprobado ──enviar──▶ enviado
                                          ▲                     │              │
                                          └─────devolver────────┴──────────────┘
```

- **Generar diagnóstico**: llama a Claude con los datos de intake y guarda el JSON
  validado contra `DiagnosticoLegal` (4 áreas: composición, masters, contratos
  previos, registro de obra).
- **Generar documento**: rellena `plantillas/{diagnostico,contrato,poder}.docx` con
  `docxtpl` a partir de ese mismo JSON.
- **Revisar**: el detalle del caso muestra diagnóstico + documentos descargables, y
  permite aprobar o devolver a un estado anterior con notas.
- **Enviar**: solo desde `aprobado`. Manda los .docx por Gmail API al abogado y al
  talento, pasa el caso a `enviado` y escribe el estado en el sheet de intake.

## Estructura

```
app/
  main.py            app FastAPI, sesión en cookie, montaje de rutas
  config.py          settings desde .env (pydantic-settings)
  db.py              engine, sesión y creación de tablas
  models.py          User, Caso, Documento, Envio + enums Estado/Rol/TipoDocumento
  schemas.py         DiagnosticoLegal / AreaDiagnostico (salida del modelo), FilaIntake
  security.py        hash de passwords y dependencias de login
  templating.py      Jinja2Templates con globals comunes
  routers/auth.py    login / logout
  routers/casos.py   cola, detalle, transiciones, descarga, envío
  services/sheets.py      lectura y escritura del sheet (Service Account)
  services/diagnostico.py llamada a Claude con structured outputs
  services/documentos.py  render de plantillas .docx
  services/mailer.py      envío por Gmail API
  templates/, static/
plantillas/          .docx con variables Jinja (generables con un script)
data/                app.db + documentos generados
scripts/             crear_usuario.py, crear_plantillas.py, autorizar_gmail.py
deploy/              unit de systemd y sitio de nginx
```

### Modelo de datos

| Tabla | Campos |
|---|---|
| `users` | `id`, `username` (único), `password_hash`, `rol` (`admin`/`abogado`), `creado_at` |
| `casos` | `id`, `sheet_row_id` (único, fila del sheet), `talento_nombre/email/documento`, `fecha_intake`, `estado`, `datos_intake` (JSON crudo), `diagnostico_json` (JSON validado), `diagnostico_generado_at`, `notas_revision`, `creado_at`, `actualizado_at` |
| `documentos` | `id`, `caso_id`, `tipo` (`diagnostico`/`contrato`/`poder`), `filename`, `path`, `creado_at` |
| `envios` | `id`, `caso_id`, `destinatarios`, `asunto`, `gmail_message_id`, `error`, `enviado_at` |

## Correr en local

```bash
python -m venv .venv
.venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # completar credenciales
python scripts/crear_usuario.py                       # admin del .env
python scripts/crear_usuario.py abogado s3creta abogado
python scripts/crear_plantillas.py                    # plantillas .docx de arranque

uvicorn app.main:app --reload
```

En <http://127.0.0.1:8000>. Con `DEBUG=true` la cookie de sesión no exige HTTPS;
en producción déjalo en `false`.

## Credenciales

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | firma de la cookie de sesión — cámbiala antes de desplegar |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | diagnóstico (por defecto `claude-opus-5`) |
| `GOOGLE_SERVICE_ACCOUNT_FILE`, `SHEET_ID`, `SHEET_WORKSHEET` | sheet de intake |
| `GMAIL_CREDENTIALS_FILE`, `GMAIL_TOKEN_FILE`, `GMAIL_SENDER`, `ABOGADO_EMAIL` | envío |

- **Sheets**: crea la Service Account, descarga el JSON y **comparte el sheet con su
  `client_email`** (permiso de editor, porque el panel escribe la columna
  `Estado panel`). Las columnas del intake se detectan por alias (nombre, correo,
  documento, fecha) sin importar mayúsculas ni acentos; ajusta `ALIAS_COLUMNAS` en
  `app/services/sheets.py` si tu formulario usa otros títulos.
- **Gmail**: `python scripts/autorizar_gmail.py` una vez en local (abre el navegador,
  scope `gmail.send`) y copia el `gmail_token.json` resultante al servidor.
- Guarda ambos JSON en `secrets/` (ya está en `.gitignore`).

## Plantillas .docx

`scripts/crear_plantillas.py` genera borradores con la sintaxis que espera el
render. El abogado los reemplaza por las minutas reales conservando las variables:

`{{ talento_nombre }}`, `{{ talento_documento }}`, `{{ fecha_larga }}`,
`{{ resumen_ejecutivo }}`, `{% for area in areas %}` (con `titulo`,
`situacion_actual`, `riesgos`, `recomendaciones`, `nivel_riesgo`),
`{{ prioridades }}`, `{{ documentos_sugeridos }}`, `{{ intake }}`.

Un botón queda deshabilitado si falta su plantilla.

Las plantillas de contratos (`prestacion_servicios`, `colaboracion_derechos`,
`produccion_fonografica`, `autorizacion_imagen`, `splitsheet`,
`autorizacion_espacios`) estan en `plantillas/` y se rellenan con los campos de
`app/documento_schema.py`. Se generaron a partir de las minutas reales del
despacho con un script interno que **no esta en el repositorio** (sus anclas son
textos literales de esas minutas, que contienen datos de terceros; la carpeta
`examples/` tampoco se versiona).

## Despliegue en un droplet

```bash
# en el servidor
sudo apt install -y python3-venv nginx
sudo adduser --system --group henao
sudo mkdir -p /srv/henao && sudo chown henao:henao /srv/henao
# copiar el proyecto a /srv/henao (rsync/git), luego:
sudo -u henao python3 -m venv /srv/henao/.venv
sudo -u henao /srv/henao/.venv/bin/pip install -r /srv/henao/requirements.txt
sudo -u henao /srv/henao/.venv/bin/python /srv/henao/scripts/crear_usuario.py

sudo cp deploy/henao-panel.service /etc/systemd/system/
sudo systemctl enable --now henao-panel

sudo cp deploy/nginx-henao.conf /etc/nginx/sites-available/henao
sudo ln -s /etc/nginx/sites-available/henao /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d panel.tu-dominio.com     # HTTPS obligatorio: la cookie es Secure
```

Gunicorn corre con workers `UvicornWorker`. Con SQLite mantén **1 worker** (`-w 1`)
para evitar escrituras concurrentes; con 2-3 usuarios sobra.

Backup: basta copiar `data/` (base + documentos generados).

## Notas de la fase de validación

- Las llamadas a Claude y la generación de documentos son síncronas: una petición
  puede tardar decenas de segundos. `nginx` está configurado con timeouts largos.
- Si el envío falla, el caso **no** cambia de estado y el error queda en `envios`.
- Si el correo sale pero el sheet no se puede actualizar, se avisa en pantalla; el
  caso ya quedó en `enviado` localmente.
