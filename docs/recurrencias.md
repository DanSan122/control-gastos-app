# Movimientos recurrentes y programación — Fase 6

## Arquitectura y alcance

apps.recurring gestiona reglas y ocurrencias, no envía pagos ni se conecta a bancos. GENERAR una ocurrencia pendiente no crea Transaction. Al confirmar o procesar una fecha vencida se utiliza apps.transactions.creation.create_movement, compartido con ingresos/gastos y transferencias de Fase 3. Este servicio requiere owner_lock y valida TransactionSerializer; mantiene dinero Decimal/NUMERIC y auditoría atómica. No hay bulk_create ni SQL financiero externo.

Trabajar en feature/fase-6-recurrencias, desde main/ec316d3. Sin commits, push ni merge autorizados en esta tarea. Configuración de producción y secretos sin cambios; el worker es una extensión optativa de desarrollo en compose.dev.yaml.

## Modelos

RecurringRule: UUID, owner PROTECT, name, kind INCOME/EXPENSE/TRANSFER, amount NUMERIC(18,2) positivo, currency PEN, source_account y destination_account opcional PROTECT, clasificación PROTECT para ingresos/gastos, payment_method existente, frequency DAILY/WEEKLY/MONTHLY/YEARLY, interval 1–1000, start_date, end_date opcional, next_due_date nullable, timezone IANA, execution_mode MANUAL/AUTOMATIC, status ACTIVE/PAUSED/COMPLETED/CANCELLED, created_at/updated_at UTC.

Timezone se toma de request.user al crear y queda fijada a la regla. Cambiar la preferencia del perfil no desplaza un calendario existente. Fechas de calendario son DATE locales; timestamps de intentos/movimientos/eventos son instantes UTC. Inicio entre 1900 y 9998. next_due_date es null en estados terminales; ACTIVE/PAUSED conservan cursor.

RecurringExecution: UUID, rule PROTECT, scheduled_date local, status PENDING/EXECUTED/FAILED/SKIPPED, transaction OneToOne PROTECT nullable, attempted_at, executed_at, error_code seguro, created_at UTC. Unicidad `(rule, scheduled_date)`, enlace único al movimiento y CHECK que exige movimiento/fecha de ejecución solo para EXECUTED. No guarda credenciales ni excepciones en claro.

Índices: reglas por owner/status/next_due_date y execution_mode/status/next_due_date; ejecuciones por rule/status/scheduled_date. Restricciones complementan validación de propietario, activos, jerarquía, monedas y tipo reutilizada desde TransactionSerializer.

## Calendario y cambios

- DAILY: suma interval días locales.
- WEEKLY: suma interval × 7 días locales.
- MONTHLY: avanza interval meses, utilizando siempre el día del inicio como ancla.
- YEARLY: avanza interval años, utilizando siempre mes/día del inicio como ancla.

Días 29, 30 y 31 se limitan al último día disponible, sin arrastrar ese recorte: 31/01/2027 → 28/02/2027 → 31/03/2027. Un 29/02 anual vuelve al 29 cuando el año es bisiesto. Fin es inclusivo; tras la última ocurrencia ejecutada/omitida, la regla pasa a COMPLETED y no crea otra ocurrencia. Desbordamiento del calendario también finaliza.

El movimiento efectivo usa el inicio de scheduled_date en la zona fijada, convertido a UTC. Si el cambio horario elimina medianoche, usa el primer minuto local válido. Si desaparece el día completo (por ejemplo Pacific/Apia 30/12/2011), conserva FAILED/CALENDAR_DATE_UNAVAILABLE; no inventa otro día. No hay selector de hora ni ejecución futura: fecha debe haber vencido en la zona de la regla.

Tipo e inicio son inmutables después de crear la primera ocurrencia. Frecuencia/intervalo se editan solo antes de cualquier ejecución, omisión o intento fallido. Importe, cuentas, clasificación, método, nombre y modo se aplican a pendientes/futuros; movimientos ya creados conservan sus datos. Fin no puede recortar una ocurrencia pendiente: cancelar si se desea detener antes. COMPLETED/CANCELLED no se editan ni reanudan; crear otra regla. DELETE puede cancelar lógicamente una regla y siempre conserva historial.

Pausa conserva la fecha pendiente. Reanudar valida relaciones activas y mantiene atrasados; el procesador puede ponerse al día. No se omiten atrasados automáticamente. Registros PENDING de reglas canceladas quedan conservados pero no aparecen como próximos ni admiten confirmación.

## Ejecución e idempotencia

POST de regla prepara una única primera ocurrencia. Tras cada ejecución/omisión, avanza cursor y prepara la siguiente. Lecturas GET no crean registros. Solo se muestra el próximo vencimiento preparado de cada regla, no toda una proyección mensual de repeticiones.

Confirmación y scheduler toman owner_lock dentro de atomic, verifican propietario/estado/modo/fecha y vuelven a validar las relaciones actuales. Clave determinista UUIDv5 por regla/fecha, usada también como idempotency_key del movimiento y correlación de auditoría. Restricciones PostgreSQL y el bloqueo del propietario complementan esta estrategia. No hay carrera separando preparar y ejecutar en el procesador.

Movimiento, evento financiero, ejecución y avance del cursor pertenecen a una misma transacción. Una caída de auditoría revierte el conjunto; la ocurrencia pendiente no se pierde. Errores de validación/BD se revierten mediante savepoint y guardan FAILED con código INVALID_RELATIONS/TEMPORARY_FAILURE, sin detalle sensible ni movimiento parcial. Tras corregir relaciones se puede reintentar la misma ocurrencia. Fallos transitorios del proceso que impiden incluso guardar FAILED dejan el estado anterior para el siguiente intento; el scheduler registra solo PROCESS_RETRY_REQUIRED.

EXECUTED devuelve el mismo resultado al reintentar, aun si posteriormente su movimiento se anula. No recrea un movimiento VOID. SKIPPED es inmutable; repetir skip no genera otro evento. Omitir una ejecución realizada se rechaza. No se pueden confirmar/omitir futuras, pausadas, canceladas o fuera del cursor. AUTO se ejecuta por el comando, no por confirmación manual; cambiar explícitamente el modo si se necesita intervención manual.

Historial muestra el importe/tipo del movimiento real cuando existe, no el importe actual de una regla editada. FAILED/PENDING son planificación sin efectos de saldo. Transferencias usan un único movimiento, excluido de ingresos/gastos y presupuestos; pagos de tarjeta no duplican gastos.

## Procesador real

Sin Celery/Redis ni nuevas dependencias. Comando idempotente:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend python manage.py process_recurring --limit 100 --per-rule 100
```

Selecciona AUTOMATIC/ACTIVE de propietarios activos, hasta 100 reglas y 100 ocurrencias por regla/ciclo (argumentos 1–1000). No procesa MANUAL, PAUSED, CANCELLED, COMPLETED ni fechas futuras. Fallos conocidos frenan esa regla y reintentan tras al menos 60 segundos; otros ciclos pueden continuar las demás. No garantiza orden global ni rendimiento de pagos masivos.

Para ejecución sin navegador, **después de aplicar migraciones**:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile recurring up -d --build recurring-worker
docker compose -f compose.yaml -f compose.dev.yaml logs --tail 20 recurring-worker
```

Servicio real de desarrollo: run_recurring_scheduler --seconds 30. Proceso continuo, conexiones renovadas, SIGTERM/SIGINT detienen de forma segura, reinicio unless-stopped. Perfil recurring optativo; no altera compose.yaml de PostgreSQL ni producción. Un solo comando manual no significa automatización. En esta fase se inicia y verifica el worker y se prueba una ejecución con la página cerrada.

Detenerlo conservando todo:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml stop recurring-worker
```

Para otro despliegue, programar process_recurring con cron/systemd/scheduler de la plataforma, con las mismas variables privadas y base; no añadir cron al host sin autorización. Servidor y worker deben usar la misma versión de código y migraciones. Los límites pueden requerir ajustes según volumen; no hay backoff exponencial ni notificaciones de fallos.

## API privada bajo /api/v1/

| Ruta | Métodos |
| --- | --- |
| recurring/rules/ | GET, POST |
| recurring/rules/{uuid}/ | GET, PATCH, DELETE (cancelación, 204) |
| recurring/rules/{uuid}/pause/ | POST |
| recurring/rules/{uuid}/resume/ | POST |
| recurring/upcoming/ | GET |
| recurring/executions/ | GET |
| recurring/executions/{uuid}/ | GET |
| recurring/executions/{uuid}/confirm/ | POST |
| recurring/executions/{uuid}/skip/ | POST |

Sesión obligatoria, CSRFSafeSessionAuthentication y CSRF en escrituras. UUID ajeno/inexistente da 404; campos técnicos/status/owner/timezone no editables. Acciones reciben `{}` sin campos adicionales. FAILED al confirmar da 422 con código seguro y ocurrencia conservada; validaciones/regla no activa/futuro dan 400. Reintentos ya ejecutados/omitidos dan 200. Ejecuciones no tienen PATCH/DELETE/POST colección.

Reglas: filtros kind/status/frequency/execution_mode, orden next_due_date/id. Ejecuciones: rule UUID/status, orden fecha descendente/id. Paginación 25/máximo 100. Upcoming: days 1–366, 30 por defecto, incluye atrasados y excluye reglas no activas. Respuesta paginada incluye scheduled_totals income/expense/transfer como cadenas: suma del próximo vencimiento de cada regla, **no gasto realizado ni proyección de todas las repeticiones del mes**. Ventana de presentación según zona actual del usuario; cada ejecución conserva zona de su regla.

Ejemplo:

```json
{"name":"Servicio mensual", "kind":"EXPENSE", "amount":"50.00", "currency":"PEN", "source_account":"UUID propio", "area":"UUID propio", "category":"UUID de gasto propia", "frequency":"MONTHLY", "interval":1, "start_date":"2026-10-31", "end_date":null, "execution_mode":"MANUAL", "payment_method":"YAPE"}
```

## Auditoría e interfaz

Se amplía el sistema existente, no se crea otro ledger de auditoría. Reglas y ejecuciones tienen allowlist de valores; fechas locales serializadas ISO. Operaciones PAUSE/RESUME/CANCEL/EXECUTE/SKIP complementan CREATE/UPDATE existentes sin modificar eventos anteriores. Preparar PENDING es CREATE de ocurrencia, no ejecución financiera. La correlación permite relacionar ocurrencia/movimiento. No se registran excepciones, contraseñas, cookies o credenciales bancarias.

Vistas: /recurrentes, /recurrentes/nueva, /recurrentes/{uuid}, /recurrentes/{uuid}/editar. Formularios con cuentas propias/clasificaciones dependientes, dinero como cadena, confirmaciones y errores del backend; nunca se anuncia éxito antes de respuesta. Próximos en dashboard y listado; historial paginado, enlaces a movimientos, pausa/reanudación/cancelación y confirmación/omisión. Se conserva diseño responsive y rutas privadas. Actualizar próximos/historial para observar el worker; no requiere página abierta para ejecutar.

Sin efecto financiero hasta que existe Transaction POSTED. Una vez ejecutada, analítica, reportes y presupuesto la integran de forma natural. No hay gastos/ingresos virtuales en sus agregados. Las cuentas de crédito conservan deuda negativa; el límite nunca es dinero propio.

## Verificación y límites

Añadir apps.recurring a los siete módulos anteriores de test, con settings_test_postgres y settings_test. Ejecutar check, makemigrations --check --dry-run, typecheck/build y recurring_flow.py junto con auth_flow.py, finance_flow.py, analytics_flow.py, reports_flow.py. E2E usa usuario sintético y worker real, cierra la página durante 35 segundos y comprueba una única transacción automática. Conserva todos los registros; capturas ignoradas.

Migraciones: recurring/0001_initial crea reglas/ejecuciones/restricciones; audit/0003_alter_auditevent_operation amplía opciones. No se modifican tablas de usuario/cuentas/presupuestos/transacciones ni eventos anteriores. Conteos antes/después en docs/verificacion.md. No se añadieron dependencias ni se tocaron secretos.

Limitaciones: fechas sin hora configurable, PEN, próximo vencimiento por regla, procesamiento acotado por ciclo, backoff fijo y sin alertas/email. Modificar reglas no reescribe sus movimientos previos ni permite restaurar omitidos/anulados. Registro interno de finanzas, no envío bancario. Sin pruebas de carga o despliegue de producción. Worker de desarrollo opcional y detenido si Docker no está activo. Implementar notificaciones, horarios configurables y jobs de mayor escala solo en otra tarea.
