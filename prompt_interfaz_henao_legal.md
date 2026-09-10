# Prompt de construcción — Panel interno HENAO LEGAL (fase de validación)

## Contexto del proyecto

Estoy construyendo un panel interno para HENAO LEGAL (despacho especializado en industria musical). El panel será usado por mí (desarrollador/consultor) y por el abogado del despacho durante una fase de validación del producto, antes de exponerlo a los talentos/clientes finales.

El panel agrupa tres funcionalidades que hoy son procesos manuales/scripts separados:
1. Diagnóstico legal (generado con IA a partir de datos de un formulario de intake)
2. Generación de contratos y poderes (generados desde plantillas, con datos variables)
3. Envío por correo al abogado y al talento, con un paso de aprobación manual antes de enviar

## Objetivo de esta construcción

Quiero un backend en **FastAPI** con frontend servido por el mismo backend (plantillas Jinja2 + HTML/CSS simple, sin frontend separado en React todavía). Debe sentirse como una app real y usable en producción interna, no un prototipo desechable — pero sin sobre-ingeniería: nada de microservicios, colas de mensajes, ni infraestructura que no necesito para 2-3 usuarios.

## Requisitos funcionales

### 1. Autenticación básica
- Login con usuario/contraseña.
- Dos roles simples: `admin` (yo) y `abogado`. No necesito permisos granulares, solo que ambos puedan ver y operar el panel.
- Sesión con cookies (usar `starlette` sessions o similar, sin JWT complejo).

### 2. Vista principal: cola de casos
- Tabla con los casos provenientes del sheet de intake (talento, fecha de intake, estado actual).
- Estados posibles: `pendiente` → `diagnóstico generado` → `en revisión` → `aprobado` → `enviado`.
- Cada fila permite avanzar al siguiente estado según corresponda (ver flujo abajo).

### 3. Flujo por caso
- **Generar diagnóstico**: botón que dispara la llamada a la API de Claude con los datos del talento, usando un prompt estructurado que devuelve JSON por área (composición, masters, contratos previos, registro de obra), validado con Pydantic.
- **Generar documento**: botón que, a partir del mismo JSON, rellena una plantilla docx (via `docxtpl`) para el diagnóstico, y separadamente otra plantilla para el contrato/poder correspondiente.
- **Revisar**: pantalla que muestra el diagnóstico generado y un preview/descarga del documento antes de aprobar. Debe permitir marcar "aprobado" o devolver a un estado anterior si algo está mal.
- **Enviar**: solo visible cuando el estado es `aprobado`. Dispara el envío por Gmail API al abogado y al talento con el documento adjunto, y mueve el estado a `enviado`.

### 4. Integración con Google Sheets
- Lectura del sheet de intake vía Service Account (no OAuth de usuario).
- Sincronización simple: un botón "actualizar casos" que trae filas nuevas del sheet, o un refresh automático al cargar la vista principal.
- Al marcar un caso como enviado, actualizar también el estado en el sheet original.

### 5. Persistencia
- Necesito guardar el estado de cada caso, el JSON del diagnóstico generado, y las rutas de los documentos generados. Usar SQLite con SQLAlchemy — no quiero levantar una base de datos gestionada aparte para esta fase.

## Stack

- **Backend**: FastAPI + Uvicorn
- **Templates**: Jinja2 (server-rendered, con algo de HTMX si facilita las interacciones sin recargar toda la página — opcional, no imprescindible)
- **DB**: SQLite + SQLAlchemy
- **Auth**: sesiones con cookies firmadas (starlette `SessionMiddleware`), passwords hasheados con `passlib`/`bcrypt`
- **Google Sheets**: `gspread` + Service Account
- **Generación de documentos**: `docxtpl`
- **LLM**: API de Claude (Anthropic), llamada directa vía SDK oficial de Python
- **Email**: Gmail API (ya tengo integración previa en otro proyecto, reusar patrón si es posible)

## Lo que NO quiero en esta fase

- No Docker (a menos que sea trivial agregarlo después sin reescribir nada).
- No frontend separado en React/Vue.
- No sistema de roles/permisos complejo.
- No colas asíncronas (Celery, Redis) — las llamadas a la API de Claude y la generación de documentos pueden ser síncronas por ahora dado el volumen bajo de casos.

## Entregable esperado

Estructura de proyecto completa (carpetas, archivos), con:
- Modelo de datos (SQLAlchemy) para casos/estado.
- Rutas FastAPI para cada paso del flujo.
- Templates HTML básicos (sin necesidad de diseño elaborado, solo funcional y claro).
- Archivo `.env.example` con las variables necesarias (credenciales de Google, API key de Claude, credenciales de Gmail).
- Instrucciones de cómo correrlo localmente y cómo desplegarlo en un droplet simple (Gunicorn + Nginx o similar).

Empieza por proponerme la estructura de carpetas y el esquema de la base de datos antes de escribir código, para que pueda validarlo.
