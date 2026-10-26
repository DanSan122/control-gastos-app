# ControlGastos

Aplicación multiusuario con espacios personales y familiares: sesiones, finanzas, dashboard, presupuestos PEN, reportes XLSX/CSV/PDF, auditoría y movimientos recurrentes personales. React + TypeScript + Vite + Tailwind + Recharts; Django 5.2 LTS + DRF; PostgreSQL 17. Otras monedas y notificaciones quedan para fases posteriores.

## Fase 7: espacios familiares

Contrato y matriz de permisos en [docs/familias.md](docs/familias.md); resultados de pruebas en [docs/verificacion.md](docs/verificacion.md). Las cuentas y movimientos anteriores siguen siendo personales. No hay aportes automáticos entre espacios ni recurrencias familiares.

Para actualizar una instalación de Fase 6, conservar sus `.env` y volumen:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml stop backend recurring-worker
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python scripts/verify_family_migration.py before
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python manage.py migrate --plan
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python scripts/verify_family_migration.py after
docker compose -f compose.yaml -f compose.dev.yaml up -d backend frontend
docker compose -f compose.yaml -f compose.dev.yaml --profile recurring up -d recurring-worker
```

Abrir http://localhost:5173/familias. A crea una familia e invita por correo a B, que ya debe estar registrado. B acepta en `/familias/invitaciones`; ambos pueden consultar y registrar movimientos familiares. C, ajeno, no puede consultar ese espacio. A puede retirar a B; los datos históricos permanecen y B pierde acceso. Usar exclusivamente cuentas sintéticas en QA. El selector visible permite volver al espacio personal sin cerrar sesión. Registro de usuarios existente conservado; propuesta de aprovisionamiento restringido en docs/familias.md.

Pruebas completas (bases temporales):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets apps.reports apps.audit apps.recurring apps.families --settings=config.settings_test_postgres
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets apps.reports apps.audit apps.recurring apps.families --settings=config.settings_test
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py check
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py makemigrations --check --dry-run
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run typecheck
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run build
```

Navegador: añadir `python families_flow.py` a la ejecución Docker/Playwright documentada más abajo y conservar los otros cinco scripts, incluido recurring_flow.py con el worker activo. Las capturas, exportaciones y huellas de migración quedan ignoradas; no se guardan contraseñas de QA.

## Requisitos
- Python 3.11+ con pip y venv (recomendado Python oficial para Windows).
- Node.js 22.12+ con npm.
- Docker Engine/Docker Desktop activo, Docker Compose y Git.

## Estructura
```text
frontend/           Aplicación React, configuración Vite y cliente HTTP
backend/config/    Settings, URLs y entradas ASGI/WSGI
backend/apps/core/ Health y pruebas
backend/apps/users/ Usuario UUID, autenticación, Admin, migraciones y tests
backend/apps/accounts/ Cuentas de activos y crédito
backend/apps/categories/ Jerarquía privada y catálogo inicial idempotente
backend/apps/transactions/ Movimientos, transferencias, saldos, periodos y reportes
backend/apps/analytics/ Agregaciones, evolución, distribución y comparación
backend/apps/budgets/ Presupuestos mensuales, progreso y alertas derivadas
backend/apps/reports/ Reportes filtrados, límites, XLSX/CSV/PDF
backend/apps/audit/ Eventos append-only y protección PostgreSQL
backend/apps/recurring/ Reglas, calendario, ocurrencias y scheduler idempotente
backend/scripts/   Comprobación de conexión real y de solo lectura
tests/browser/     Flujo E2E Chromium y capturas locales ignoradas
docs/              Arquitectura, requisitos y modelo propuesto
compose.yaml       PostgreSQL local con volumen persistente
.env.example       Configuración de backend y base de datos
AGENTS.md          Convenciones de desarrollo y seguridad
```

## Ejecución recomendada en este equipo: Docker

Conservar los `.env` existentes. Para una instalación nueva, copiar los ejemplos y completar secretos como se indica abajo. El stack utiliza el volumen PostgreSQL de la Fase 1; no lo borra. La extensión de desarrollo no ejecuta migraciones automáticamente.

Desde la raíz:
```powershell
docker compose -f compose.yaml -f compose.dev.yaml build backend
docker compose up -d --wait postgres
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python scripts/check_database.py
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python manage.py migrate --plan
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python manage.py seed_catalog
docker compose -f compose.yaml -f compose.dev.yaml up -d backend frontend
```
Abrir **http://localhost:5173**. Backend: http://localhost:8000. Crear tu propia cuenta desde `/registro`; el catálogo inicial se crea automáticamente. Rutas privadas: `/dashboard`, `/cuentas`, `/clasificaciones`, `/gastos/nuevo`, `/ingresos/nuevo`, `/transferir`, `/movimientos`, `/movimientos/{uuid}`, `/resumen`, `/perfil` y `/seguridad`. Otras rutas muestran 404.

El frontend instala dependencias con `npm ci` en un volumen propio y usa Node 22. El backend instala las versiones de `requirements.lock.txt`, generado desde el entorno comprobado. Vite usa sondeo de archivos en Docker para detectar cambios desde Windows. Tras cambiar dependencias, reconstruir backend o reiniciar frontend según corresponda; tras cambiar variables, recrear el servicio.

Parar servicios conservando datos:
```powershell
docker compose -f compose.yaml -f compose.dev.yaml down
```
No usar `down -v`. Son servidores de desarrollo; no constituyen un despliegue de producción.

## Instalación (PowerShell, desde la raíz)
```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
```
En Windows usar Python oficial; el Python MSYS de este equipo no admite psycopg-binary. En Linux/macOS: `python3 -m venv .venv` y `.venv/bin/python -m pip install -r backend/requirements.lock.txt`. Usar la alternativa Docker si el intérprete no es compatible.

Completar `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` en `.env` con valores aleatorios diferentes. Generar cada uno localmente con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. No reutilizar ni publicar los resultados. Las variables del proceso tienen prioridad sobre `.env`. `VITE_*` es configuración pública.

```powershell
docker compose config --quiet
docker compose up -d --wait postgres
docker compose ps
.\.venv\Scripts\python.exe backend/manage.py check
cd frontend
npm ci
npm run build
cd ..
```
`package-lock.json` fue generado mediante npm y permite instalaciones reproducibles con `npm ci`. `requirements.txt` declara rangos de dependencias; `requirements.lock.txt` fija las versiones comprobadas en Linux/Python 3.12. Windows puede resolver además dependencias específicas de plataforma como tzdata. Revisar actualizaciones antes de producción.

## Ejecutar
Terminal 1, raíz:
```powershell
.\.venv\Scripts\python.exe backend/manage.py runserver localhost:8000
```
Terminal 2:
```powershell
cd frontend
npm run dev
```
Abrir `http://localhost:5173`. La aplicación consulta auth/me/ y muestra login o las rutas privadas según la sesión. En desarrollo se autorizan los orígenes localhost y 127.0.0.1 del puerto 5173. Usar el mismo hostname para ambos servicios; si se usa 127.0.0.1, actualizar `frontend/.env` y reiniciar Vite. Puertos fijos para no desajustar CORS/CSRF. No iniciar servidores nativos en los mismos puertos que los contenedores activos.

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/
```
Respuesta esperada: `status=ok`, `service=controlgastos-api`, `version=v1`. Health comprueba vida de la API, no PostgreSQL.

`AUTH_USER_MODEL=users.User` ya está configurado y la migración inicial fue revisada y aplicada en este equipo. Para una base nueva, ejecutar `python backend/manage.py migrate` antes de iniciar las sesiones. Si una base externa ya usa auth.User, no intentar reemplazarlo ni borrar tablas: requiere un plan específico de migración de datos.

## Endpoints de Fase 2

Todas las rutas REST empiezan por `/api/v1/`. Las respuestas de usuario incluyen solo `id`, `email`, `first_name`, `last_name`, `date_joined`, `is_active`, `timezone` y `currency`.

| Método y ruta | Acceso / payload | Respuesta |
| --- | --- | --- |
| GET health/ | Público | 200: status, service, version |
| GET auth/csrf/ | Público | 200: csrfToken y cookie CSRF HttpOnly |
| POST auth/register/ | Público con CSRF: email, password, first_name, last_name | 201: usuario; no inicia sesión |
| POST auth/login/ | Público con CSRF: email, password | 200: user y csrfToken rotado |
| POST auth/logout/ | Sesión + CSRF | 204; invalida sesión |
| GET auth/me/ | Sesión | 200: usuario actual |
| PATCH users/me/ | Sesión + CSRF: first_name, last_name, timezone, currency | 200: usuario actualizado |
| POST auth/change-password/ | Sesión + CSRF: current_password, new_password | 200: detail y csrfToken |

Antes de cada escritura, obtener `/auth/csrf/` con cookies (`credentials: include`) y enviar el valor JSON en `X-CSRFToken`. La cookie no se lee desde JavaScript. Login rota CSRF; el cliente obtiene un token nuevo para cada escritura. No hay tokens en localStorage. Registro y login anónimos también rechazan peticiones sin CSRF válido.

Errores: 400 para validación, 403 para CSRF/credenciales/sesión ausente (convención de SessionAuthentication de DRF), 429 con `Retry-After` para límite de intentos, 405 para métodos no admitidos. Login incorrecto e inexistente devuelve el mismo mensaje. Campos no permitidos, incluidos id, email, password y privilegios en PATCH, se rechazan. El correo del perfil es de solo lectura; no se implementa cambio de correo ni verificación por email en esta fase.

## Variables de entorno

Fase 3 reutiliza las variables existentes y no introduce secretos ni servicios nuevos. CORS permite Idempotency-Key. Para actualizar una instalación existente: aplicar migraciones financieras y ejecutar seed_catalog; no recrear PostgreSQL ni aplicar reset a usuarios. Backend de desarrollo usa el código montado; reconstruir la imagen para incorporar los módulos a la imagen Docker.

## Gestión financiera (Fase 3)

Documentación completa de modelos, reglas, ejemplos JSON, filtros y reportes en [docs/finanzas.md](docs/finanzas.md).

| Recurso bajo /api/v1/ | Operaciones |
| --- | --- |
| accounts/ y accounts/{id}/ | GET/POST colección; GET/PATCH/DELETE detalle |
| accounts/{id}/balance/ | GET saldo y deuda |
| areas/, categories/, subcategories/ y sus detalles | GET/POST colección; GET/PATCH/DELETE detalle |
| transactions/ y transactions/{id}/ | GET/POST ingresos/gastos; GET/PATCH/DELETE detalle |
| transfers/ | POST con Idempotency-Key UUID obligatorio |
| reports/summary/ | GET ingresos, gastos, flujo neto, agrupaciones, evolución y saldos |

Todos requieren sesión y CSRF en escrituras. Importe como cadena, por ejemplo `"25.50"`, nunca número JSON. Moneda PEN. Fecha efectiva ISO 8601 con offset/Z. DELETE conserva historial mediante desactivación/anulación. VOID no se edita ni reactiva. Desde Fase 5 se auditan cambios; no se reconstruyen versiones históricas anteriores.

Transferencia = un movimiento con dos efectos de saldo, excluido de ingresos/gastos. Crédito = deuda negativa; pago de tarjeta = transferencia desde cuenta de activos. Yape/Plin pueden ser métodos sobre una cuenta bancaria, sin crear saldos duplicados. Saldo de cuenta es distinto del flujo neto del periodo y del patrimonio total; sus definiciones están en el documento financiero.

Listas paginadas: page, page_size (25 por defecto, máximo 100), filtros y ordenamiento. Historial/resumen admiten period=day/week/month/custom y start/end para rango personalizado. Filtros en la zona del usuario; semanas empiezan lunes. No se mezcla PEN con otras monedas.

## Fase 4: analítica y presupuestos

Dashboard `/dashboard`, análisis `/analisis`, comparación `/comparacion` y presupuestos `/presupuestos`, con sesión, CSRF y diseño responsive. Se conserva `/resumen` de Fase 3. Decisiones y contrato completo en [docs/analitica-presupuestos.md](docs/analitica-presupuestos.md).

Nuevos GET privados: `/api/v1/analytics/dashboard/`, `evolution/`, `distribution/`, `comparison/`. CRUD privado `/api/v1/budgets/` y `/api/v1/budgets/{uuid}/`; progreso GET `/api/v1/budgets/{uuid}/progress/`. DELETE desactiva. Importe límite como cadena decimal; presupuestos mensuales de área o categoría, solo PEN. Las alertas se muestran desde 80 % y 100 %, sin notificaciones externas.

Filtros temporales: day, yesterday, week, previous_week, month, previous_month, year, custom con start/end. Analítica avanzada limita el periodo actual al instante de consulta y compara con una duración local equivalente inmediatamente anterior. No equivale siempre al mes calendario anterior. Transferencias y pagos de tarjeta no son gastos duplicados.

Para actualizar el sistema existente sin borrar el volumen:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build backend
docker compose -f compose.yaml -f compose.dev.yaml up -d
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py migrate --plan
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py migrate --noinput
```

Abrir http://localhost:5173. No se agregan variables de entorno ni dependencias: Recharts ya estaba declarado. La migración nueva solo crea Budget; conserva usuarios, cuentas, movimientos y volumen.

Comprobaciones completas de Fase 4:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py check
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py makemigrations --check --dry-run
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets --settings=config.settings_test
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets --settings=config.settings_test_postgres
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run typecheck
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run build
docker run --rm --ipc=host --env E2E_DOCKER=true --mount type=bind,source=D:\control-gastos-app\tests\browser,target=/tests --workdir /tests mcr.microsoft.com/playwright/python:v1.56.0-noble sh -c "pip install -r requirements.txt && python analytics_flow.py && python finance_flow.py && python auth_flow.py"
```

La suite PostgreSQL usa base temporal separada. Chromium conserva usuarios sintéticos; no muestra contraseñas. Capturas en tests/browser/artifacts/, ignoradas. Resultados reales en docs/verificacion.md.

## Fase 5: reportes, exportaciones y auditoría

Vistas privadas `/reportes` y `/auditoria`; historial de cambios en el detalle de movimiento. Filtros combinables y vista previa paginada, con exportaciones Excel, CSV y PDF. Contratos y decisiones en [docs/reportes-auditoria.md](docs/reportes-auditoria.md).

API privada GET: `reports/`, `reports/preview/`, `reports/export/xlsx/`, `reports/export/csv/`, `reports/export/pdf/`, `audit/events/`, `audit/events/{uuid}/`, bajo `/api/v1/`. El resumen de Fase 3 conserva su ruta. Las escrituras financieras registran eventos dentro de su misma transacción; las transferencias reintentadas no duplican auditoría. Los eventos no se editan ni borran mediante API.

Excel contiene cinco hojas, importes como texto decimal exacto con formato PEN y sin fórmulas; no admite sumas nativas de esa columna sin conversión explícita. CSV tiene BOM UTF-8 y defensa contra fórmulas; PDF es multipágina con encabezados repetidos. Indicadores excluyen VOID y transferencias, aunque el detalle pueda mostrar esos registros. Auditoría empieza al activar Fase 5 y omite contenidos de descripción, referencia e institución.

Actualización de instalación existente, conservando `.env` y volumen:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build backend
docker compose -f compose.yaml -f compose.dev.yaml up -d backend frontend
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py migrate --plan
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py migrate --noinput
```

Se agregan openpyxl/ReportLab y dependencias transitivas en el lock generado desde contenedor limpio. Migraciones audit/0001_initial y 0002_append_only solo crean eventos/índices y trigger PostgreSQL; no cambian el ledger. Límites predeterminados: 366 días, 5000 movimientos XLSX/CSV, 500 PDF; 30 vistas y 10 descargas por usuario/60 segundos. Ajustes opcionales en `.env.example`; no son secretos.

Verificación completa de Fase 5:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py check
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py makemigrations --check --dry-run
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets apps.reports apps.audit --settings=config.settings_test_postgres
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets apps.reports apps.audit --settings=config.settings_test
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run typecheck
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run build
docker run --rm --ipc=host --env E2E_DOCKER=true --mount type=bind,source="${PWD}/tests/browser",target=/tests --workdir /tests mcr.microsoft.com/playwright/python:v1.56.0-noble sh -c 'pip install -r requirements.txt && python reports_flow.py && python analytics_flow.py && python finance_flow.py && python auth_flow.py'
```

QA de documentos sintéticos y límites: docs/reportes-auditoria.md. Resultados reales: docs/verificacion.md. Exportaciones síncronas, sin plantillas guardadas, firmas ni bitácora resistente a administradores de base. El commit `918736c` conserva Fases 1–4; no se crea otro commit sin autorización.

## Fase 6: movimientos recurrentes y programación

Abrir `/recurrentes`: reglas de ingresos/gastos/transferencias, próximos vencimientos, confirmación/omisión, edición, pausa/reanudación/cancelación e historial con enlaces al movimiento real. El dashboard muestra próximos aparte de saldos y presupuestos. Crear regla no registra dinero. Documentación completa: [docs/recurrencias.md](docs/recurrencias.md).

API privada bajo `/api/v1/`: `recurring/rules/`, `recurring/rules/{uuid}/`, acciones POST `pause/` y `resume/`; GET `recurring/upcoming/`, `recurring/executions/`, `recurring/executions/{uuid}/`; acciones POST `confirm/` y `skip/`. DELETE cancela lógicamente. Sesiones/CSRF, filtros/paginación y propiedad estricta. Dinero como cadenas; PEN. Primer intento/omisión bloquea frecuencia e intervalo; inicio/tipo no cambian tras crear. Zona horaria fijada al crear la regla.

Calendarios diarios/semanales/mensuales/anuales, intervalos y fin inclusivo. Día 31 se ajusta a febrero y vuelve al 31 en marzo; no deriva. Movimiento efectivo al inicio válido del día local, almacenado UTC. Sin selector de hora ni movimientos futuros; no se envían pagos externos. Clave determinista por regla/fecha, owner_lock y restricciones PostgreSQL evitan duplicados. Auditoría financiera/ocurrencia/cursor se confirma o revierte de forma conjunta.

Actualizar desde Fase 5 conservando datos:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build backend
docker compose -f compose.yaml -f compose.dev.yaml up -d backend frontend
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py migrate --plan
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py migrate --noinput
docker compose -f compose.yaml -f compose.dev.yaml --profile recurring up -d --build recurring-worker
docker compose -f compose.yaml -f compose.dev.yaml logs --tail 20 recurring-worker
```

Worker de desarrollo real cada 30 segundos, optativo en perfil recurring; no cambia producción ni necesita navegador. Iniciarlo después de migrar. Pararlo sin borrar datos: `docker compose -f compose.yaml -f compose.dev.yaml stop recurring-worker`. Comando puntual: `docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py process_recurring --limit 100 --per-rule 100`. Ejecutar solo ese comando manual no activa una automatización. No se añaden dependencias ni variables privadas nuevas.

Verificación completa, incluidas las 97 pruebas previas:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py check
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py makemigrations --check --dry-run
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets apps.reports apps.audit apps.recurring --settings=config.settings_test_postgres
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions apps.analytics apps.budgets apps.reports apps.audit apps.recurring --settings=config.settings_test
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run typecheck
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run build
docker run --rm --ipc=host --env E2E_DOCKER=true --mount type=bind,source="${PWD}/tests/browser",target=/tests --workdir /tests mcr.microsoft.com/playwright/python:v1.56.0-noble sh -c 'pip install -r requirements.txt && python recurring_flow.py && python auth_flow.py && python finance_flow.py && python analytics_flow.py && python reports_flow.py'
```

E2E requiere el worker activo: verifica automatización mientras no hay página abierta, conserva cuentas sintéticas y capturas ignoradas. Resultados reales en docs/verificacion.md. Esta fase se trabaja exclusivamente en feature/fase-6-recurrencias; no hace commits, push ni merge sin autorización.

## Variables disponibles (configuración)

| Variable | Uso / valor predeterminado |
| --- | --- |
| POSTGRES_DB / USER / PASSWORD / HOST / PORT | Base, usuario y conexión; contraseña obligatoria |
| DJANGO_SECRET_KEY | Obligatoria, privada y aleatoria |
| DJANGO_DEBUG | false por defecto; true exclusivamente local |
| DJANGO_ALLOWED_HOSTS | Hosts explícitos |
| DJANGO_CORS_ALLOWED_ORIGINS | Orígenes de lectura con credenciales |
| DJANGO_CSRF_TRUSTED_ORIGINS | Orígenes de escrituras permitidas |
| AUTH_RATE_WINDOW_SECONDS | 900 segundos |
| AUTH_LOGIN_EMAIL_LIMIT | 10 peticiones por correo y ventana |
| AUTH_LOGIN_IP_LIMIT | 30 peticiones por IP y ventana |
| AUTH_REGISTER_IP_LIMIT | 10 peticiones de registro por IP y ventana |
| AUTH_PASSWORD_USER_LIMIT | 5 cambios de contraseña por usuario y ventana |
| VITE_API_BASE_URL | Pública, en frontend/.env: http://localhost:8000/api/v1 |
| VITE_USE_POLLING | true en el servicio frontend Docker; vigila archivos montados |

Los límites cuentan peticiones válidas en CSRF, incluidas las exitosas y las de validación fallida. Son ventanas fijas, atómicas y compartidas en PostgreSQL; 429 incluye el tiempo de espera. Admin comparte límites de login. Se usa REMOTE_ADDR, no X-Forwarded-For; varios usuarios detrás del mismo proxy/NAT comparten límite IP. Antes de producción configurar la obtención de IP con un proxy de confianza y defensas de infraestructura. Los contadores guardan HMAC, no correos/IP en claro. Para retirar exclusivamente contadores expirados: `python backend/manage.py cleanup_auth_limits` (programable periódicamente).

Admin: http://localhost:8000/admin/. Crear un administrador solo si lo necesitas, con `python backend/manage.py createsuperuser`, o `docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser`. Es compatible con correo, nombre y apellidos; no hay administrador ni contraseña predeterminados.

## Comprobaciones
```powershell
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py test apps.core apps.users apps.transactions --settings=config.settings_test
.\.venv\Scripts\python.exe backend/manage.py test apps.core apps.users apps.transactions --settings=config.settings_test_postgres
cd frontend
npm run typecheck
npm run build
```
Tests aislados: SQLite en memoria, sin secretos; la prueba de concurrencia se omite. Integración: `.env` y PostgreSQL, base temporal `test_<POSTGRES_DB>` gestionada por Django; el usuario necesita permiso CREATEDB. Usar exclusivamente una base de desarrollo y no apuntar estos tests a producción. La base de desarrollo no se limpia ni sustituye.

Con los contenedores iniciados:
```powershell
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions --settings=config.settings_test
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py test apps.core apps.users apps.transactions --settings=config.settings_test_postgres
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py makemigrations --check --dry-run
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend npm run build
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python scripts/check_database.py
```

E2E Chromium, desde la raíz en Windows/Docker Desktop (servidores ya iniciados):
```powershell
docker run --rm --ipc=host --env E2E_DOCKER=true --mount type=bind,source="${PWD}/tests/browser",target=/tests --workdir /tests mcr.microsoft.com/playwright/python:v1.56.0-noble sh -c 'pip install -r requirements.txt && python auth_flow.py && python finance_flow.py'
```
Los scripts crean y conservan usuarios sintéticos cg-e2e/cg-finance y sus registros; no eliminan datos existentes. Capturas en tests/browser/artifacts/ ignoradas por Git. En ejecución nativa: instalar tests/browser/requirements.txt y Chromium, ejecutar auth_flow.py y finance_flow.py (sin E2E_DOCKER). Docker conserva los orígenes localhost mediante DNS de Chromium; la simulación de respuesta perdida usa host.docker.internal con Host/Origin locales y no imprime cabeceras.

Para comprobar PostgreSQL, con el contenedor iniciado:
```powershell
docker compose exec -T postgres psql -U controlgastos -d controlgastos -c 'SELECT version();'
```
Ese comando usa los nombres del ejemplo; ajustarlos si cambiaste usuario/base. scripts/check_database.py usa las variables configuradas y verifica la conexión real desde Django.
Parar sin borrar datos: `docker compose down`. El volumen persiste. No usar `down -v` salvo intención explícita de borrar la base. Cambiar la contraseña en `.env` no cambia la contraseña de un volumen ya inicializado.

## Seguridad y siguiente fase
Las rutas son privadas por defecto. Cookies de sesión y CSRF: HttpOnly, SameSite=Lax; Secure y redirección HTTPS con DEBUG=false. Sesión persistente de 14 días, restaurada desde auth/me/ al recargar. Cambio de contraseña mantiene la sesión actual y hace inválidas las demás al comprobar su hash. Contraseñas mediante hashers/validadores Django; campos sensibles fuera de respuestas y sin registro en logs de aplicación. Docker y runserver son exclusivamente locales.

Pendiente: notificaciones programadas, exportaciones asíncronas, conciliación y conversión de monedas. Arquitectura, modelo y reglas actuales en docs/arquitectura.md, docs/modelo-datos.md, docs/finanzas.md, docs/analitica-presupuestos.md y docs/reportes-auditoria.md.

## Estado de verificación del entorno inicial
Ver `docs/verificacion.md` para resultados reales y limitaciones. Tener configuración creada no implica que todos los servicios hayan sido ejecutados.

Este equipo conserva sus `.env` ignorados y el volumen PostgreSQL. El host tiene Python MSYS 3.11.6 (sin soporte para psycopg-binary), Node 16.20.2 y npm 8.19.4. Para ejecución nativa instalar Python oficial y Node 22.12+; no se modificaron instalaciones globales. La alternativa Docker usa Python 3.12 y Node 22 y permite ejecutar el sistema completo.
