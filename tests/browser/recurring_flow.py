"""Real recurring flow; AUTOMATIC requires the running Docker scheduler."""

import os
import secrets
import socket
import time
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


def create_ui(
    page,
    account,
    category,
    name,
    amount,
    start,
    end,
    kind="EXPENSE",
    mode="MANUAL",
    destination=None,
):
    page.goto(f"{BASE}/recurrentes/nueva")
    form = page.get_by_role("form", name="Regla recurrente")
    form.get_by_label("Nombre de la regla", exact=True).fill(name)
    form.get_by_label("Tipo de movimiento", exact=True).select_option(kind)
    form.get_by_label("Cuenta de origen", exact=True).select_option(
        account["id"]
    )
    form.get_by_label("Importe programado (PEN)", exact=True).fill(amount)
    if kind == "TRANSFER":
        form.get_by_label("Cuenta de destino", exact=True).select_option(
            destination["id"]
        )
    else:
        form.get_by_label("Área", exact=True).select_option(category["area"])
        form.get_by_label("Categoría", exact=True).select_option(
            category["id"]
        )
    form.get_by_label("Frecuencia", exact=True).select_option("DAILY")
    form.get_by_label("Cada cuántos periodos", exact=True).fill("1")
    form.get_by_label("Fecha inicial", exact=True).fill(start)
    form.get_by_label("Fecha final (opcional)", exact=True).fill(end)
    form.get_by_label("Modo de ejecución", exact=True).select_option(mode)
    form.get_by_role("button", name="Guardar regla", exact=True).click()
    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
    return page.url.rsplit("/", 1)[-1]


def run(context):
    page = context.new_page()
    page.goto(f"{BASE}/recurrentes")
    page.wait_for_url("**/login")
    email = f"cg-recurring-{secrets.token_hex(6)}@example.test"
    password = f"Recurrencias!{secrets.token_urlsafe(20)}"
    page.goto(f"{BASE}/registro")
    for label, value in [
        ("Nombre", "Recurrencias"),
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
    bank = api(
        page,
        "accounts/",
        {
            "name": "Banco recurrencias",
            "kind": "BANK",
            "initial_balance": "1000.00",
        },
        "POST",
    )
    card = api(
        page,
        "accounts/",
        {
            "name": "Tarjeta recurrencias",
            "kind": "CREDIT",
            "initial_balance": "-100.00",
        },
        "POST",
    )
    expense = api(page, "categories/?kind=EXPENSE")["results"][0]
    income = api(page, "categories/?kind=INCOME")["results"][0]
    dates = page.evaluate(
        """() => [-1,0,1].map(offset => {const d=new Date(Date.now()+offset*86400000); return new Intl.DateTimeFormat('en-CA',{timeZone:'America/Lima',year:'numeric',month:'2-digit',day:'2-digit'}).format(d)})"""
    )
    yesterday, today, tomorrow = dates
    year, month = map(int, today.split("-")[:2])
    budget = api(
        page,
        "budgets/",
        {
            "area": expense["area"],
            "limit_amount": "100.00",
            "year": year,
            "month": month,
        },
        "POST",
    )
    rule_id = create_ui(
        page, bank, expense, "Gasto manual prueba", "25.50", yesterday, today
    )
    occurrence = api(page, f"recurring/executions/?rule={rule_id}")["results"][
        0
    ]
    assert api(page, "transactions/")["count"] == 0
    assert api(page, f"budgets/{budget['id']}/progress/")["consumed"] == "0.00"
    page.get_by_role("link", name="Editar regla", exact=True).click()
    page.get_by_label("Importe programado (PEN)", exact=True).fill("30.00")
    page.get_by_role("button", name="Guardar regla", exact=True).click()
    page.get_by_role("button", name="Confirmar ocurrencia", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name=f"{yesterday} · Ejecutada", exact=True
        )
    ).to_be_visible()
    repeated = api(
        page, f"recurring/executions/{occurrence['id']}/confirm/", {}, "POST"
    )
    assert repeated["transaction"]
    assert api(page, "transactions/")["count"] == 1
    page.get_by_role("button", name="Omitir ocurrencia", exact=True).click()
    expect(
        page.get_by_role("heading", name=f"{today} · Omitida", exact=True)
    ).to_be_visible()
    assert api(page, f"recurring/rules/{rule_id}/")["status"] == "COMPLETED"
    page.screenshot(
        path=str(ARTIFACTS / "recurring-manual-desktop.png"), full_page=True
    )
    print("PASS: regla manual, edición, confirmación, omisión e idempotencia")

    transfer_id = create_ui(
        page,
        bank,
        None,
        "Pago tarjeta recurrente",
        "40.00",
        today,
        today,
        "TRANSFER",
        destination=card,
    )
    page.get_by_role("button", name="Pausar regla", exact=True).click()
    expect(
        page.get_by_role("button", name="Reanudar regla", exact=True)
    ).to_be_visible()
    assert (
        page.get_by_role(
            "button", name="Confirmar ocurrencia", exact=True
        ).count()
        == 0
    )
    page.get_by_role("button", name="Reanudar regla", exact=True).click()
    page.get_by_role("button", name="Confirmar ocurrencia", exact=True).click()
    expect(
        page.get_by_role("heading", name=f"{today} · Ejecutada", exact=True)
    ).to_be_visible()
    assert api(page, "reports/preview/")["expense"] == "30.00"
    assert (
        api(page, f"budgets/{budget['id']}/progress/")["consumed"] == "30.00"
    )
    future_id = create_ui(
        page,
        bank,
        expense,
        "Regla futura cancelada",
        "15.00",
        tomorrow,
        tomorrow,
    )
    expect(
        page.get_by_role("button", name="Confirmar ocurrencia", exact=True)
    ).to_be_disabled()
    page.get_by_role("button", name="Cancelar regla", exact=True).click()
    expect(
        page.get_by_role("button", name="Cancelar regla", exact=True)
    ).to_have_count(0)
    assert api(page, f"recurring/rules/{future_id}/")["status"] == "CANCELLED"
    print(
        "PASS: pausa/reanudación, cancelación y pago de tarjeta sin doble gasto"
    )

    automatic_id = create_ui(
        page,
        bank,
        income,
        "Ingreso automático prueba",
        "80.25",
        today,
        today,
        "INCOME",
        "AUTOMATIC",
    )
    assert (
        page.get_by_role(
            "button", name="Confirmar ocurrencia", exact=True
        ).count()
        == 0
    )
    page.close()
    # Real scheduler keeps running while there is no application page open.
    time.sleep(35)
    page = context.new_page()
    page.goto(f"{BASE}/recurrentes/{automatic_id}")
    expect(
        page.get_by_role("heading", name=f"{today} · Ejecutada", exact=True)
    ).to_be_visible()
    automatic = api(page, f"recurring/executions/?rule={automatic_id}")[
        "results"
    ]
    assert len(automatic) == 1 and automatic[0]["transaction"]
    report = api(page, "reports/preview/")
    assert report["income"] == "80.25" and report["expense"] == "30.00"
    assert api(page, "transactions/")["count"] == 3
    print(
        "PASS: scheduler Docker ejecuta sin página abierta; sin movimiento futuro ni duplicado"
    )
    api(
        page,
        "recurring/rules/",
        {
            "name": "Próximo gasto prueba",
            "kind": "EXPENSE",
            "amount": "12.00",
            "source_account": bank["id"],
            "area": expense["area"],
            "category": expense["id"],
            "frequency": "MONTHLY",
            "interval": 1,
            "start_date": tomorrow,
        },
        "POST",
    )
    page.get_by_role("link", name="Inicio", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Próximos movimientos programados", exact=True
        )
    ).to_be_visible()
    expect(
        page.get_by_role("link", name="Próximo gasto prueba", exact=True)
    ).to_be_visible()
    events = api(
        page,
        "audit/events/?resource_type=recurring.recurringexecution&operation=EXECUTE",
    )
    assert events["count"] == 3
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_function(
        "document.documentElement.scrollWidth <= window.innerWidth",
        timeout=5000,
    )
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    page.get_by_role(
        "link", name="Movimientos recurrentes", exact=True
    ).click()
    expect(
        page.get_by_role("heading", name="Movimientos recurrentes", exact=True)
    ).to_be_visible()
    page.get_by_label("Estado de regla", exact=True).select_option("")
    expect(
        page.get_by_role(
            "heading", name="Ingreso automático prueba", exact=True
        )
    ).to_be_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    page.screenshot(
        path=str(ARTIFACTS / "recurring-mobile.png"), full_page=True
    )
    page.get_by_role("button", name="Cerrar sesión", exact=True).click()
    page.wait_for_url("**/login")
    page.goto(f"{BASE}/recurrentes/{transfer_id}")
    page.wait_for_url("**/login")
    print("PASS: dashboard, auditoría, filtros, móvil y rutas privadas")
    print(f"Cuenta sintética conservada: {email}")


args = []
if os.getenv("E2E_DOCKER") == "true":
    args = [
        f"--host-resolver-rules=MAP localhost {socket.gethostbyname('host.docker.internal')}",
        "--no-proxy-server",
    ]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=args)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    errors = []
    context.on(
        "page",
        lambda p: (
            p.on("dialog", lambda d: d.accept()),
            p.on("pageerror", lambda error: errors.append(str(error))),
        ),
    )
    try:
        run(context)
        assert not errors, errors
    except Exception:
        if context.pages:
            context.pages[-1].screenshot(
                path=str(ARTIFACTS / "recurring-failure.png"), full_page=True
            )
        raise
    finally:
        browser.close()
