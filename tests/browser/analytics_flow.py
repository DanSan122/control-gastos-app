"""Chromium + React + session/CSRF + PostgreSQL, using retained synthetic data."""
import os
import secrets
import socket
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("E2E_BASE_URL", "http://localhost:5173")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def api(page, path, data=None, method="GET"):
    # Runs in Chromium so the existing localhost resolver and Origin apply.
    return page.evaluate("""async ({path, data, method}) => {
      const base = 'http://localhost:8000/api/v1/';
      const headers = {'Content-Type': 'application/json'};
      if (method !== 'GET') {
        const csrf = await fetch(base + 'auth/csrf/', {credentials: 'include'});
        headers['X-CSRFToken'] = (await csrf.json()).csrfToken;
      }
      const response = await fetch(base + path, {method, headers, credentials: 'include', body: method === 'GET' ? undefined : JSON.stringify(data)});
      if (!response.ok) throw new Error('Fixture API status ' + response.status);
      return response.status === 204 ? null : response.json();
    }""", {"path": path, "data": data, "method": method})


def run(page):
    email = f"cg-analytics-{secrets.token_hex(6)}@example.test"
    password = f"Analisis!{secrets.token_urlsafe(20)}"
    page.goto(f"{BASE}/presupuestos")
    page.wait_for_url("**/login")
    page.goto(f"{BASE}/registro")
    for label, value in [("Nombre", "Analítica"), ("Apellidos", "Prueba"), ("Correo electrónico", email), ("Contraseña", password), ("Confirmar contraseña", password)]:
        page.get_by_label(label, exact=True).fill(value)
    page.get_by_role("button", name="Crear cuenta", exact=True).click()
    page.wait_for_url("**/login")
    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/dashboard")
    expect(page.get_by_role("heading", name="Bienvenido, Analítica")).to_be_visible()
    expect(page.get_by_text("No hay gastos en este periodo.").first).to_be_visible()
    account = api(page, "accounts/", {"name": "Banco análisis", "kind": "BANK", "initial_balance": "1000.00"}, "POST")
    categories = api(page, "categories/?kind=EXPENSE")['results']
    category = categories[0]
    instant = page.evaluate("new Date(Date.now() - 60000).toISOString()")
    expense = api(page, "transactions/", {"account": account['id'], "kind": "EXPENSE", "amount": "80.00", "area": category['area'], "category": category['id'], "occurred_at": instant}, "POST")
    page.get_by_role("link", name="Presupuestos", exact=True).click()
    form = page.get_by_role("form", name="Nuevo presupuesto")
    form.get_by_label("Alcance", exact=True).select_option("category")
    form.get_by_label("Clasificación", exact=True).select_option(category['id'])
    form.get_by_label("Límite (PEN)", exact=True).fill("100.00")
    form.get_by_role("button", name="Guardar presupuesto").click()
    expect(page.get_by_text("Alerta: has alcanzado el 80 %.", exact=True)).to_be_visible()
    article = page.locator('article').filter(has=page.get_by_role('heading', name=category['name'], exact=True))
    article.get_by_role('button', name='Editar', exact=True).click()
    edit = page.get_by_role('form', name='Editar presupuesto')
    edit.get_by_label('Límite (PEN)', exact=True).fill('80.00')
    edit.get_by_role('button', name='Guardar presupuesto').click()
    expect(page.get_by_text('Límite alcanzado o superado.', exact=True)).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / 'budgets-desktop.png'), full_page=True)
    print('PASS: presupuestos, creación/edición y alertas 80/100')
    page.get_by_role('link', name='Inicio', exact=True).click()
    expect(page.get_by_text('Gastos del periodo', exact=True)).to_be_visible()
    expect(page.locator('.recharts-wrapper')).to_have_count(6)
    expect(page.get_by_role('heading', name='Presupuestos del mes actual')).to_be_visible()
    page.get_by_label('Agrupar por', exact=True).select_option('monthly')
    expect(page.locator('.recharts-wrapper')).to_have_count(6)
    page.get_by_label('Periodo', exact=True).select_option('year')
    expect(page.locator('.recharts-wrapper')).to_have_count(6)
    page.screenshot(path=str(ARTIFACTS / 'analytics-desktop.png'), full_page=True)
    page.get_by_role('link', name='Comparar periodos', exact=True).click()
    expect(page.get_by_text('Sin base porcentual anterior', exact=False).first).to_be_visible()
    page.get_by_label('Periodo', exact=True).select_option('yesterday')
    expect(page.get_by_role('img', name='Comparación entre periodos')).to_be_visible()
    page.get_by_role('link', name='Análisis de gastos', exact=True).click()
    expect(page.get_by_role('heading', name='Análisis de gastos', exact=True)).to_be_visible()
    print('PASS: seis gráficos, filtros, comparación y análisis')
    api(page, f"transactions/{expense['id']}/", {}, 'DELETE')
    page.get_by_role('link', name='Presupuestos', exact=True).click()
    expect(page.get_by_text('S/ 0.00 de S/ 80.00 · 0.00 %', exact=True)).to_be_visible()
    assert page.get_by_text('Límite alcanzado o superado.', exact=True).count() == 0
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(ARTIFACTS / 'budgets-mobile.png'), full_page=True)
    page.get_by_role('button', name='Desactivar', exact=True).click()
    expect(page.get_by_text('Área · Inactivo', exact=True).or_(page.get_by_text('Categoría · Inactivo', exact=True))).to_be_visible()
    page.get_by_role('link', name='Inicio', exact=True).click()
    expect(page.get_by_role('heading', name='Bienvenido, Analítica')).to_be_visible()
    expect(page.locator('.recharts-wrapper')).to_have_count(4)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(ARTIFACTS / 'analytics-mobile.png'), full_page=True)
    page.reload()
    expect(page.get_by_role('heading', name='Bienvenido, Analítica')).to_be_visible()
    page.get_by_role('button', name='Cerrar sesión', exact=True).click()
    page.wait_for_url('**/login')
    page.goto(f'{BASE}/comparacion')
    page.wait_for_url('**/login')
    print('PASS: gasto anulado, desactivación, móvil y persistencia/protección de sesión')
    print(f'Cuenta sintética conservada: {email}')


args = []
if os.getenv('E2E_DOCKER') == 'true':
    args = [f"--host-resolver-rules=MAP localhost {socket.gethostbyname('host.docker.internal')}", '--no-proxy-server']
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=args)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.on('dialog', lambda dialog: dialog.accept())
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        run(page)
        assert not errors, errors
    except Exception:
        page.screenshot(path=str(ARTIFACTS / 'analytics-failure.png'), full_page=True)
        raise
    finally:
        browser.close()
