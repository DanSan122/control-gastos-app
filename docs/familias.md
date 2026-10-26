# Espacios personales y familiares — Fase 7

## Arquitectura

Se amplían los modelos financieros existentes; no se crea otro motor contable. Account, Area, Category, Subcategory, Transaction y Budget tienen FK opcional `family` con PROTECT. `family=NULL` identifica PERSONAL y requiere el owner actual. FAMILY identifica exclusivamente a la familia; owner conserva al autor/creador y no determina el acceso. No se permite modificar owner/family mediante payload ni convertir recursos personales en familiares.

`apps.core.scope` centraliza el filtro y la zona horaria. El contexto es local a cada petición (ContextVar), establecido únicamente por las rutas familiares autenticadas, nunca mediante un encabezado arbitrario o selector del cliente. Sin contexto, todas las consultas financieras exigen owner y family NULL. Relaciones, unicidad, balances, presupuestos, agregaciones, reportes y auditoría respetan el mismo ámbito. El catálogo inicial y las recurrencias son exclusivamente personales.

Las rutas familiares reutilizan los viewsets, serializers y servicios actuales. `family_finance_view` toma `locked_family`, comprueba sesión/membresía/rol, establece el ámbito y materializa la respuesta antes de liberarlo. Cada ruta familiar, incluso las lecturas, bloquea la fila Family dentro de transaction.atomic. Cambiar membresías usa el mismo bloqueo. Una escritura esperando detrás de una revocación vuelve a comprobar el acceso y falla; una operación que ya tenía el bloqueo termina antes de que la revocación se confirme. El bloqueo de usuario se conserva para finanzas personales. No se toman ambos bloqueos en orden inverso.

`create_movement` sigue siendo la única entrada de creación financiera, bajo owner_lock; en ámbito familiar ese bloqueo resuelve a la familia. Dinero NUMERIC/Decimal, JSON string, dos decimales y solo PEN. No se mezclan monedas ni ámbitos. Un saldo inicial de tarjeta es deuda negativa; pagarla es una transferencia, sin doble gasto. DELETE conserva historial: desactiva o anula.

## Modelos nuevos y atribución

- Family: UUID, nombre, descripción opcional, created_by PROTECT, PEN, zona IANA, ACTIVE/ARCHIVED y timestamps. Creador obtiene membresía ADMIN en la misma transacción. Varias familias por usuario.
- FamilyMembership: UUID, familia, usuario, rol ADMIN/MEMBER, ACTIVE/REMOVED, joined_at, removed_at. Unicidad familia/usuario incluso retirados; al aceptar una nueva invitación se reactiva el mismo registro como MEMBER. Una familia conserva al menos un administrador activo mediante validación bajo bloqueo. No se eliminan membresías físicamente.
- FamilyInvitation: UUID, familia, email normalizado, usuario destinatario registrado, invited_by, PENDING/ACCEPTED/REJECTED/EXPIRED/REVOKED, expiración, creación y respuesta. Unicidad parcial familia/email para PENDING. Las invitaciones caducadas se presentan como EXPIRED aun sin worker; las acciones de respuesta/revocación y la nueva invitación materializan la expiración bajo bloqueo.
- AuditEvent añade family opcional sin modificar eventos anteriores. Finanzas familiares y operaciones de familia/membresía/invitación registran al actor real. No se copian email de invitación, descripción, referencia, institución, contraseñas ni cookies a eventos.

Transaction.owner es «registrado por», expuesto como registered_by y registered_by_name; no significa «pagado por». No hay campo pagado_por ni cambios automáticos en cuentas personales. Autoría también aparece en historial, dashboard, reportes y exportaciones; las modificaciones se atribuyen mediante auditoría.

## Matriz de permisos

| Operación familiar | ADMIN | MEMBER | Ajeno/retirado |
| --- | --- | --- | --- |
| Consultar familia, miembros y finanzas | Sí | Sí | 404 |
| Editar perfil, archivar/reactivar familia | Sí | No | 404 |
| Invitar, listar/revocar invitaciones enviadas | Sí | No | 404 |
| Cambiar roles/retirar otros integrantes | Sí; protege último administrador | No | 404 |
| Salir | Sí, salvo último administrador | Sí | 404 |
| Administrar cuentas/clasificaciones/presupuestos | Sí | Solo lectura | 404 |
| Crear ingresos, gastos y transferencias internas | Sí | Sí | 404 |
| Editar/anular movimientos | Cualquiera vigente | Solo registrados por él | 404 |
| Dashboard, reportes/exportaciones y auditoría | Sí | Sí | 404 |
| Datos personales ajenos | No | No | No |

ARCHIVED permite consultas pero bloquea escrituras financieras y gestión de membresías/invitaciones. Un administrador puede reactivarla desde configuración. No hay eliminación física de familia. Estado VOID es inmutable; no existe restauración de movimientos anulados. La UI deshabilita gestiones de ADMIN para MEMBER, pero el servidor siempre vuelve a validarlas.

## API privada

Prefijo `/api/v1/`. Sesiones HttpOnly y CSRFSafeSessionAuthentication; CSRF obligatorio en escrituras. Listas paginadas count/next/previous/results; page_size máximo 100. UUIDs en rutas, errores seguros 404 para ámbitos ajenos y 403 para operaciones no permitidas a miembros conocidos.

| Recurso | Métodos/rutas |
| --- | --- |
| Familias | GET/POST families/; GET/PATCH families/{uuid}/ |
| Miembros | GET families/{uuid}/members/; PATCH/DELETE members/{membership_uuid}/; POST families/{uuid}/leave/ |
| Invitaciones enviadas | GET/POST families/{uuid}/invitations/; POST invitations/{invitation_uuid}/revoke/ |
| Invitaciones recibidas | GET families/invitations/mine/; POST families/invitations/{uuid}/accept/ o reject/ |
| Cuentas | GET/POST families/{uuid}/accounts/; GET/PATCH/DELETE accounts/{id}/; GET accounts/{id}/balance/ |
| Clasificaciones | GET/POST families/{uuid}/areas/, categories/, subcategories/; GET/PATCH/DELETE recurso/{id}/ |
| Movimientos | GET/POST families/{uuid}/transactions/; GET/PATCH/DELETE transactions/{id}/; POST transfers/ |
| Presupuestos | GET/POST families/{uuid}/budgets/; GET/PATCH/DELETE budgets/{id}/; GET budgets/{id}/progress/ |
| Analítica | GET families/{uuid}/dashboard/, analytics/ y analytics/{dashboard,evolution,distribution,comparison}/ |
| Reportes | GET families/{uuid}/reports/summary/, reports/preview/, reports/export/{xlsx,csv,pdf}/ |
| Auditoría | GET families/{uuid}/audit/events/ |

Las rutas abreviadas de la tabla se resuelven dentro de la misma familia. Contratos financieros y filtros de fases anteriores se conservan. Historial/reportes aceptan registered_by UUID y categorías/cuentas; este filtro siempre restringe el queryset ya autorizado y no concede acceso. Las transferencias exigen Idempotency-Key UUID, único por familia, independiente del autor del reintento; la misma clave/payload devuelve el movimiento original. No reutilizar claves para operaciones diferentes.

POST invitations/ acepta solo email. Responde siempre 202 con mensaje genérico para desconocidos, miembros actuales, duplicados o invitación creada. No envía email ni crea enlaces públicos. Solo usuarios activos ya registrados reciben invitaciones, válidas siete días; solo el destinatario puede aceptar/rechazar. Un administrador puede consultar el estado de invitaciones emitidas; el mensaje genérico no debe interpretarse como garantía frente a inferencias a partir de su historial autorizado. Escrituras administrativas familiares limitadas a 30 por usuario/hora con contadores persistentes y atómicos; reportes conservan sus límites existentes.

PATCH members/{id}/ acepta exclusivamente role. leave, accept, reject y revoke no admiten campos adicionales. No hay recurrencias familiares ni endpoint que permita crear una regla personal con cuentas familiares.

La lista administrativa muestra invited_email, el correo introducido en la invitación, para identificar correctamente qué invitación revocar. Solo los administradores de esa familia y el propio destinatario (en su bandeja) pueden consultarlo; no aparece en auditoría ni en la lista general de integrantes. La reactivación conserva el UUID y joined_at originales de la membresía.

## Frontend

Selector visible tras login: Mi espacio personal, Familia: nombre, Crear familia. Rutas /familias, /familias/nueva, /familias/invitaciones; por familia: dashboard, integrantes, cuentas, clasificaciones, movimientos, movimientos/nuevo, gastos/nuevo, ingresos/nuevo, transferir, presupuestos, reportes, auditoria, configuracion y detalle movimientos/{id}. La barra de navegación familiar mantiene el UUID en los enlaces.

FinancialScope inyecta un cliente HTTP por ámbito y enlaces locales; no hay variable global mutable de familia. Los componentes se desmontan al cambiar ruta/espacio; cancelan peticiones y descartan filtros/borradores en memoria. PersonalScope protege también la salida desde formularios personales. FamilyScope carga membresía antes de montar datos financieros. No hay tokens ni datos financieros en localStorage. Las denegaciones familiares se muestran sin cerrar la sesión personal. El panel familiar no muestra las recurrencias personales.

Las gráficas reutilizan Recharts con coordenadas normalizadas en backend e importes exactos como string. Dashboard incluye saldos exclusivos familiares, ingresos/gastos/flujo, evolución, distribución, alertas presupuestarias y diez movimientos recientes. Saldo es inicial más ledger; flujo neto es ingresos menos gastos del periodo; patrimonio familiar registrado suma saldos firmados familiares, nunca cuentas personales de integrantes.

## Migración y conservación

Migraciones incrementales generadas por Django. Añaden tablas, FK nullable, restricciones e índices por familia; sustituyen unicidades de owner por variantes parciales personales y familiares. No contienen traslado de datos, UPDATE de importes, eliminación de filas ni regeneración de UUID. La protección append-only de audit/0002 se conserva.

`python scripts/verify_family_migration.py before` calcula conteos y SHA-256 de todos los campos históricos (excluyendo el nuevo family). `after` exige las mismas huellas y que todos los registros anteriores mantengan family NULL. Guarda únicamente hashes/conteos bajo backend/tmp ignorado; no exporta contenidos ni secretos. Ejecutar con servicios de escritura y worker detenidos, antes de QA que cree nuevos datos.

Ver resultados reales y nombres de migraciones en [verificacion.md](verificacion.md). Aplicar migraciones antes de reactivar backend/worker. No se configura producción ni se elimina el volumen.

## Recurrencias y aportes futuros

RecurringRule/Execution siguen siendo personales. Validación de relaciones exige cuentas/clasificaciones personales y el worker conserva usuario, zona fijada, bloqueo, UUIDv5 e idempotencia. Recurrencias familiares requieren diseño explícito de actor automático, permisos vigentes, revocación y pruebas antes de activarse.

No se implementan aportes entre espacios. Propuesta posterior: entidad Contribution con origen personal, destino familiar, autorización de ambas partes, importe/currency y clave idempotente; dos asientos internos enlazados y atómicos bajo orden global de bloqueos de ambos espacios, únicos por contribución. Los asientos cambiarían los saldos de origen/destino y se excluirían de ingresos/gastos ordinarios para no distorsionar flujo ni duplicar gastos. Es necesario definir devolución, anulación coordinada, revocación y privacidad de contrapartes antes de implementarlo. «Gastos registrados por un integrante» no son aportes monetarios.

## Aprovisionamiento y límites

No se altera el registro actual: las cuentas de desarrollo y los E2E lo usan. Para cerrar el acceso público se propone una invitación global distinta de la membresía familiar, emitida por un operador autorizado, de un solo uso y duración limitada; permitiría crear usuario personal sin conceder lectura de otros espacios. Antes de cambiar auth/register/ se requiere acordar recuperación, primer operador y migración de los flujos existentes. No se crean superadministradores con acceso a finanzas personales.

PEN, grupos pequeños, sin envíos de correo, enlaces públicos, conciliación bancaria, pagos externos, aportes cruzados o recurrencias familiares. El bloqueo familiar prioriza consistencia y no se ha medido carga masiva. Exportaciones se generan en memoria bajo el bloqueo familiar para mantener autorización vigente; pueden retrasar otras operaciones hasta sus límites de volumen actuales. No hay CI nuevo ni despliegue de producción en esta tarea.

## Pruebas y recorrido de tres usuarios

Suite apps.families junto con las ocho apps anteriores: familias, permisos, invitaciones, privacidad, exactitud, transferencias, presupuesto/reportes/auditoría, CSRF, rollback y concurrencia PostgreSQL. SQLite omite justificadamente casos exclusivos de PostgreSQL. Los tests anteriores permanecen.

`tests/browser/families_flow.py` crea tres cuentas sintéticas sin imprimir contraseñas: A crea familia e invita a B; B acepta y registra gasto; ambos lo consultan, se verifican gastos personales separados, C recibe rechazo; A retira a B, que pierde acceso; se conserva historial y se prueba móvil/exportación. El flujo no borra sus datos. Ejecutar también auth_flow, finance_flow, analytics_flow, reports_flow y recurring_flow con el worker personal activo. Comandos en README y resultados, incluidos fallos encontrados, en docs/verificacion.md.
