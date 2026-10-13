# Arquitectura — Fases 1–5

ControlGastos es un monorepo con frontend React/TypeScript y API Django REST Framework independientes. PostgreSQL 17 se ejecuta mediante Docker Compose; frontend y backend se ejecutan en el host en desarrollo.

```text
Navegador (React + Vite + Tailwind; :5173)
    | HTTP JSON + cookies, orígenes autorizados
API REST (/api/v1/, Django + DRF; :8000)
    | ORM + psycopg
PostgreSQL (Docker; 127.0.0.1:5432)
```

`GET /api/v1/health/` conserva su contrato `{"status":"ok","service":"controlgastos-api","version":"v1"}`. Es una comprobación de vida del proceso, no de PostgreSQL. Autenticación y perfil conservan sus rutas; accounts/categories/transactions agregan la API financiera privada documentada en docs/finanzas.md.

`config/` contiene configuración y WSGI/ASGI. `apps/core/` conserva salud y agrega utilidades financieras compartidas (Decimal, UUID, paginación y bloqueo). `apps/users/` conserva autenticación. `apps/accounts/` gestiona activos/crédito, `apps/categories/` jerarquía/catálogo y `apps/transactions/` movimientos, periodos, saldos y reportes. No se agregaron dependencias ni servicios externos en Fase 3. Recharts permanece disponible; la evolución básica se presenta como tablas exactas sin convertir dinero a float.

La API usa queryset por propietario, validación de propiedad de todas las FK y restricciones PostgreSQL. Un propietario controla sus recursos sin recibir owner desde el cliente. Se conserva el mismo usuario UUID y volumen existente; las migraciones financieras solo crean tablas/índices/restricciones nuevos.

El núcleo de consistencia es owner_lock: transaction.atomic + select_for_update sobre la fila del usuario. Todas las escrituras financieras y las lecturas compuestas de saldos/reportes usan el mismo bloqueo. Transferencias son un registro con dos efectos; idempotencia por propietario/UUID y huella del JSON original. Así se evitan escrituras parciales, doble contabilización e inconsistencias de lectura entre agregaciones. Los saldos no se almacenan duplicados.

Frontend financiero en src/finance/, con Sidebar reutilizable y cliente HTTP existente ampliado para DELETE/Idempotency-Key. Hooks cancelan consultas al cambiar filtros; campos de importe son texto decimal. Fechas locales del usuario se convierten a instantes ISO con zona explícita. Dashboard muestra flujo del periodo y patrimonio actual por separado. La UI confirma cambios sensibles y conserva en memoria el payload de una transferencia incierta para reintentar con la misma clave.

React Router define rutas públicas y privadas; AuthProvider consulta auth/me/ al iniciar y representa carga, sesión anónima y fallo de conexión por separado. Los errores de conexión permiten reintentar, sin fingir que no existe sesión. Las rutas privadas guardan un destino permitido y el login vuelve a él. src/lib/api.ts centraliza cookies, CSRF, timeout, errores y expiración de sesión. Formularios usan componentes de campos con etiquetas, mensajes accesibles y estados de carga. No se almacena autenticación en localStorage.

La configuración carga `.env` raíz sin sobrescribir variables del proceso. El frontend utiliza su propio `.env`. Los secretos obligatorios fallan explícitamente si faltan. En producción DEBUG queda desactivado por defecto, se exige HTTPS y las cookies son Secure. La configuración de despliegue, proxy, HSTS y observabilidad deberá resolverse antes de producción.

Sesiones Django almacenadas en PostgreSQL con cookie HttpOnly/SameSite=Lax y duración de 14 días. DRF exige autenticación por defecto; health, csrf, register y login son públicos. CSRFSafeSessionAuthentication fuerza CSRF también en peticiones anónimas inseguras. auth/csrf/ devuelve token en JSON y establece cookie HttpOnly; cada escritura obtiene el token en memoria y lo envía como X-CSRFToken. Login rota el token y la clave de sesión; logout destruye sesión. Cambio de contraseña valida la actual y la nueva, preserva la sesión actual e invalida las demás mediante su hash. Respuestas auth no se cachean.

AbstractUser permite reutilizar permisos, hashers, fechas y Admin. Se eliminó username; email normalizado a minúsculas es USERNAME_FIELD, único también mediante índice funcional Lower(email). UUID es clave primaria y pública. AUTH_USER_MODEL se configuró antes de generar/aplicar la primera migración; no se creó auth_user.

AuthRateLimit guarda HMAC de ámbito/identidad, contador y expiración. La combinación de transacción, fila única y select_for_update serializa actualizaciones entre procesos; no depende de caché local ni del throttle estándar no atómico de DRF. Ventanas fijas por IP/correo/usuario. Admin comparte límites de login y conserva csrf_protect. Estos límites no reemplazan defensas de red; REMOTE_ADDR puede representar un proxy/NAT. Cleanup explícito solo de contadores expirados.

compose.yaml y su volumen PostgreSQL permanecen. compose.dev.yaml agrega backend con Dockerfile y frontend Node 22 como alternativa a dependencias del host. No aplica migraciones al arrancar. Puertos publicados solo en 127.0.0.1. Son servicios de desarrollo; producción requiere un servidor apropiado, TLS y política de proxy. Vite usa sondeo en el contenedor para evitar transformaciones obsoletas en montajes Windows.

Para desarrollo, usar siempre el mismo hostname en frontend/backend (localhost en ambos o 127.0.0.1 en ambos). Cambiar entre ellos puede impedir el envío de cookies SameSite. CORS autoriza lectura desde orígenes explícitos; no reemplaza autenticación ni CSRF.

Los datos financieros tienen propietario, Decimal/NUMERIC y cadenas JSON; números JSON se rechazan como importes. Moneda financiera inicial PEN. Instantes UTC y presentación/filtros en zona del usuario (America/Lima predeterminada), con límites [inicio, fin). Resúmenes por agregación. DELETE desactiva recursos o anula movimientos; PROTECT conserva referencias y VOID es inmutable. Crédito/pagos de deuda y límites del saldo inicial se explican en docs/finanzas.md.

Pruebas: contrato health original, registro, validación, login/logout, CSRF anónimo/autenticado/origen/rotación, perfil, aislamiento, sesiones, cambio de contraseña, manager/Admin/createsuperuser y límites. Suite SQLite rápida y suite PostgreSQL con concurrencia real. E2E Chromium sigue formularios → API → persistencia PostgreSQL → renderizado, recargas y móvil. scripts/check_database.py consulta PostgreSQL desde Django sin modificar datos, incluso antes de migrar.

Referencias técnicas: [Django settings](https://docs.djangoproject.com/en/5.2/ref/settings/), [Vite](https://vite.dev/guide/), [Tailwind con Vite](https://tailwindcss.com/docs/installation/using-vite).
# Extensión de Fase 4

`apps.analytics` agrega el ledger con Decimal, reutiliza period_bounds, balances_for y owner_lock. No almacena tablas de resúmenes. `apps.budgets` añade límites mensuales con restricciones y progreso agrupado sin N+1. React `src/analytics` consume agregados y renderiza Recharts con coordenadas enteras derivadas por backend; importes exactos siguen como cadenas. Se mantiene el resumen de Fase 3. Contrato y comparaciones en [analitica-presupuestos.md](analitica-presupuestos.md).

## Extensión de Fase 5

apps.reports comparte filtered_transactions con el historial y totals/distribution/evolution con analytics. Materializa el snapshot bajo owner_lock y renderiza exportaciones en memoria fuera del bloqueo. apps.audit registra señales acotadas al contexto financiero, dentro de atomic; Model/QuerySet y trigger PostgreSQL conservan append-only. El catálogo inicial y la seguridad de usuarios no se auditan. React reutiliza cliente centralizado con descargas Blob y componentes de auditoría en la página y en el detalle. Contratos y límites en [reportes-auditoria.md](reportes-auditoria.md).
