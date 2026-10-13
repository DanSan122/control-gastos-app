"""Flujo financiero real con datos sintéticos; conserva los registros creados."""
import os
import secrets
import socket
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.getenv("E2E_BASE_URL", "http://localhost:5173")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def select_named(field, name):
    option = field.locator("option").filter(has_text=name)
    expect(option).to_have_count(1)
    value = option.get_attribute("value")
    assert value
    field.select_option(value=value)


def run(page):
    email = f"cg-finance-{secrets.token_hex(6)}@example.test"
    password = f"Finanzas!{secrets.token_urlsafe(20)}"
    page.goto(f"{BASE}/registro")
    page.get_by_label("Nombre", exact=True).fill("Finanzas")
    page.get_by_label("Apellidos", exact=True).fill("Prueba")
    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_label("Confirmar contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Crear cuenta", exact=True).click()
    page.wait_for_url("**/login")
    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/dashboard")
    expect(page.get_by_role("heading", name="Bienvenido, Finanzas")).to_be_visible()
    print("PASS: autenticación y resumen vacío")

    page.get_by_role("link", name="Mis cuentas", exact=True).click()
    for name, kind, opening in [("Banco prueba", "BANK", "1000.00"), ("Efectivo prueba", "CASH", "50.00"), ("Tarjeta prueba", "CREDIT", "-100.00")]:
        form = page.get_by_role("form", name="Nueva cuenta", exact=True)
        form.get_by_label("Nombre de la cuenta").fill(name)
        form.get_by_label("Tipo de cuenta").select_option(kind)
        form.get_by_label("Saldo inicial (PEN)").fill(opening)
        form.get_by_role("button", name="Guardar cuenta").click()
        expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
    print("PASS: creación de cuentas de activos y crédito")

    for value in ("1050.00", "1000.00"):
        card = page.locator("article").filter(has=page.get_by_role("heading", name="Banco prueba", exact=True))
        card.get_by_role("button", name="Editar", exact=True).click()
        form = page.get_by_role("form", name="Editar cuenta", exact=True)
        form.get_by_label("Saldo inicial (PEN)").fill(value)
        form.get_by_role("button", name="Guardar cuenta").click()
        expect(page.get_by_role("form", name="Nueva cuenta", exact=True)).to_be_visible()
        expect(card).to_contain_text("1,050.00" if value == "1050.00" else "1,000.00")
    print("PASS: corrección de saldo inicial antes del primer movimiento")

    page.get_by_role("link", name="Áreas y categorías", exact=True).click()
    area = page.get_by_role("form", name="Nueva área", exact=True)
    area.get_by_label("Nombre de área", exact=True).fill("Proyectos prueba")
    area.get_by_role("button", name="Crear área", exact=True).click()
    category = page.get_by_role("form", name="Nueva categoría", exact=True)
    category.get_by_label("Nombre de categoría", exact=True).fill("Materiales prueba")
    category.get_by_label("Área padre").select_option(label="Proyectos prueba")
    category.get_by_role("button", name="Crear categoría", exact=True).click()
    sub = page.get_by_role("form", name="Nueva subcategoría", exact=True)
    sub.get_by_label("Nombre de subcategoría", exact=True).fill("Papelería prueba")
    sub.get_by_label("Categoría padre").select_option(label="Materiales prueba · Gasto")
    sub.get_by_role("button", name="Crear subcategoría", exact=True).click()
    expect(page.get_by_text("Papelería prueba", exact=True)).to_be_visible()
    print("PASS: catálogo inicial y creación de jerarquía propia")

    page.get_by_role("link", name="Registrar gasto", exact=True).click()
    form = page.get_by_role("form", name="Movimiento financiero")
    select_named(form.get_by_label("Cuenta", exact=True), "Tarjeta prueba")
    form.get_by_label("Importe (PEN)").fill("30.00")
    form.get_by_label("Área", exact=True).select_option(label="Alimentación")
    form.get_by_label("Categoría", exact=True).select_option(label="General")
    form.get_by_label("Descripción", exact=True).fill("Compra en tarjeta prueba")
    form.get_by_role("button", name="Guardar gasto", exact=True).click()
    page.wait_for_url("**/movimientos/*")
    expect(page.get_by_role("heading", name="Detalle del movimiento")).to_be_visible()

    page.get_by_role("link", name="Registrar ingreso", exact=True).click()
    form = page.get_by_role("form", name="Movimiento financiero")
    select_named(form.get_by_label("Cuenta", exact=True), "Banco prueba")
    form.get_by_label("Importe (PEN)").fill("200.00")
    form.get_by_label("Área", exact=True).select_option(label="Finanzas")
    form.get_by_label("Categoría", exact=True).select_option(label="Sueldo")
    form.get_by_label("Descripción", exact=True).fill("Ingreso prueba")
    form.get_by_role("button", name="Guardar ingreso", exact=True).click()
    page.wait_for_url("**/movimientos/*")
    print("PASS: gasto de tarjeta e ingreso con selectores dependientes")

    # El servidor recibe el primer POST, pero el navegador pierde la respuesta.
    lost = [False]
    def lose_response(route):
        if route.request.method == "POST" and not lost[0]:
            target = route.request.url
            headers = route.request.headers
            if os.getenv("E2E_DOCKER") == "true":
                target = target.replace("http://localhost:8000", "http://host.docker.internal:8000")
                headers = {**headers, "host": "localhost:8000"}
            try:
                response = route.fetch(url=target, headers=headers)
                lost[0] = response.status == 201
            except Exception:
                # No imprimir excepciones de red que puedan incluir cookies/cabeceras.
                lost[0] = False
            route.abort("failed")
        else:
            route.continue_()
    page.route("**/api/v1/transfers/", lose_response)
    page.get_by_role("link", name="Transferir dinero", exact=True).click()
    form = page.get_by_role("form", name="Movimiento financiero")
    select_named(form.get_by_label("Cuenta de origen"), "Banco prueba")
    select_named(form.get_by_label("Cuenta de destino"), "Tarjeta prueba")
    form.get_by_label("Importe (PEN)").fill("100.00")
    form.get_by_label("Descripción", exact=True).fill("Pago de tarjeta prueba")
    form.get_by_role("button", name="Confirmar transferencia", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("No se pudo conectar")
    assert lost[0], "La simulación no confirmó una transferencia guardada antes de perder la respuesta."
    page.get_by_role("button", name="Reintentar la misma transferencia", exact=True).click()
    page.wait_for_url("**/movimientos/*")
    expect(page.get_by_role("heading", name="Detalle del movimiento")).to_be_visible()
    page.unroute("**/api/v1/transfers/", lose_response)
    page.get_by_role("link", name="Resumen financiero", exact=True).click()
    expect(page.locator("section").filter(has=page.get_by_role("heading", name="Gastos del periodo", exact=True))).to_contain_text("S/ 30.00")
    expect(page.locator("section").filter(has=page.get_by_role("heading", name="Ingresos del periodo", exact=True))).to_contain_text("S/ 200.00")
    expect(page.locator("section").filter(has=page.get_by_role("heading", name="Patrimonio registrado actual", exact=True))).to_contain_text("S/ 1,120.00")
    print("PASS: reintento idempotente tras pérdida de respuesta y deuda sin doble gasto")

    page.get_by_role("link", name="Registrar gasto", exact=True).click()
    form = page.get_by_role("form", name="Movimiento financiero")
    select_named(form.get_by_label("Cuenta", exact=True), "Banco prueba")
    form.get_by_label("Método de pago").select_option("YAPE")
    form.get_by_label("Importe (PEN)").fill("12.30")
    form.get_by_label("Área", exact=True).select_option(label="Proyectos prueba")
    form.get_by_label("Categoría", exact=True).select_option(label="Materiales prueba")
    form.get_by_label("Subcategoría", exact=True).select_option(label="Papelería prueba")
    form.get_by_label("Descripción", exact=True).fill("Compra Yape prueba")
    form.get_by_role("button", name="Guardar gasto", exact=True).click()
    page.wait_for_url("**/movimientos/*")
    page.get_by_role("button", name="Editar movimiento", exact=True).click()
    page.get_by_label("Importe (PEN)").fill("20.30")
    page.get_by_role("button", name="Guardar corrección", exact=True).click()
    expect(page.get_by_role("heading", name="Detalle del movimiento")).to_be_visible()
    expect(page.get_by_text("S/ 20.30", exact=True)).to_be_visible()
    page.get_by_role("button", name="Anular movimiento", exact=True).click()
    expect(page.get_by_text("Gasto · Anulado", exact=True)).to_be_visible()
    print("PASS: Yape vinculado al banco, edición y anulación con historial")

    page.get_by_role("link", name="Historial", exact=True).click()
    page.get_by_label("Estado", exact=True).select_option("VOID")
    expect(page.get_by_role("heading", name="Compra Yape prueba", exact=True)).to_be_visible()
    page.get_by_label("Estado", exact=True).select_option("POSTED")
    page.get_by_label("Tipo", exact=True).select_option("TRANSFER")
    expect(page.get_by_role("heading", name="Pago de tarjeta prueba", exact=True)).to_be_visible()
    expect(page.get_by_text("1 movimientos · página 1", exact=True)).to_be_visible()
    page.get_by_role("link", name="Resumen financiero", exact=True).click()
    page.get_by_label("Periodo", exact=True).select_option("day")
    page.get_by_label("Agrupar por").select_option("weekly")
    expect(page.get_by_text("S/ 170.00", exact=True).first).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / "finance-summary-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("heading", name="Tu panorama financiero")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "finance-summary-mobile.png"), full_page=True)
    page.get_by_role("link", name="Mis cuentas", exact=True).click()
    expect(page.get_by_role("heading", name="Banco prueba", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "finance-accounts-mobile.png"), full_page=True)
    page.get_by_role("button", name="Cerrar sesión", exact=True).click()
    page.wait_for_url("**/login")
    page.goto(f"{BASE}/cuentas")
    page.wait_for_url("**/login")
    print("PASS: filtros, resumen, evolución, móvil y rutas privadas")
    print(f"Cuenta sintética conservada: {email}")


args = []
if os.getenv("E2E_DOCKER") == "true":
    args = [f"--host-resolver-rules=MAP localhost {socket.gethostbyname('host.docker.internal')}", "--no-proxy-server"]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=args)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("dialog", lambda dialog: dialog.accept())
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        run(page)
        assert not errors, errors
    except Exception:
        page.screenshot(path=str(ARTIFACTS / "finance-failure.png"), full_page=True)
        print(f"Fallo de E2E en ruta: {page.url}")
        raise
    finally:
        browser.close()
