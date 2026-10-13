# Analítica y presupuestos — Fase 4

## API y autorización

Todos los endpoints están bajo `/api/v1/`, requieren sesión y filtran exclusivamente por propietario. Las escrituras de presupuestos requieren CSRF mediante CSRFSafeSessionAuthentication. Las lecturas financieras y escrituras comparten owner_lock para un snapshot lógico consistente con las correcciones del ledger.

| Endpoint | Métodos | Contenido |
| --- | --- | --- |
| analytics/dashboard/ | GET | KPI, cuentas, evolución, distribuciones, comparación y alertas del mes actual |
| analytics/evolution/ | GET | Totales y serie agregada con días/semanas/meses vacíos |
| analytics/distribution/ | GET | Gastos por área y categoría |
| analytics/comparison/ | GET | Totales actuales y comparación equivalente |
| budgets/ | GET, POST | Lista paginada y creación |
| budgets/{uuid}/ | GET, PATCH, DELETE | Consulta, edición, desactivación |
| budgets/{uuid}/progress/ | GET | Consumo, disponible, porcentaje y alerta |

Analytics acepta `currency=PEN`, `granularity=daily|weekly|monthly`, `period=day|yesterday|week|previous_week|month|previous_month|year|custom`. Rango personalizado: start/end YYYY-MM-DD, ambos días incluidos en la selección; internamente `[inicio, fin)` con fin exclusivo al inicio del día siguiente. Semanas empiezan lunes. El helper compartido amplía también filtros de historial y resumen de Fase 3. El endpoint reports/summary/ conserva su respuesta y periodos calendario completos.

La analítica avanzada corta el fin al instante de consulta; rechaza periodos futuros que no hayan comenzado. Comparación anterior = intervalo inmediatamente anterior de igual duración **en hora local**, no necesariamente un mes calendario ni las mismas horas UTC cuando cambia el horario de verano. Por ejemplo, hoy de 00:00 a 12:00 se compara con ayer de 12:00 a hoy 00:00. Ambos rangos se devuelven y muestran explícitamente. Promedio diario = gasto / número de fechas locales abarcadas, incluido el día parcial actual; los días sin gastos cuentan. Rango máximo: diez años.

Variación = `(actual - anterior) / abs(anterior) * 100`, con Decimal y redondeo HALF_UP a dos decimales. Base cero y actual cero: 0.00 %, status both_zero. Base cero y actual distinto: percent null, status no_base; se muestra «Sin base porcentual anterior». Para flujo anterior negativo, mejorar un déficit produce variación positiva. Un aumento de gastos no se presenta como mejora financiera.

## Dinero y gráficos

Se agregan solo movimientos POSTED, de la moneda solicitada, en SQL. TRANSFER no es ingreso/gasto ni consume presupuestos. Un gasto en tarjeta sí consume; pagarla mediante transferencia no vuelve a contabilizar el gasto. VOID queda excluido. No se modifican movimientos ni se almacenan resúmenes duplicados.

Saldo de activos = suma firmada actual de cuentas no CREDIT, también inactivas; puede incluir sobregiros y no es una garantía bancaria de fondos disponibles. Deuda de tarjetas = suma de max(0, -saldo) en CREDIT. Patrimonio registrado = suma de todos los saldos firmados, incluyendo crédito y saldos a favor. No incluye bienes o deudas ajenos al registro. Flujo neto = ingresos menos gastos del periodo, independiente de saldos iniciales. Mayor categoría se desempata por nombre y UUID.

Importes exactos permanecen como cadenas decimales. Recharts recibe exclusivamente coordenadas enteras normalizadas por el backend (escala 1 000 000) para geometría; los importes no se convierten a Number. Ejes, tooltips y tablas muestran cadenas exactas formateadas con BigInt. Las posiciones y proporciones son aproximaciones gráficas: una diferencia extremadamente pequeña puede no verse. Distribuciones usan pesos enteros, mínimo uno para gastos positivos. Evolución rellena buckets vacíos con cero y calcula acumulados con Decimal. No se descargan transacciones individuales para los indicadores. Las vistas de analítica se cargan de forma diferida.

## Modelo Budget

UUID, owner PROTECT, area o category PROTECT (exactamente una), limit_amount NUMERIC(18,2) positivo, currency PEN, year 1900–9998, month 1–12, created_at, updated_at, is_active. Restricciones CHECK y dos índices únicos parciales por propietario/alcance/año/mes/moneda. Los presupuestos inactivos siguen siendo únicos: se editan/reactivan, no se crean duplicados.

Categoría debe ser de gasto, pertenecer al usuario y estar activa al seleccionar un nuevo alcance; su área también debe estar activa. Los alcances históricos inactivos se pueden conservar al ajustar límites. Presupuestos de área y categoría pueden coexistir y evalúan el mismo ledger por separado; no se suman sus consumos o límites como si fueran independientes.

Ejemplo POST:

```json
{"category":"UUID propio", "limit_amount":"500.00", "currency":"PEN", "year":2026, "month":10}
```

Progreso agrupa gastos por año/mes **en la zona actual del usuario** y alcance. Las listas usan como máximo dos consultas agrupadas del ledger, sin consulta por cada presupuesto. Consumo Decimal; disponible = límite - consumo, puede ser negativo. Porcentaje no se limita a 100; barra visual se limita. NORMAL <80 %, WARNING >=80 y <100 %, EXCEEDED >=100 %, INACTIVE para desactivados. La alerta usa el porcentaje sin redondear para evitar alertas prematuras. El dashboard muestra alertas de presupuestos activos del mes actual, incluso al consultar otros periodos.

Filtros de lista: year, month, active=true|false, area/category UUID, ordering=year|month|created_at|limit_amount (prefijo - descendente), page, page_size (25, máximo 100). DELETE cambia is_active y updated_at, nunca borra. Alertas son visuales calculadas al consultar; no hay notificaciones programadas ni correo.

## Limitaciones y siguiente fase

PEN y mensual exclusivamente. Cambiar zona del perfil reinterpreta las fechas y meses analíticos del historial sin modificar sus timestamps UTC. Sin conversión, presupuestos recurrentes automáticos, arrastre de sobrantes, recordatorios, exportación ni bitácora de versiones. owner_lock prioriza coherencia por usuario; no se ha realizado prueba de carga. Chromium se prueba en Linux y viewport móvil, no dispositivos físicos. SQLite no garantiza centavos en importes extremos: la prueba NUMERIC máxima es exclusiva de PostgreSQL.

Para la siguiente fase: reportes/exportaciones con autorización, recuperación de cuentas y verificación de correo, y auditoría de cambios financieros. Notificaciones y otras monedas necesitan políticas explícitas antes de implementarse.
