# Verificación — Fases 1–6

## Fase 6: movimientos recurrentes

Fecha: 13 de octubre de 2026, America/Lima. Trabajo en `feature/fase-6-recurrencias`, desde `ec316d3`; sin commits, push ni cambios en main.

| Comprobación | Resultado real |
| --- | --- |
| Migraciones revisadas y aplicadas | recurring/0001_initial y audit/0003_alter_auditevent_operation; sin borrar datos ni volúmenes |
| Preservación al migrar | Antes/después: 17 usuarios, 22 cuentas, 23 movimientos, 3 presupuestos y 24 eventos de auditoría |
| Suite completa PostgreSQL | 126 tests OK, sin omisiones, 160.785 s; conserva las 97 pruebas anteriores y añade 29 de recurrencia |
| Suite completa SQLite | 126 tests OK, skipped=6, 146.287 s; omite tres concurrencias, dos casos NUMERIC extremos y el trigger exclusivo de PostgreSQL |
| Cobertura nueva | Calendario y anclas, zona horaria, precisión, relaciones, CSRF, aislamiento, confirmación/omisión, ejecución automática, reintentos, fallos, rollback, concurrencia, saldos/presupuestos y consultas del listado sin N+1 |
| Chromium | recurring_flow.py, auth_flow.py, finance_flow.py, analytics_flow.py y reports_flow.py ejecutados: OK |
| Automatización real | Worker periódico ejecutando cada 30 segundos; el flujo nuevo cierra la página, espera y verifica un ingreso automático único de S/ 80.25 al regresar |
| Visual | Captura móvil de recurrencias inspeccionada; prueba de ancho sin desbordamiento y estados de ejecución/paginación |
| Frontend final | npm run typecheck y npm run build OK; Vite procesó 657 módulos sin advertencias |
| Configuración final | Django check sin incidencias; makemigrations --check --dry-run: No changes detected; backend y worker reconstruidos y arrancados con el código final |

Los comandos reproducibles están en README y las decisiones, modelos y endpoints en [recurrencias.md](recurrencias.md). Las pruebas usan bases separadas; los flujos de navegador conservan sus cuentas sintéticas y capturas ignoradas. No se instalaron dependencias globales ni se modificaron los locks.

Problemas resueltos durante la verificación: el test de cancelación necesitaba esperar la respuesta CSRF/DELETE antes de comprobar el estado; la comprobación móvil necesitaba esperar el redimensionado de Recharts. Ambos flujos se repitieron correctamente sin ocultar el desbordamiento mediante CSS. El listado carga cuentas y clasificaciones con select_related y tiene una regresión de número de consultas.

Limitaciones: solo PEN y registro contable interno, sin pagos bancarios. Los próximos movimientos muestran una ocurrencia por regla, incluidos atrasados; no son un pronóstico completo del periodo. AUTO necesita mantener activo el perfil Docker recurring; los fallos se reintentan con espera mínima de 60 segundos. Las reglas conservan su zona horaria original y el calendario se bloquea tras un intento u omisión. Las ejecuciones pendientes no alteran saldos, reportes ni presupuestos.

## Fase 5: resultado final

Fecha: 13 de octubre de 2026, America/Lima. Punto de recuperación previo: commit local 918736c; esta fase no realiza commits.

| Comprobación | Resultado real |
| --- | --- |
| Inspección | Instrucciones, README, documentación relevante, cuentas/clasificaciones/movimientos/analítica/presupuestos y sesiones/CSRF revisados; plan incremental presentado |
| Dependencias | Contenedor limpio Python 3.12: lock anterior + rangos nuevos resueltos, pip check OK, pip freeze real. openpyxl 3.1.5 y ReportLab 4.5.1, cinco dependencias añadidas al lock |
| Migraciones | audit/0001_initial crea eventos e índices; 0002_append_only agrega trigger UPDATE/DELETE PostgreSQL. Revisadas y aplicadas OK; sin UPDATE financiero, reset ni eliminación de volumen |
| Preservación al migrar | Antes/después: 13 usuarios, 17 cuentas, 17 movimientos, 2 presupuestos |
| Pruebas nuevas | apps.reports + apps.audit: 18 tests PostgreSQL OK, incluidos XLSX/CSV/PDF, inyección, precisión extrema, límites, aislamiento, snapshots, rollback y transferencia idempotente |
| Regresión completa PostgreSQL | 97 tests OK sin omisiones, 119.661 s; incluye las 79 pruebas anteriores, concurrencia y restricciones PostgreSQL; base de tests separada |
| Regresión completa SQLite | 97 tests OK, skipped=5, 102.566 s; dos concurrencias previas, dos precisiones NUMERIC extremas y trigger PostgreSQL omitidos |
| Ajuste posterior de PDF | Diez tests de reports PostgreSQL OK tras mantener juntas las dos filas por movimiento; 12.330 s |
| Comprobación final de módulos nuevos | 18 tests reports/audit PostgreSQL OK, 23.002 s, después de estado vacío, nombre inclusivo de archivo y formato Python a 79 columnas |
| Esquema/configuración | Django check sin incidencias; makemigrations --check --dry-run: No changes detected |
| Frontend | Build incluye tsc --noEmit; 654 módulos, OK. Inicial 319.36 kB, reports 8.08 kB, analítica 427.32 kB; sin advertencia de importación tras corregir AuditHistory |
| Chromium nuevo | reports_flow.py OK: filtros combinados, preview, descargas XLSX/CSV/PDF con sesión real, creación/edición/anulación auditada, privacidad de campos, estado VOID, móvil y rutas privadas |
| Chromium regresiones | analytics_flow.py, finance_flow.py y auth_flow.py OK, incluidos seis gráficos, presupuestos, reintento de transferencia y sesiones/cambio de contraseña; sin pageerror |
| PDF renderizado | QA sin base: 40 movimientos con descripciones de 500 caracteres, 16 páginas renderizadas con PyMuPDF 1.28.2. Texto incluye total exacto y último movimiento; portada, páginas intermedias y cierre inspeccionados |
| Visual frontend | Capturas de reportes escritorio y auditoría móvil inspeccionadas; tests verifican ausencia de desbordamiento horizontal. Descargas sintéticas/capturas ignoradas |
| PostgreSQL final consultado | SELECT 1 = 1, UTC, 18 tablas, 17 usuarios; cuatro usuarios adicionales creados y conservados por los cuatro flujos E2E |

Comandos reproducibles y endpoints en README y [reportes-auditoria.md](reportes-auditoria.md). Los resultados completos preceden al último ajuste de estado vacío/nombre inclusivo del archivo; las suites específicas reports/audit se repitieron después de esos ajustes y pasaron. El render final comprobó todas las cajas de texto dentro de las páginas y parejas de filas por movimiento. Ningún fallo o ejecución interrumpida se considera aprobación.

### Problemas encontrados

- Primer render: las filas de identidad/importe y descripción del mismo movimiento podían caer en páginas diferentes. Se agregó NOSPLIT por pareja, se regeneraron los documentos y se repitieron pruebas y revisión visual.
- Un comando auxiliar de render falló por las comillas de Python dentro de PowerShell/Docker. Se sustituyó por render_report_qa.py; el render posterior finalizó correctamente. No se instalaron herramientas globales.
- Build inicial advertía AuditHistory importado tanto estática como dinámicamente. Se mantuvo su importación compartida estática (componente pequeño); el build final pasó sin esa advertencia.
- El primer comando de prueba generó artefactos PDF válidos y la suite confirmó su cabecera/EOF, pero eso no se tomó como prueba visual. La comprobación de paginación se hizo después sobre PNG renderizados.
- SQLite no reproduce NUMERIC extremo ni triggers/concurrencia PostgreSQL; las cinco omisiones son explícitas. PostgreSQL ejecutó todos esos casos.

### Límites

Exportaciones síncronas limitadas por rango/filas y contador atómico. XLSX conserva dinero como texto con formato PEN: no sumas nativas sin conversión explícita. PDF con fuente latina; no garantiza alfabetos/símbolos fuera de su repertorio. Sin plantillas guardadas, exportaciones en cola, firmas digitales ni auditoría resistente a administradores de base. Auditoría comienza al activar Fase 5, no reconstruye historia; señales solo para escrituras que siguen owner_lock/save, no SQL externo/bulk. Chromium Linux y viewport móvil, sin dispositivos físicos/Firefox/WebKit/carga/producción. El host antiguo sigue requiriendo contenedores o versiones compatibles; no se cambió software global ni se borraron datos.

Los resultados siguientes conservan el historial de fases anteriores.

## Fase 4: resultado final

Fecha: 13 de octubre de 2026, America/Lima.

Historia comprobada: React con cookies/CSRF → presupuestos y movimientos propios en PostgreSQL → agregaciones exactas → seis gráficos, comparaciones y alertas → corrección/anulación de gastos con progreso actualizado. Se conservaron las fases anteriores y el volumen persistente.

| Comprobación | Resultado real |
| --- | --- |
| Inspección | README, AGENTS, documentación y puntos de integración revisados antes de modificar; plan incremental presentado |
| Conexión inicial | SELECT 1 = 1; UTC; 16 tablas y 9 usuarios |
| Migración | budgets/0001_initial generada por Django 5.2.18, revisada: solo CreateModel Budget y restricciones; aplicada OK |
| Conservación al migrar | Antes y después: 9 usuarios, 12 cuentas, 11 movimientos; sin operaciones de eliminación/reset/volumen |
| PostgreSQL final | `test apps.core apps.users apps.transactions apps.analytics apps.budgets --settings=config.settings_test_postgres`: **79 tests, OK**, 88.247 s, sin omisiones; base temporal separada |
| SQLite final | Mismo comando con config.settings_test: **79 tests, OK, skipped=3**, 82.695 s |
| Esquema final | check sin incidencias; makemigrations --check --dry-run: No changes detected |
| Precisión e integración | Agregaciones NUMERIC extremas, transferencias/VOID/crédito excluidos de gastos duplicados, UTC/Lima y DST, aislamiento, comparación cero, presupuesto CRUD/80/100, restricciones y CSRF |
| Consultas | Tests demuestran progreso agrupado sin consulta por presupuesto y dashboard con igual cantidad de consultas al añadir 15 cuentas; lecturas no modifican ledger |
| Frontend final | npm run build incluye tsc --noEmit; 651 módulos, compilación OK; carga diferida: inicial 315.12 kB, analítica 427.32 kB, presupuestos 6.75 kB, sin advertencia de paquete >500 kB |
| Chromium analítica | analytics_flow.py OK: creación/edición de presupuesto, alertas 80/100, seis gráficos, filtros/año/agrupación, comparación, análisis, gasto anulado, desactivación, móvil, sesión persistente y rutas privadas |
| Chromium regresiones | finance_flow.py y auth_flow.py OK, incluido reintento de transferencia tras pérdida de respuesta y cambio de contraseña; sin pageerror |
| Revisión visual | Capturas de dashboard escritorio y presupuestos móvil inspeccionadas; controles y tarjetas legibles; tests comprueban ausencia de desbordamiento horizontal |
| Servicios | Backend/frontend/PostgreSQL activos en puertos locales 8000/5173/5432; postgres saludable. Health HTTP devuelve contrato original |
| PostgreSQL final consultado | SELECT 1 = 1, UTC, 17 tablas, 13 usuarios; los 4 adicionales son sintéticos creados por E2E, uno en un intento fallido y tres en los flujos completos |
| Git | Sin commits; .env, frontend/.env, dist y capturas siguen ignorados |

### Problemas encontrados y correcciones

- Primer intento backend: Django había detenido autoreload mientras se añadían módulos/rutas todavía incompletos. La captura E2E mostró error de conexión. Se reconstruyó/recreó backend con los módulos completos y se comprobó health antes de repetir Chromium.
- Navegación comparación → análisis: se reutilizaba la instancia React con una respuesta anterior de estructura diferente. Se dieron claves distintas a las rutas; el flujo repetido pasó. Vite sirvió el código actualizado con polling habilitado.
- La prueba de método POST esperaba 405 sin enviar CSRF; 403 era la protección correcta. Se corrigió la prueba para enviar un token válido, sin relajar seguridad.
- SQLite redondea centavos de un importe extremo NUMERIC(18,2). La prueba extrema se ejecuta exclusivamente en PostgreSQL. Junto con las dos pruebas de concurrencia anteriores, explica las tres omisiones SQLite.
- Una ejecución SQLite fue interrumpida por recrear backend; no se contó como resultado válido. Las suites finales completas anteriores sí finalizaron.
- Build inicial advertía paquete grande al importar Recharts de forma inmediata. Se cargaron las vistas analíticas de forma diferida y el build final pasó sin esa advertencia.

### Reproducción y límites

Comandos completos en README; contrato y decisiones en [analitica-presupuestos.md](analitica-presupuestos.md). Tests de backend crean bases temporales. Chromium usa Playwright 1.56.0 en contenedor Linux contra localhost, con cookies/CSRF reales y cuentas sintéticas conservadas; capturas ignoradas en tests/browser/artifacts/. No se imprimen contraseñas. No se modificaron dependencias globales ni se añadieron servicios externos.

PEN y presupuestos mensuales; alertas visuales al consultar, sin correo/notificaciones automáticas. Geometría de gráficos normalizada y aproximada, importes exactos en tooltips/tablas. Comparaciones de igual duración local inmediatamente anterior, no necesariamente meses calendario. Sin pruebas de carga, dispositivos físicos, Firefox/WebKit ni despliegue de producción. Estado anterior del host permanece: Python MSYS 3.11.6 y Node 16 no sirven para la instalación nativa completa; usar los contenedores probados o instalar versiones compatibles con autorización.

Los resultados siguientes son históricos de Fases 1–3.

## Fase 3: resultado final

Fecha: 12 de octubre de 2026, America/Lima.

Historia verificada: cuentas/clasificaciones propias → registro de ingresos/gastos y transferencias con cookies/CSRF → PostgreSQL → historial, correcciones/anulaciones y resumen exacto. Se reutilizaron autenticación, usuario UUID, configuración y volumen existentes.

| Comprobación | Resultado real |
| --- | --- |
| Inspección inicial | AGENTS, README, todos los documentos y puntos de integración revisados; 4 usuarios y 11 tablas antes de la fase |
| Conexión inicial | Django–PostgreSQL SELECT 1 = 1, conexión UTC |
| Modelos | check sin incidencias; accounts/categories/transactions separados |
| Migraciones | Tres 0001_initial generadas por Django, revisadas y aplicadas; 16 tablas al finalizar |
| Catálogo | seed_catalog ejecutado dos veces sobre los 4 usuarios existentes; conservación e idempotencia también probadas en suite |
| PostgreSQL final | 62 tests, OK sin omisiones; incluye los 37 tests anteriores y casos financieros/concurrencia |
| SQLite final | 62 tests, OK; 2 omitidos (concurrencia auth y transferencias, requieren PostgreSQL) |
| Esquema | makemigrations --check --dry-run: No changes detected |
| Frontend final | npm run build: tsc --noEmit y Vite correctos; 60 módulos transformados |
| Imagen backend | Reconstruida con el código/migraciones financieros; backend recreado y check correcto |
| E2E financiero | finance_flow.py terminó con código 0 y todas las etapas PASS; repetido tras habilitar corrección de saldo inicial |
| E2E autenticación | auth_flow.py también terminó con código 0 tras la incorporación de la interfaz financiera |
| Datos existentes | Después de migraciones/catalogado seguían 4 usuarios; al finalizar 9, por 5 usuarios sintéticos conservados de ejecuciones de navegador |
| Secretos/artefactos | .env, frontend/.env, dist y capturas ignorados por Git; no se introdujeron secretos ni dependencias nuevas |
| Control de versiones | Sin commits, sin reset/borrado de datos o volumen |

Pruebas financieras: CRUD lógico de cuentas/clasificaciones; saldos iniciales de crédito y campos financieros congelados tras historial; catálogo repetido que conserva renombrados/inactivos; ingreso/gasto, edición y VOID; importes string/Decimal, rechazo de números JSON, ceros/negativos/precisión excesiva/NaN/Infinity; fecha explícita con zona y calendario válido, rechazo de futuro; jerarquía/tipo/moneda/propiedad; aislamiento de listas, detalle, balance, PATCH y DELETE; CSRF y sesión; transferencia sin clasificación, destinos propios/distintos, idempotencia/conflicto/alcance por propietario; rollback después de una escritura real simulando error; cinco solicitudes concurrentes con una sola transferencia; pago de crédito sin doble gasto; exactitud 0.10 + 0.20 = 0.30; agrupaciones/evolución; límites temporales locales Lima y Tokyo; filtros/paginación/ordenamiento.

El E2E financiero creó banco/efectivo/tarjeta, corrigió saldo inicial antes de usar la cuenta, creó área/categoría/subcategoría propias, registró gasto de tarjeta e ingreso y pagó deuda con transferencia. Se guardó la primera transferencia y se abortó deliberadamente su respuesta al navegador; el botón de reintento reutilizó clave/payload y recuperó el mismo registro. El historial mostró una sola transferencia y el resumen conservó gasto 30.00, ingreso 200.00 y patrimonio 1120.00. Se registró Yape contra el banco, se editó/anuló ese gasto y se comprobó que su efecto desapareció de saldos/reportes mientras el registro siguió en historial.

También se verificaron filtros de estado/tipo/día, agrupación semanal, detalle, recarga, cierre de sesión, rutas privadas y vistas móviles sin desbordamiento de página. Capturas finance-summary-desktop/mobile y finance-accounts-mobile en tests/browser/artifacts/, ignoradas; resumen móvil revisado visualmente. Componentes revisados con React best practices. No se usaron importes float para renderizar ni calcular dinero.

### Problemas encontrados y límites

- El ejecutor del sandbox seguía sin iniciar procesos; se usaron comandos aprobados fuera de él y los contenedores existentes, sin cambiar instalaciones globales.
- El primer intento E2E usó regex en select_option, que Playwright no admite; se corrigió el script para seleccionar el UUID de la opción por texto.
- La simulación de respuesta perdida inicialmente usó Route.fetch contra localhost del contenedor, distinto de la resolución DNS de Chromium. Se dirigió al host de Docker conservando Host/Origin locales y se evitó imprimir excepciones de red con cabeceras. La prueba corregida pasó.
- Se ajustó el formulario para reintentar desde el payload congelado cuando los campos estaban deshabilitados, y para liberar el borrador tras un 400. Se restablece el detalle después de guardar una corrección.
- Los cuatro usuarios anteriores y sus sesiones/datos no se borraron. Usuarios y movimientos de pruebas de navegador, incluidos intentos parciales, permanecen en cuentas sintéticas separadas; no se creó ningún administrador real.
- Chromium Linux en contenedor con escritorio y viewport móvil; no se probaron dispositivos físicos, Firefox/WebKit, producción ni carga masiva. Tabla de evolución con grupos activos; no gráficos monetarios en esta fase.
- PEN únicamente, sin conversión. No hay bitácora de versiones anteriores de correcciones, recurrencia, presupuestos ni exportación. Reintentos UI conservados en memoria; tras recargar una transferencia de resultado incierto, consultar historial antes de generar otra clave. Reglas completas en docs/finanzas.md.

Backend, frontend y PostgreSQL quedan activos en 8000/5173/5432 publicados localmente. README contiene instalación, actualización de la base existente, seed idempotente, endpoints y comandos de pruebas reproducibles.

## Historial: Fase 2, resultado final

Fecha: 12 de octubre de 2026, America/Lima.

Historia verificada: registro/inicio de sesión desde React → API Django con cookies y CSRF → persistencia PostgreSQL → dashboard y perfil protegidos, con recarga, cambio de contraseña y cierre de sesión.

| Comprobación | Evidencia / resultado |
| --- | --- |
| Conexión antes de migrar | scripts/check_database.py: SELECT 1 = 1, timezone UTC, 0 tablas, sin django_migrations |
| Regresión Fase 1 | 4 tests health originales pasaron antes de cambiar el modelo; se conservaron |
| Modelo/configuración | AbstractUser con UUID/email, AUTH_USER_MODEL antes de migrar; Django check sin incidencias |
| Migración | 0001_initial generada por Django, revisada (User y AuthRateLimit), plan revisado y aplicada junto con migraciones Django |
| PostgreSQL después de migrar | SELECT 1 = 1, UTC, 11 tablas; consulta de usuarios mediante ORM correcta |
| SQLite final | 37 tests: OK, 1 omitido (concurrencia PostgreSQL) |
| PostgreSQL final | 37 tests: OK, sin omisiones; base temporal test_controlgastos creada/eliminada por Django |
| Consistencia de esquema | makemigrations --check --dry-run: No changes detected |
| Frontend final | npm run build: tsc --noEmit y Vite build correctos, 51 módulos transformados |
| Lock Python | Generado con pip freeze del contenedor; reconstrucción e instalación del lock correctas |
| Dependencias frontend | Lock actualizado con npm; npm ci ejecutado; npm informó 0 vulnerabilidades en esa ejecución |
| Chromium E2E | auth_flow.py terminó con código 0; todas las etapas PASS |
| Seguridad de archivos | .env, frontend/.env, .venv, frontend/dist y tests/browser/artifacts ignorados por Git |
| Control de versiones | Sin commits; no se configuró remoto ni se borraron datos |

Cobertura backend: registro/normalización/hash, correo duplicado y restricción PostgreSQL insensible a mayúsculas, contraseñas débiles/similares, privilegios rechazados, login válido/inválido/inactivo, logout e invalidación, CSRF ausente/inválido/origen/rotación, endpoints privados, consulta/modificación de perfil, preferencias inválidas, aislamiento entre usuarios, cambio de contraseña (conserva sesión actual/invalida otras), persistencia y rotación de sesión, límites/expiración, concurrencia entre seis peticiones, Admin con CSRF y límites compartidos, manager y comando createsuperuser.

Cobertura navegador: redirección anónima al login, validación de confirmación de contraseña, registro real, error de login, login correcto, cookie HttpOnly/SameSite, recarga de sesión, perfil persistido, cambio de contraseña, móvil de 390px sin desbordamiento, logout, ruta privada protegida, login con nueva contraseña y regreso al destino previo, 404, sin pageerror de JavaScript. Capturas locales revisadas de login escritorio y dashboard móvil; los artefactos están ignorados por Git. Se revisaron componentes según React best practices.

El flujo utiliza datos sintéticos. Se conservaron las cuentas creadas durante las ejecuciones E2E (incluidos intentos anteriores); no se eliminan usuarios ni se publican sus contraseñas. No se creó administrador en la base de desarrollo: createsuperuser se verificó en base temporal de tests.

## Entorno y problemas encontrados

- Host: Python MSYS 3.11.6, Node 16.20.2, npm 8.19.4, Docker 29.1.3 y Compose v5.0.0-desktop.1. Node es demasiado antiguo para el frontend; Python MSYS no admite el driver binario. No se modificaron instalaciones globales.
- Contenedores comprobados: Python 3.12.15, Node 22.23.3, npm 10.9.9. PostgreSQL mantiene el volumen de Fase 1. Backend/Frontend/PostgreSQL quedan activos en puertos locales 8000/5173/5432.
- El ejecutor del sandbox seguía fallando; los comandos se ejecutaron con aprobación fuera de él. El conector de navegador tampoco pudo arrancar por ese error. Se usó Chromium Linux/Playwright 1.56.0 en un contenedor temporal, sin ampliar los orígenes CORS/CSRF.
- El primer E2E falló en el regreso a /perfil tras login: la redirección automática pública competía con el destino recordado. Se unificó el destino permitido en ambos puntos.
- La repetición aún servía código anterior: se confirmó que Vite no reflejaba el cambio aunque el archivo montado sí lo contenía. Se activó VITE_USE_POLLING en Docker/Windows. Un intento inmediato tras recrear el frontend falló antes de que npm ci/Vite terminaran; tras confirmar disponibilidad y código actualizado, el E2E completo pasó.
- Un parche fue rechazado sin motivo informado; tras la confirmación expresa del usuario se incorporaron las protecciones adicionales de Admin y Retry-After.

## Límites de esta verificación

Chromium de escritorio y viewport móvil, no dispositivos físicos ni Firefox/WebKit. Los límites atómicos se probaron contra PostgreSQL; no equivalen a pruebas de carga ni defensas DDoS. Desarrollo es HTTP local, por eso Secure=false; producción exige HTTPS con DEBUG=false y su configuración de proxy. No se desplegó producción. No se probaron módulos financieros, recuperación de contraseña ni verificación/cambio de correo, fuera de esta fase.

Comandos reproducibles y endpoints en README.md. Las siguientes fases pueden partir de usuarios/sesiones migrados y probados, conservando el aislamiento como requisito.

## Historial: Fase 1

Lo siguiente conserva los resultados históricos de la Fase 1; sus pendientes de conexión/autenticación fueron abordados arriba.

Fecha: 12 de octubre de 2026, America/Lima.

| Comprobación | Resultado |
| --- | --- |
| Inspección inicial | Directorio vacío; no existía repositorio Git |
| Git | Repositorio inicializado; sin commit ni remoto |
| Tests HTTP | `python backend/manage.py test apps.core --settings=config.settings_test`: 4 tests OK |
| Django aislado | `check --settings=config.settings_test`: sin incidencias |
| Dependencias backend completas | Instalación correcta en contenedor temporal Python 3.12 estándar |
| Django con configuración PostgreSQL | `python manage.py check` en contenedor: sin incidencias |
| Compose | `docker compose config --quiet`: correcto |
| PostgreSQL | `docker compose up -d --wait postgres`: saludable; `SELECT version()` respondió PostgreSQL 17.11 |
| Frontend | Contenedor temporal Node 22: npm install correcto, TypeScript sin errores y Vite build correcto |
| Dependencias frontend | npm reportó 0 vulnerabilidades en esa instalación; package-lock.json generado realmente |

Los tests usan SimpleTestCase y no acceden a base de datos. La comprobación de Django con configuración PostgreSQL valida configuración/importación del driver; no demuestra una consulta Django–PostgreSQL. PostgreSQL sí fue consultado directamente con psql. No se aplicaron migraciones.

Se revisaron estructura, hooks, cancelación de fetch, estados y accesibilidad de los dos archivos TSX siguiendo la habilidad React best practices. No se ejecutó una prueba visual ni el flujo frontend–API en navegador. Los artefactos de compilación quedaron en el contenedor temporal; para generarlos en el host ejecutar npm ci y npm run build.

Limitaciones del host: Python 3.11.6 de MSYS, sin pip inicialmente; se creó .venv y se instalaron las dependencias HTTP, pero psycopg-binary no tiene distribución compatible con ese intérprete. Node.js y npm no estaban disponibles. Instalar Python oficial y Node 22.12+ para el flujo local documentado.

El ejecutor del sandbox comenzó a fallar al crear procesos; verificaciones posteriores se ejecutaron con aprobación fuera del sandbox. Docker inicialmente negó acceso desde el sandbox y fue verificado fuera de él. Git fuera del sandbox requiere una excepción de propiedad por comando porque el repositorio fue creado por el usuario del sandbox; no se modificó la configuración Git global.

La primera ejecución de tests sin etiqueta desde la raíz descubrió 0 tests; se corrigió el comando documentado para señalar apps.core y se ejecutaron los 4 tests realmente. No se considera aquella ejecución una validación.

Pendiente para Fase 2: definir usuario personalizado antes de migrar, implementar autenticación/CSRF y verificar sesiones y aislamiento de usuarios con PostgreSQL.
