# Requisitos funcionales

## Fase 1: alcance implementado
- Estructura separada de frontend y backend.
- Configuración PostgreSQL mediante Compose y variables de entorno.
- Endpoint GET público de salud; la pantalla inicial de conectividad fue sustituida por las pantallas de Fase 2.
- Configuración base de sesiones, CORS y CSRF.
- Pruebas de infraestructura HTTP y documentación de instalación/arquitectura.

## Fase 2: alcance implementado
- Usuario personalizado UUID con correo normalizado/único, nombres, fecha de registro, estado y preferencias America/Lima/PEN.
- Registro, login/logout, consulta de sesión, perfil propio y cambio de contraseña mediante sesiones Django.
- Protección CSRF incluso anónima; validación de contraseñas y límites atómicos de intentos.
- Pantallas de registro/login/dashboard vacío/perfil/seguridad/404, rutas privadas y persistencia al recargar.
- Preferencias de moneda/zona horaria, sin operaciones ni cálculos financieros.
- Compatibilidad con Admin y createsuperuser; sin administradores predeterminados.
- Tests SQLite/PostgreSQL y flujo Chromium de escritorio/móvil.

## Fase 3: alcance implementado
- CRUD lógico de cuentas propias de activos/crédito, moneda inicial PEN y saldos derivados.
- Jerarquía de área/categoría/subcategoría privada, tipo ingreso/gasto y catálogo inicial idempotente.
- Ingresos/gastos/transferencias exactos, validación de propiedad y jerarquía, edición/anulación conservando registros.
- Transferencias atómicas e idempotentes; compras de crédito y pagos de deuda sin doble contabilización.
- Métodos de pago opcionales, incluidos Yape/Plin sobre cuentas vinculadas.
- Historial con filtros por periodos/tipo/cuenta/estado, paginación y ordenamiento.
- Resumen básico de flujo neto, agrupaciones por clasificación, evolución diaria/semanal/mensual y patrimonio/saldos separados.
- Interfaz con sidebar, formularios, estados/confirmaciones y soporte móvil.
- Pruebas PostgreSQL y E2E, incluidos reintentos después de perder una respuesta de transferencia.

## Fases futuras: propuesta, no implementada
1. Notificaciones programadas para presupuestos y recurrencia automática.
2. Exportaciones y reportes avanzados.
3. Conversión explícita de monedas y precisión por moneda.
4. Conciliación/importación, recurrencia y auditoría de versiones si se solicitan.

## Criterios transversales
- Ningún usuario puede leer, alterar ni relacionar recursos ajenos, incluidos IDs manipulados.
- Validaciones claras y errores consistentes sin filtrar detalles sensibles.
- Importes exactos, sin float; moneda inicial PEN y diseño extensible.
- Datos en UTC y límites de periodos calculados en America/Lima.
- Sin duplicación de transacciones para estadísticas.
- Tests de autorización positiva/negativa, validación, precisión y límites temporales antes de habilitar cada módulo.

## Decisiones pendientes
Transferencias, saldo inicial, crédito y eliminación lógica se definieron en docs/finanzas.md. Pendientes: conversión de monedas, devoluciones específicas, conciliación, periodos presupuestarios y formatos de exportación antes de implementar los módulos afectados.
# Fase 4 implementada

Dashboard con indicadores, análisis temporal y seis gráficos; filtros hoy/ayer/semana/semana anterior/mes/mes anterior/año/rango personalizado. Presupuestos mensuales por área o categoría, CRUD con desactivación, progreso y alertas visuales 80/100 %. Aislamiento por usuario, dinero Decimal, exclusión de transferencias/anulaciones y pagos de deuda sin gasto duplicado. Contratos, límites y criterio de comparación en [analitica-presupuestos.md](analitica-presupuestos.md).
