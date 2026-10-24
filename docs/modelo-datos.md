# Propuesta inicial del modelo de datos

User y AuthRateLimit están implementados en Fase 2. Account, Area, Category, Subcategory y Transaction están implementados y migrados en Fase 3; Budget en Fase 4. Currency, PaymentMethod como catálogo independiente y BudgetAlert persistido son propuestas futuras; las alertas actuales son derivadas.

## Modelo implementado

User extiende AbstractUser sin username. Clave primaria UUID; email único normalizado (strip/minúsculas), índice único Lower(email); first_name, last_name, date_joined, is_active, is_staff, is_superuser, last_login, password con hasher Django y relaciones a grupos/permisos. USERNAME_FIELD=email. Manager compatible con create_user y createsuperuser; Admin utiliza formularios de creación/cambio que gestionan el hash.

Preferencias directamente en User: timezone (64 caracteres, valor America/Lima, validador ZoneInfo/IANA) y currency (PEN por defecto; PEN/USD/EUR disponibles como preferencia). No se crea una tabla UserSettings duplicada para solo dos campos. No hay conversiones ni cálculos monetarios.

AuthRateLimit: key CHAR/VARCHAR(64) primaria con HMAC del ámbito e identidad, attempts entero no negativo y expires_at con índice. Sin relaciones a usuarios para contar peticiones anónimas. Contadores de seguridad, no historial de credenciales. La limpieza opcional elimina únicamente contadores expirados.

Tablas de sesión, permisos, grupos, contenttypes y registro administrativo gestionadas por Django. La migración users/0001_initial depende de auth para grupos/permisos y se ejecuta antes de admin mediante dependencia al modelo intercambiable. El auth.User estándar queda intercambiado, sin tabla auth_user.

## Modelo financiero de Fase 3

Account: UUID, owner (PROTECT), name, kind CASH/BANK/WALLET/CREDIT/OTHER, institution opcional, currency=PEN, initial_balance NUMERIC(18,2), created_at e is_active. Nombre único por propietario sin distinguir mayúsculas. Crédito exige saldo inicial <= 0. Saldo/deuda calculados, no persistidos.

Area/Category/Subcategory: UUID, owner, name, is_active, created_at y seed_code estable nullable. Category.area y Subcategory.category con PROTECT; Category.kind INCOME/EXPENSE. Unicidad por propietario/ámbito/tipo y unicidad de seed_code por usuario. Nueve áreas iniciales; catálogo idempotente, sin recrear/renombrar/desactivar datos del usuario.

Transaction: UUID, owner, account, destination_account nullable, kind INCOME/EXPENSE/TRANSFER, amount NUMERIC(18,2) > 0, currency=PEN, area/category requeridas para ingreso/gasto y subcategory opcional, description, occurred_at TIMESTAMPTZ, created_at/updated_at, payment_method opcional como enum, reference, status POSTED/VOID, idempotency_key UUID nullable y request_hash SHA-256. Una transferencia exige destino distinto y clasificación nula; un ingreso/gasto exige clasificación y destino nulo. Unicidad (owner, idempotency_key); índices por propietario/fecha, cuenta/fecha y categoría/fecha. Todas las FK de dominio se conservan con PROTECT.

Propiedad/jerarquía/moneda se validan en serializers bajo bloqueo del propietario. Restricciones locales de monto, forma y unicidad también están en base de datos. No hay tabla de saldo acumulado ni duplicados de movimiento para origen/destino o periodos. DELETE lógico; las correcciones no conservan versiones anteriores. Detalles y ejemplos en docs/finanzas.md.

## Entidades y ampliaciones previstas

| Entidad | Campos principales propuestos | Relaciones |
| --- | --- | --- |
| User (implementado) | UUID, email, nombres, fechas, estado, timezone, currency | Propietario de recursos |
| Currency | code CHAR(3), nombre, decimales | Catálogo de monedas |
| Account (implementado) | owner, nombre, tipo, institución, moneda, saldo inicial, activo | Usuario |
| PaymentMethod (propuesta) | Catálogo privado futuro; en Fase 3 se usa enum opcional | Usuario en ampliación futura |
| Area (implementada) | owner, nombre, activo, seed_code | Usuario |
| Category (implementada) | owner, area, nombre, tipo ingreso/gasto, activo | Usuario y área |
| Subcategory (implementada) | owner, category, nombre, activo | Usuario y categoría |
| Transaction (implementada) | owner, origen/destino, tipo, Decimal, clasificación, fecha efectiva, estado e idempotencia | Usuario, cuentas y clasificación |
| Budget (implementado) | owner, area XOR category, limit_amount NUMERIC(18,2), currency, year, month, timestamps, is_active | Usuario y clasificación |
| BudgetAlert | user, budget, umbral, triggered_at, read_at opcional | Usuario y presupuesto |

Importes positivos y tipo separado para ingresos/gastos. Precisión (18,2) inicial para PEN; antes de admitir monedas con otras fracciones se decidirá escala y validación por moneda. No almacenar cálculos en float. La API serializará importes como cadenas decimales.

Cada recurso privado lleva propietario explícito. Las claves foráneas por sí solas no garantizan que sus propietarios coincidan: serializers/servicios validarán pertenencia y consistencia de área/categoría/subcategoría/cuenta. Querysets se restringirán por usuario. No se aceptará asignar propietario mediante payload. Evaluar restricciones adicionales a nivel base de datos según implementación.

Restricciones previstas: importe > 0, start_date < end_date, nombres únicos por usuario dentro de su ámbito, moneda del movimiento igual a moneda de cuenta. Índices `(user_id, occurred_at)`, `(user_id, account_id, occurred_at)` y `(user_id, category_id, occurred_at)` según consultas reales. Usar PROTECT o archivo para referencias históricas; definir la política de eliminación antes de implementar.

Resumen financiero implementado: transacciones por propietario, moneda y periodo `[inicio, fin)`, límites locales convertidos a UTC. No hay tablas de totales. Saldo inicial y transferencias se implementaron con las reglas de docs/finanzas.md; pagos de tarjeta no crean otro gasto y los reportes excluyen TRANSFER/VOID de flujo neto.

AUTH_USER_MODEL=users.User se configuró antes de las primeras migraciones. Revisar el modelo financiero propuesto antes de implementar cada módulo; reportes/exportaciones no requieren tablas duplicadas de movimientos. Perfil REST modifica solo nombres y preferencias del usuario autenticado; nunca identidad, correo, contraseña ni permisos mediante PATCH.
# Extensión de Fase 4: Budget

Budget incorpora UUID, owner, area XOR category, limit_amount Decimal(18,2), currency PEN, year, month, created_at, updated_at e is_active. FK PROTECT y CHECK de alcance/importe/fecha; unicidad parcial por propietario y alcance/periodo/moneda, también para inactivos. Consumo y alertas son derivados del ledger POSTED, no columnas persistidas. No cambian modelos de usuario ni movimientos. Ver [analitica-presupuestos.md](analitica-presupuestos.md).

## Fase 5: AuditEvent

UUID, actor User PROTECT, operation, resource_type, resource_id UUID, occurred_at UTC, before/after JSON con allowlist, changed_fields y correlation_id. Índices actor/fecha y actor/recurso/identificador. Append-only desde aplicación y trigger PostgreSQL para UPDATE/DELETE. No FK a recurso financiero, así se conserva identidad genérica. No backfill, datos históricos ni secretos. Reportes no añaden tablas de totales o definiciones guardadas. Ver [reportes-auditoria.md](reportes-auditoria.md).

## Fase 6: RecurringRule y RecurringExecution

Regla: UUID, owner, plantilla financiera Decimal/PEN con FK PROTECT, frecuencia/intervalo, inicio/fin/cursor como DATE local, timezone fijada, modo y estado. Ejecución: UUID, rule PROTECT, scheduled_date, status, Transaction OneToOne PROTECT opcional, intento/ejecución UTC y código de error seguro. Unicidad rule/date y CHECK de estado/cursor, importes y forma; índices por propietario y vencimiento. No se duplican movimientos ni persisten saldos programados. Opciones de AuditEvent amplían pausa/reanudación/cancelación/ejecución/omisión sin cambiar eventos previos. Ver [recurrencias.md](recurrencias.md).
