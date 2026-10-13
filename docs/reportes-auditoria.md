# Reportes personalizados y auditoría — Fase 5

## Contratos y filtros

Todos los endpoints requieren sesión Django y permisos privados; no existen enlaces públicos ni archivos persistidos por la API. Cookies HttpOnly y CSRF se conservan para escrituras. Respuestas y descargas tienen Cache-Control private,no-store. GET no modifica el ledger ni crea eventos financieros.

| Endpoint bajo /api/v1/ | Métodos | Resultado |
| --- | --- | --- |
| reports/ | GET | Alias de vista previa |
| reports/preview/ | GET | Resumen y detalle paginado |
| reports/export/xlsx/ | GET | Workbook con cinco hojas |
| reports/export/csv/ | GET | Movimientos UTF-8 BOM |
| reports/export/pdf/ | GET | Informe A4 apaisado multipágina |
| audit/events/ | GET | Eventos propios paginados |
| audit/events/{uuid}/ | GET | Un evento propio, 404 para ajenos |

Se conserva reports/summary/ de Fase 3. reports no persiste definiciones/plantillas: «personalizado» significa filtros combinables, no reportes guardados o programados.

Filtros: period=day/yesterday/week/previous_week/month/previous_month/year/custom; start/end YYYY-MM-DD para custom; account, area, category, subcategory UUID propios; kind=INCOME/EXPENSE/TRANSFER; status=POSTED/VOID/ALL; payment_method=CASH/CARD/YAPE/PLIN/BANK/OTHER/UNSPECIFIED; currency=PEN; granularity=daily/weekly/monthly. Filtros omitidos no restringen salvo status=POSTED y period=month. UNSPECIFIED selecciona método vacío. Identificadores ajenos o inexistentes producen el mismo 400. Filtros incompatibles entre sí producen detalle vacío. Parámetros desconocidos se rechazan.

Detalle: ordering=occurred_at/created_at/amount con - descendente, page, page_size (25 por defecto, máximo 100). Los enlaces next/previous siguen requiriendo sesión; no contienen datos ni tokens. Descargar exporta todos los movimientos filtrados, no solo la página visible. Los botones usan los últimos filtros aplicados a la vista previa.

Respuesta preview: currency, timezone, start, end_exclusive, generated_at, filters, income, expense, net_flow, areas, categories, evolution y movements={count,next,previous,results}. Los importes son cadenas decimales. La estructura de movimientos reutiliza TransactionSerializer. Cuenta filtra origen o destino, también transferencias.

Periodos calendario completos en zona del usuario, límites `[inicio, fin)` traducidos por ORM a UTC, semanas desde lunes. A diferencia de la analítica avanzada, no se hacen comparaciones ni se recorta el fin calendario al instante de consulta. No se suman monedas diferentes. Agregaciones reutilizan totals/distribution/evolution; filtros de movimientos son compartidos con el historial. Grupos sin actividad se completan con cero.

Los indicadores solo consideran POSTED, aunque VOID aparezca en detalle. Transferencias nunca son ingresos/gastos. Compras en tarjetas sí son gastos; el pago mediante transferencia no vuelve a contabilizarse. Exportar status=VOID produce indicadores cero y conserva los importes originales en el detalle para inspección.

## Límites y abuso

Configuración mediante variables positivas:

| Variable | Predeterminado |
| --- | --- |
| REPORT_MAX_DAYS | 366 días locales |
| REPORT_EXPORT_ROWS | 5000 para XLSX/CSV |
| REPORT_PDF_ROWS | 500 para PDF |
| REPORT_RATE_SECONDS | 60 segundos |
| REPORT_PREVIEW_LIMIT | 30 peticiones por usuario/ventana |
| REPORT_EXPORT_LIMIT | 10 descargas por usuario/ventana, compartidas entre formatos |

Un año bisiesto completo es válido. Rangos o volúmenes excedidos: 400 con indicación para reducir filtros. Contadores atómicos en AuthRateLimit, identidades HMAC, compartidos por workers/PostgreSQL. Los intentos inválidos autenticados también cuentan. 429 con Retry-After; limpieza mediante cleanup_auth_limits. No se utiliza IP suministrada por cabeceras. Son exportaciones síncronas con límites; no sustituyen controles de infraestructura ni pruebas de carga.

## Archivos y precisión

Los datos se materializan bajo owner_lock y transaction.atomic para un snapshot lógico consistente; la serialización del documento ocurre después de liberar el bloqueo. No se consulta una relación por cada movimiento: select_related carga todas las FK necesarias. Una nueva escritura posterior puede cambiar los datos de una descarga futura; preview y descarga son consultas separadas, no una instantánea persistida.

CSV: Content-Type text/csv; charset=utf-8, BOM, cabeceras españolas y fechas ISO con offset del usuario. Importes exactos como texto decimal. Todos los textos se protegen frente a =,+,-,@ incluso tras espacios iniciales; tabuladores y saltos iniciales también se prefijan con apóstrofo. Se eliminan controles inválidos. El prefijo de seguridad no modifica el ledger.

XLSX: openpyxl, cinco hojas (Resumen financiero, Movimientos, Gastos por área, Gastos por categoría, Evolución temporal). Encabezados verdes, panel inmovilizado, autofiltros, anchos definidos, texto envuelto, periodo y zona visibles. No hay fórmulas, hipervínculos ni contenido externo: todos los valores se fuerzan a texto literal, aunque comiencen con '='. Fechas ISO conservan offset. **Importes como texto decimal exacto con formato monetario textual `"S/ "@`**, alineados a la derecha. Excel no garantiza los 18 dígitos de NUMERIC; se prioriza exactitud sobre sumas nativas de celdas. Para cálculos posteriores usar Decimal o conversión explícita con política de precisión, nunca convertir silenciosamente la columna a float.

PDF: ReportLab Platypus/LongTable, encabezados repetidos, numeración y pie privado, tablas de indicadores/áreas/categorías/evolución/detalle. Cada movimiento usa dos filas mantenidas juntas para no separar importe, identidad y descripción al paginar. Texto de usuario escapado antes de Paragraph; importes son cadenas, no se realizan cálculos financieros con float ni se generan gráficos aproximados. Datos vacíos reciben mensajes explícitos. Fuente Helvetica: español y caracteres latinos soportados; alfabetos o símbolos fuera del repertorio de la fuente requieren una ampliación de fuentes antes de garantizar su presentación.

Content-Disposition attachment con nombre generado por servidor sin texto del usuario; Content-Type correcto y nosniff. El cliente usa fetch con credentials:include y Blob temporal, revocado tras descargar. No almacena archivos, tokens ni datos financieros en localStorage. Los archivos descargados en el equipo del usuario requieren su protección habitual.

## Auditoría

AuditEvent: UUID, actor FK PROTECT, operation CREATE/UPDATE/VOID/DEACTIVATE, resource_type (label de modelo), resource_id UUID, occurred_at UTC, before/after JSON, changed_fields y correlation_id UUID. Índices por actor/fecha y actor/recurso/identificador. API de solo lectura; respuestas de eventos serializan fechas en UTC y React las presenta en la zona del usuario.

Campos con valores anteriores/posteriores permitidos:

| Recurso | Valores auditados |
| --- | --- |
| Cuenta | name, kind, currency, initial_balance, is_active |
| Área | name, is_active |
| Categoría | name, area_id, kind, is_active |
| Subcategoría | name, category_id, is_active |
| Movimiento | cuentas, kind, amount, currency, clasificación, occurred_at, payment_method, status |
| Presupuesto | area/category, limit_amount, currency, year/month, is_active |

Descripción, referencia e institución: solo nombre de campo en changed_fields si se editan; sus contenidos se omiten. No se auditan usuarios, credenciales, cookies, tokens, IP, cabeceras ni secretos. Los nombres financieros se conservan para explicar sus cambios; evitar introducir información sensible en ellos.

owner_lock establece un ContextVar de actor/correlación dentro de atomic. Señales pre_save/post_save registran antes/después para modelos permitidos. El evento se inserta **en la misma transacción**, no on_commit: un error de auditoría revierte la escritura financiera y viceversa. Sin cambios significativos, PATCH y DELETE repetidos no crean eventos nuevos. El catálogo inicial seed_code se excluye de CREATE; cambios posteriores sí se auditan.

Transferencia creada: un evento CREATE del movimiento TRANSFER, correlación = Idempotency-Key. El reintento retorna el movimiento existente sin save ni evento. Conflictos no crean eventos. Resto de operaciones usan UUID de correlación por bloque propietario.

Append-only: Model/QuerySet rechazan modificaciones, eliminaciones y actualizaciones masivas. PostgreSQL agrega un trigger BEFORE UPDATE OR DELETE. No hay Admin ni endpoints de escritura para eventos. Administradores de base pueden alterar/deshabilitar protecciones, y escrituras externas SQL/bulk o fuera del servicio transaccional no se auditan automáticamente: no es almacenamiento forense inalterable ni un WAL. Todas las escrituras financieras de la aplicación deben seguir usando owner_lock y save, sin bulk/update directo.

**La auditoría comienza al activar la Fase 5. No reconstruye versiones ni responsables históricos inexistentes.** Movimientos anteriores pueden mostrar historial vacío; su primera corrección queda registrada con estado previo disponible. Migraciones solo crean la tabla/índices y la protección; no cambian usuarios, cuentas, movimientos ni presupuestos. No hay endpoints para restaurar versiones.

Filtros audit: resource_type, resource_id, operation, page/page_size. Solo eventos del actor autenticado. La página /auditoria y el detalle /movimientos/{uuid} presentan campos cambiados; valores sensibles omitidos aparecen como no disponibles.

## Verificación reproducible

Suites: añadir apps.reports y apps.audit a los siete módulos de README, con config.settings_test_postgres y config.settings_test. Ejecutar también reports_flow.py y los tres flujos anteriores. Todos los E2E conservan usuarios sintéticos; no se elimina historial.

QA PDF/XLSX/CSV sin consultar base:

```powershell
docker run --rm --mount type=bind,source="${PWD}/backend",target=/app --mount type=bind,source="${PWD}/tests/browser/artifacts",target=/artifacts control-gastos-app-backend python scripts/report_artifact_qa.py /artifacts
docker run --rm --mount type=bind,source="${PWD}/tests/browser",target=/tests python:3.12-slim sh -c 'pip install pymupdf pypdf && python /tests/render_report_qa.py /tests/artifacts'
```

Capturas y archivos bajo artifacts/ ignorados por Git. Renderiza todas las páginas; comprueba texto final, total, cajas dentro de página y parejas de filas por movimiento. Revisar PNG de portada, evolución, páginas intermedias y cierre. Versiones de runtime fijadas en requirements.lock.txt desde un contenedor limpio con pip check; las herramientas de render son auxiliares de QA, no dependencias del servidor.

Límites: exportación síncrona, mensual/PEN en presupuestos existentes, sin plantillas guardadas, firma digital, cadena criptográfica, retención/legal hold, notificaciones, trabajos en cola ni pruebas de carga. Siguiente fase sugerida: definir retención y accesos administrativos de auditoría, exportaciones asíncronas para grandes historiales y recuperación/verificación de cuentas.
