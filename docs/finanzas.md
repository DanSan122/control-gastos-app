# Gestión financiera — Fase 3

## Decisiones de negocio

ControlGastos registra operaciones realizadas por el usuario. No se conecta a bancos ni ejecuta pagos externos. Todo el dominio financiero de esta fase utiliza PEN con precisión de dos decimales, Decimal en Python, NUMERIC(18,2) en PostgreSQL y cadenas decimales en JSON. Los números JSON, incluidos enteros, se rechazan para importes. La interfaz formatea con BigInt y cadenas; no convierte importes a Number.

### Cuentas, activos y crédito

Account contiene UUID, owner, name, kind (CASH/BANK/WALLET/CREDIT/OTHER), institution opcional, currency, initial_balance, created_at e is_active. La institución es texto: admite bancos peruanos, Yape y Plin sin catálogos restrictivos de instituciones.

El saldo inicial representa el estado anterior a todo el historial registrado. Es independiente de la fecha técnica de creación de la cuenta. Ingresos aumentan saldo; gastos lo reducen; transferencias restan en origen y suman en destino. Los saldos se agregan desde movimientos POSTED efectivos hasta el momento de consulta, sin columna de saldo acumulado que pueda desincronizarse. Se permiten negativos para registrar sobregiros o historiales incompletos; esta aplicación no autoriza operaciones bancarias por disponibilidad de fondos.

CREDIT es una cuenta de pasivo: la deuda inicial se registra negativa, nunca como límite de crédito positivo. Deuda pendiente = max(0, -saldo). Una compra con tarjeta es EXPENSE sobre la tarjeta y aumenta su deuda. El pago desde un banco hacia la tarjeta es TRANSFER y reduce la deuda sin crear otro gasto. Ejemplo: saldo tarjeta -100, compra 30 → -130; pago 100 desde banco → -30. El gasto del periodo es 30. Un saldo positivo de tarjeta representa un sobrepago/saldo a favor y participa en el patrimonio firmado; nunca es un límite disponible.

Yape/Plin se pueden seleccionar como payment_method de un movimiento contra la cuenta bancaria vinculada. Si el usuario tiene una billetera con saldo realmente independiente, puede crear WALLET. No se crean cuentas Yape/Plin automáticamente ni se duplican saldos bancarios.

Saldo inicial, moneda y tipo no se cambian después del primer movimiento, incluso si luego se anula. Nombre, institución y estado siguen editables. DELETE desactiva la cuenta; su saldo e historial permanecen, y los reportes incluyen cuentas inactivas.

### Clasificaciones

Area → Category → Subcategory, cada entidad con UUID, propietario, nombre, estado y fecha de creación. Category distingue INCOME/EXPENSE. Nombres únicos sin distinguir mayúsculas por propietario y ámbito. Relaciones PROTECT y validación de propietario en API.

Las nueve áreas iniciales son Alimentación, Transporte, Vivienda, Educación, Salud, Entretenimiento, Finanzas, Compras personales y Otros. Cada una incluye General (EXPENSE) y Otros como subcategoría; Finanzas incluye Sueldo y Otros ingresos (INCOME). La señal de usuario nuevo inicializa el catálogo. `python manage.py seed_catalog` inicializa los usuarios existentes y se puede repetir. seed_code estable por usuario evita duplicaciones y conserva renombrados/desactivaciones.

DELETE desactiva, nunca elimina. Se exige toda la jerarquía activa para nuevos movimientos. Correcciones de un movimiento existente pueden conservar sus referencias desactivadas, pero no adoptar otras desactivadas. Categorías/subcategorías con movimientos no pueden cambiar su padre; una categoría con movimientos no cambia INCOME/EXPENSE. Renombrar actualiza las etiquetas mostradas en el historial, conservando los IDs.

### Movimientos y transferencias

Transaction contiene UUID, owner, account, destination_account opcional, kind, amount, currency, area/category/subcategory cuando corresponda, description, occurred_at, created_at, updated_at, payment_method opcional, reference opcional y status POSTED/VOID. Índices por propietario/fecha, cuenta/fecha y categoría/fecha.

INCOME/EXPENSE requieren área y categoría de tipo correcto; subcategoría es opcional. Se validan todas las relaciones contra el propietario y la jerarquía. Los importes deben ser positivos y tener como máximo dos decimales. occurred_at debe incluir offset/Z en ISO 8601; no se admiten fechas inválidas, ingenuas ni futuras (no hay movimientos programados en esta fase). Django persiste instantes UTC; filtros y presentación utilizan la zona del usuario.

TRANSFER utiliza un único registro con origen/destino propios, distintos y de igual moneda. No admite clasificación de ingreso/gasto. Tiene dos efectos de saldo y ninguno en ingresos/gastos. Todos los cambios financieros se realizan dentro de una transacción y con bloqueo de la fila del propietario, incluyendo cambios de cuentas y clasificaciones. Reportes/saldos toman el mismo bloqueo para una lectura coherente. El bloqueo serializa operaciones del mismo usuario; es una decisión simple para finanzas personales, no una arquitectura de pagos masivos.

Transferencias nuevas solo mediante POST transfers/ con `Idempotency-Key` UUID obligatorio. Se conserva una huella SHA-256 del JSON original, ordenando sus claves. Misma clave/propietario y mismo contenido devuelve 200 con el movimiento existente; primer envío devuelve 201; clave reutilizada con otro contenido devuelve 409. El contenido debe conservar exactamente los valores originales (por ejemplo, "10.00" y "10" no son el mismo payload). Restricción única `(owner, idempotency_key)` y bloqueo evitan carreras. Una clave de otro usuario no permite consultar su transferencia. Reintentar una transferencia anulada devuelve su registro VOID y no vuelve a ejecutarla.

El formulario conserva clave y payload en memoria durante un reintento de red y bloquea la modificación del borrador incierto. Un 400 permite corregirlo porque no se guardó el movimiento. Tras cerrar/recargar esa página, revisar el historial antes de crear otra operación; no se persisten borradores financieros en el navegador. La idempotencia de esta fase se exige para transferencias, no para los POST de ingresos/gastos.

PATCH permite corregir importe, cuentas, clasificación, fecha y textos de un movimiento vigente, preservando su tipo y recalculando saldos/reportes desde los registros. No hay bitácora de versiones anteriores de esas correcciones. DELETE cambia a VOID, conserva el registro y revierte sus efectos por exclusión de agregaciones. VOID es inmutable y no se reactiva. La UI confirma transferencias, correcciones financieras, desactivaciones y anulaciones.

## API privada bajo /api/v1/

Todos los endpoints financieros requieren sesión; todas las escrituras exigen CSRF, reutilizando el cliente/autenticación de Fase 2. owner, IDs técnicos, timestamps técnicos, status y datos de idempotencia no son editables mediante payload ordinario.

| Recurso | Colección | Detalle | Operación adicional |
| --- | --- | --- | --- |
| Cuentas | GET/POST accounts/ | GET/PATCH/DELETE accounts/{uuid}/ | GET accounts/{uuid}/balance/ |
| Áreas | GET/POST areas/ | GET/PATCH/DELETE areas/{uuid}/ | — |
| Categorías | GET/POST categories/ | GET/PATCH/DELETE categories/{uuid}/ | — |
| Subcategorías | GET/POST subcategories/ | GET/PATCH/DELETE subcategories/{uuid}/ | — |
| Movimientos | GET/POST transactions/ | GET/PATCH/DELETE transactions/{uuid}/ | POST transfers/ |
| Resumen | GET reports/summary/ | — | — |

Ejemplo de gasto:
```json
{
  "account": "UUID_DE_CUENTA_PROPIA",
  "kind": "EXPENSE",
  "amount": "25.50",
  "currency": "PEN",
  "area": "UUID_DE_AREA_PROPIA",
  "category": "UUID_DE_CATEGORIA_DE_GASTO",
  "subcategory": null,
  "occurred_at": "2026-10-01T12:30:00-05:00",
  "description": "Almuerzo",
  "payment_method": "YAPE",
  "reference": "operacion-opcional"
}
```
Ejemplo de transferencia (con cabecera Idempotency-Key y CSRF):
```json
{
  "account": "UUID_ORIGEN_PROPIO",
  "destination_account": "UUID_DESTINO_PROPIO",
  "amount": "100.00",
  "currency": "PEN",
  "occurred_at": "2026-10-01T12:30:00-05:00",
  "description": "Pago de tarjeta"
}
```
Métodos de pago: CASH, CARD, YAPE, PLIN, BANK, OTHER o cadena vacía. Account.kind: CASH, BANK, WALLET, CREDIT, OTHER. PATCH usa los mismos nombres de campos editables; status cambia solo por DELETE.

Las listas responden `{count, next, previous, results}`: page y page_size, 25 por defecto y máximo 100. Orden estable con UUID como desempate. Cuentas/clasificaciones: active=true/false, search, ordering=name/created_at (o descendente con -), kind donde existe, categorías por area y subcategorías por category. Movimientos: account (incluye origen/destino), area, category, subcategory, kind, status, search (descripción/referencia), ordering=occurred_at/created_at/amount con prefijo - opcional. Por defecto las listas incluyen activos/inactivos o POSTED/VOID; la UI de historial empieza filtrando POSTED.

Periodos para movimientos/resumen: period=day/week/month/custom. Día, semana (lunes–domingo) y mes corresponden al presente en la zona del usuario. Custom requiere start/end como YYYY-MM-DD, extremos locales inclusivos, convertidos a `[inicio, siguiente día de end)`; rango máximo 3660 días. Movimientos sin parámetros de periodo muestran todo el historial; resumen usa month por defecto. UUIDs/filtros inválidos devuelven 400; recursos ajenos devuelven 404. DELETE devuelve 204.

## Reportes y significado de los totales

- **Saldo de cuenta:** saldo inicial + ingresos − gastos − transferencias salientes + entrantes, excluyendo VOID y movimientos aún no efectivos.
- **Flujo neto del periodo:** ingresos − gastos de ese periodo. No incluye saldos iniciales ni transferencias.
- **Patrimonio registrado actual:** suma de todos los saldos firmados de cuentas propias en PEN, incluidas inactivas. Los saldos negativos de crédito restan y los saldos a favor suman. No incorpora bienes/deudas no registrados como cuentas.
- **Patrimonio al cierre del periodo:** mismos saldos iniciales más movimientos previos al límite exclusivo de cierre. El saldo inicial se interpreta anterior a todo el historial registrado, no como una medición de patrimonio externa en una fecha arbitraria.

Summary devuelve income, expense, net_flow, expenses_by_area/category, evolution.daily/weekly/monthly, accounts con balance/debt, asset_balances (saldos de cuentas no CREDIT), credit_debt, net_worth y net_worth_at_period_end. Todos los importes son cadenas. La evolución incluye grupos con actividad; semanas/meses extremos pueden estar recortados por el rango seleccionado. No duplica transacciones ni mantiene tablas de totales.

## Verificación y límites

Fase 4 agrega analítica avanzada, gráficos y presupuestos mensuales sin cambiar estas reglas de cuentas, transferencias y crédito. Contrato adicional en [analitica-presupuestos.md](analitica-presupuestos.md); la lista siguiente conserva el alcance histórico de Fase 3.

Tests de dominio/API en apps.transactions, junto con los tests existentes de core/users; suite PostgreSQL necesaria para concurrencia y restricciones reales. tests/browser/finance_flow.py prueba una pérdida de respuesta posterior a guardar y el reintento de la misma transferencia, además de cuentas, clasificación, ingresos/gastos, deuda, edición/anulación, reportes y móvil. Datos sintéticos conservados en una cuenta separada.

No hay conversión monetaria, extractos bancarios automáticos, conciliación, auditoría de versiones, recurrencia/programación, presupuestos ni exportaciones en esta fase. El esquema mantiene moneda explícita para futuras ampliaciones, que deberán definir conversión y precisión antes de admitir monedas distintas a PEN.
