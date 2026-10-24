# Convenciones de ControlGastos

## Alcance y estructura
- Fases 1–6: infraestructura, usuarios, finanzas, analítica, presupuestos PEN, reportes, auditoría y recurrencias. Otras monedas, notificaciones y pagos bancarios externos requieren nuevas tareas.
- Frontend en `frontend/`; backend en `backend/`; decisiones y requisitos en `docs/`.
- API bajo `/api/v1/`. Apps Django por dominio bajo `backend/apps/`; componentes React por funcionalidad cuando comience su implementación.
- Inspeccionar archivos existentes antes de modificarlos. Mantener cambios acotados y documentar decisiones relevantes.

## Seguridad
- Nunca versionar `.env`, credenciales, cookies, tokens, datos personales ni volcados de base de datos.
- Variables `VITE_*` son públicas: nunca contienen secretos.
- Sesiones Django con cookies HttpOnly; HTTPS y cookies Secure fuera de desarrollo. No guardar tokens de autenticación en localStorage.
- No desactivar CSRF. Conservar CSRFSafeSessionAuthentication en registro/login y toda escritura, incluso anónima; SessionAuthentication por sí sola no protege login anónimo. Obtener token desde auth/csrf/, con cookie HttpOnly.
- CORS y CSRF usan orígenes explícitos. No usar comodines con credenciales.
- Nuevos endpoints requieren autenticación por defecto. Filtrar querysets por propietario y validar también el propietario de relaciones; nunca confiar en un user_id del cliente.
- AUTH_USER_MODEL=users.User está definido y migrado. Nunca sustituirlo sin un plan explícito de migración. No crear superusuarios fuera de una solicitud autorizada; tests usan bases temporales.
- Mantener los límites atómicos de login/registro/cambio de contraseña y Admin; no reemplazarlos por contadores en memoria de proceso. No confiar en IP de cabeceras sin un proxy verificado.
- Perfil solo actúa sobre request.user. UUID, correo, permisos, estado y contraseña no son editables por PATCH; rechazar campos adicionales.
- No exponer detalles internos en respuestas de error de producción.

## Datos y código
- Python: PEP 8. TypeScript estricto; no `any` injustificados. Componentes accesibles y estados de carga/error explícitos.
- Dinero: `Decimal` / `DecimalField`, PostgreSQL `NUMERIC`; JSON como cadena decimal. Nunca convertir importes a float ni hacer cálculos monetarios con Number en frontend.
- Moneda predeterminada PEN, código ISO de tres letras. No sumar monedas diferentes sin política explícita de conversión.
- Timestamps conscientes de zona horaria y persistencia UTC; presentación America/Lima. Periodos con límites `[inicio, fin)` convertidos a UTC.
- Transacciones individuales; resúmenes por agregación, sin registros duplicados de periodos.
- Las restricciones de base de datos complementan validaciones de serializer y autorización.
- API financiera: importes como cadenas, MoneyField rechaza números JSON; no usar Number para importes en frontend. Formatear mediante cadenas/BigInt.
- Todas las escrituras financieras toman owner_lock dentro de transaction.atomic; lecturas de saldos/reportes usan ese bloqueo para coherencia. Validar relaciones después del bloqueo.
- Transferencia: un registro con origen/destino, Idempotency-Key UUID y huella del payload; no crear ingreso/gasto para transferencias ni pagos de tarjeta.
- Crédito: saldo/deuda inicial negativo; el límite de crédito nunca es saldo propio. No cambiar tipo/moneda/saldo inicial después de cualquier movimiento.
- DELETE financiero nunca borra: cuenta/clasificación se desactiva, movimiento se anula. VOID es inmutable. Conservar FK PROTECT y restricciones monetarias/jerárquicas.
- Catálogo inicial mediante seed_catalog idempotente; preservar seed_code estable, renombrados y estados. Revisar docs/finanzas.md al cambiar reglas.

## Verificación
- Recurrencias: consultar docs/recurrencias.md. Todas las creaciones de Transaction pasan por create_movement bajo owner_lock. Unicidad regla/fecha, UUIDv5 determinista y enlace único al movimiento; no reejecutar una ocurrencia EXECUTED/VOID o SKIPPED. Calendario local anclado al inicio, zona fijada, nunca movimiento futuro.
- Añadir apps.recurring a las suites de ocho apps anteriores y ejecutar recurring_flow.py junto con los cuatro flujos previos. El E2E automático exige recurring-worker real activo y comprueba ejecución con página cerrada. Aplicar migraciones antes de iniciar el worker optativo de desarrollo; no configurar scheduler de producción sin autorización.
- Auditoría: todas las escrituras siguen owner_lock + save; no bulk/update directo en modelos financieros. Eventos atómicos, append-only; no auditar secretos, description/reference/institution. Consultar docs/reportes-auditoria.md. No recrear eventos previos a activación.
- Reportes: reutilizar filtros/agregaciones; límites de rango/volumen y throttles atómicos. Texto literal en XLSX, protección de fórmulas CSV y escape Paragraph PDF. Importes Excel como texto exacto, no float. Renderizar y revisar páginas tras cambios de PDF.
- Añadir apps.reports y apps.audit a las suites anteriores; ejecutar tests/browser/reports_flow.py y conservar regresiones. QA sintético con scripts/report_artifact_qa.py y tests/browser/render_report_qa.py, archivos solo bajo artifacts ignorado.
- Analítica: consultar docs/analitica-presupuestos.md; coordenadas de gráficos normalizadas en backend, dinero exacto como cadena. Presupuestos: alcance exclusivo, unicidad también inactivos, progreso agrupado sin N+1 y alertas derivadas sin persistir consumo.
- Incluir apps.analytics y apps.budgets en las suites SQLite/PostgreSQL, además de los tests existentes. Ejecutar tests/browser/analytics_flow.py para indicadores, gráficos y presupuestos.
- Backend: `python backend/manage.py check`, `makemigrations --check --dry-run` y `python backend/manage.py test apps.core apps.users apps.transactions --settings=config.settings_test`.
- Frontend: desde `frontend`, `npm run typecheck` y `npm run build`.
- Ejecutar también la suite con `--settings=config.settings_test_postgres` para PostgreSQL y concurrencia; usa base de tests separada. Conservar tests de health originales.
- Ejecutar tests/browser/auth_flow.py para cambios de sesión/rutas/CSRF cuando sea posible; conserva cuentas sintéticas y no registra contraseñas. Capturas ignoradas por Git.
- Ejecutar también tests/browser/finance_flow.py para cambios financieros; prueba la pérdida de respuesta y reintento sin duplicado. No imprimir excepciones de red con cookies/cabeceras.
- En Docker/Windows conservar VITE_USE_POLLING=true; antes de diagnosticar una corrección, confirmar que Vite sirve el archivo actualizado.
- No borrar volúmenes ni datos ni realizar commits sin mostrar primero los cambios al usuario.
- Reportar comandos ejecutados y resultados reales. Distinguir tests SQLite de integración PostgreSQL. No afirmar que Docker o el frontend funcionan sin probarlos.
- Dependencias: requirements.txt declara rangos; requirements.lock.txt se genera desde un entorno limpio comprobado. Docker instala el lock; npm ci utiliza package-lock.json. No inventar hashes. Actualizar documentación al cambiar instalación o comportamiento.
