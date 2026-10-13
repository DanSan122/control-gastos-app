const destinations = ['/dashboard', '/analisis', '/comparacion', '/presupuestos', '/perfil', '/seguridad', '/cuentas', '/clasificaciones', '/gastos/nuevo', '/ingresos/nuevo', '/transferir', '/movimientos', '/resumen']
export function privateDestination(value: string | undefined) {
  return value && (destinations.includes(value) || /^\/movimientos\/[0-9a-f-]{36}$/i.test(value)) ? value : '/dashboard'
}
