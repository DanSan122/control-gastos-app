"""Real session/CSRF report downloads and atomic audit, retained synthetic account."""

import os
import secrets
import socket
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

BASE = os.getenv("E2E_BASE_URL", "http://localhost:5173")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def api(page, path, data=None, method="GET"):
    return page.evaluate(
        """async ({path,data,method}) => {
      const base='http://localhost:8000/api/v1/'; const headers={'Content-Type':'application/json'};
      if(method!=='GET') { const r=await fetch(base+'auth/csrf/',{credentials:'include'}); headers['X-CSRFToken']=(await r.json()).csrfToken; }
      const r=await fetch(base+path,{method,headers,credentials:'include',body:method==='GET'?undefined:JSON.stringify(data)});
      if(!r.ok) throw new Error('Fixture API status '+r.status);
      return r.status===204?null:r.json();
    }""",
        {"path": path, "data": data, "method": method},
    )


def run(page):
    email = f"cg-reports-{secrets.token_hex(6)}@example.test"
    password = f"Reportes!{secrets.token_urlsafe(20)}"
    page.goto(f"{BASE}/reportes")
    page.wait_for_url("**/login")
    page.goto(f"{BASE}/registro")
    for label, value in [
        ("Nombre", "Reportes"),
        ("Apellidos", "Prueba"),
        ("Correo electrónico", email),
        ("Contraseña", password),
        ("Confirmar contraseña", password),
    ]:
        page.get_by_label(label, exact=True).fill(value)
    page.get_by_role("button", name="Crear cuenta", exact=True).click()
    page.wait_for_url("**/login")
    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/dashboard")
    page.get_by_role("link", name="Reportes", exact=True).click()
    expect(
        page.get_by_text("No hay movimientos para estos filtros.", exact=True)
    ).to_be_visible()
    account = api(
        page,
        "accounts/",
        {
            "name": "Banco reporte",
            "kind": "BANK",
            "initial_balance": "1000.00",
        },
        "POST",
    )
    category = api(page, "categories/?kind=EXPENSE")["results"][0]
    instant = page.evaluate("new Date(Date.now()-60000).toISOString()")
    movement = api(
        page,
        "transactions/",
        {
            "account": account["id"],
            "kind": "EXPENSE",
            "amount": "25.50",
            "category": category["id"],
            "area": category["area"],
            "description": "=1+1",
            "payment_method": "YAPE",
            "occurred_at": instant,
        },
        "POST",
    )
    page.reload()
    form = page.get_by_role("form", name="Filtros del reporte")
    form.get_by_label("Cuenta", exact=True).select_option(account["id"])
    form.get_by_label("Área", exact=True).select_option(category["area"])
    form.get_by_label("Categoría", exact=True).select_option(category["id"])
    form.get_by_label("Tipo", exact=True).select_option("EXPENSE")
    form.get_by_label("Método de pago", exact=True).select_option("YAPE")
    form.get_by_role(
        "button", name="Actualizar vista previa", exact=True
    ).click()
    expect(
        page.get_by_text("1 movimientos · página 1", exact=True)
    ).to_be_visible()
    expect(page.get_by_text("S/ 25.50", exact=True).first).to_be_visible()
    for label, kind in (("Excel", "xlsx"), ("CSV", "csv"), ("PDF", "pdf")):
        with page.expect_download() as event:
            page.get_by_role(
                "button", name=f"Exportar {label}", exact=True
            ).click()
        download = event.value
        path = ARTIFACTS / f"browser-report.{kind}"
        download.save_as(path)
        assert download.failure() is None
        raw = path.read_bytes()
        assert raw.startswith(
            {"xlsx": b"PK", "csv": b"\xef\xbb\xbf", "pdf": b"%PDF-"}[kind]
        )
    page.screenshot(
        path=str(ARTIFACTS / "reports-desktop.png"), full_page=True
    )
    print(
        "PASS: filtros combinados, vista previa y tres descargas autenticadas"
    )
    page.goto(f"{BASE}/movimientos/{movement['id']}")
    expect(
        page.get_by_role(
            "heading", name="Historial de cambios del movimiento", exact=True
        )
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Creación · Movimiento", exact=True)
    ).to_be_visible()
    api(
        page,
        f"transactions/{movement['id']}/",
        {"amount": "30.00", "description": "Texto privado actualizado"},
        "PATCH",
    )
    page.reload()
    expect(
        page.get_by_role("heading", name="Edición · Movimiento", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Anular movimiento", exact=True).click()
    expect(
        page.get_by_role("heading", name="Anulación · Movimiento", exact=True)
    ).to_be_visible()
    events = api(page, f"audit/events/?resource_id={movement['id']}")[
        "results"
    ]
    assert len(events) == 3
    assert all(
        "description" not in e["after"] and "reference" not in e["after"]
        for e in events
    )
    page.get_by_role("link", name="Auditoría", exact=True).click()
    page.get_by_label("Recurso", exact=True).select_option(
        "transactions.transaction"
    )
    page.get_by_label("Operación", exact=True).select_option("VOID")
    expect(
        page.get_by_role("heading", name="Anulación · Movimiento", exact=True)
    ).to_be_visible()
    page.get_by_text(
        "Ver valores anteriores y posteriores", exact=True
    ).click()
    expect(page.get_by_role("cell", name="POSTED", exact=True)).to_be_visible()
    expect(page.get_by_role("cell", name="VOID", exact=True)).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / "audit-desktop.png"), full_page=True)
    print(
        "PASS: auditoría de creación, edición, anulación y campos redactados"
    )
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    page.screenshot(path=str(ARTIFACTS / "audit-mobile.png"), full_page=True)
    page.get_by_role("link", name="Reportes", exact=True).click()
    page.get_by_label("Estado", exact=True).select_option("VOID")
    page.get_by_role(
        "button", name="Actualizar vista previa", exact=True
    ).click()
    expect(
        page.get_by_text("1 movimientos · página 1", exact=True)
    ).to_be_visible()
    expect(page.get_by_text("S/ 0.00", exact=True).first).to_be_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    page.screenshot(path=str(ARTIFACTS / "reports-mobile.png"), full_page=True)
    page.get_by_role("button", name="Cerrar sesión", exact=True).click()
    page.wait_for_url("**/login")
    page.goto(f"{BASE}/auditoria")
    page.wait_for_url("**/login")
    print("PASS: móvil, anulados fuera de indicadores y rutas privadas")
    print(f"Cuenta sintética conservada: {email}")


args = []
if os.getenv("E2E_DOCKER") == "true":
    args = [
        f"--host-resolver-rules=MAP localhost {socket.gethostbyname('host.docker.internal')}",
        "--no-proxy-server",
    ]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=args)
    page = browser.new_page(
        viewport={"width": 1440, "height": 1000}, accept_downloads=True
    )
    page.on("dialog", lambda dialog: dialog.accept())
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        run(page)
        assert not errors, errors
    except Exception:
        page.screenshot(
            path=str(ARTIFACTS / "reports-failure.png"), full_page=True
        )
        raise
    finally:
        browser.close()
