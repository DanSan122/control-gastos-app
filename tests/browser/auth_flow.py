"""E2E contra servidores activos. Crea una cuenta sintética; no elimina datos.

No registra contraseñas ni captura trazas con payloads. Artefactos ignorados por Git.
"""
import os
import secrets
import socket
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

base_url = os.getenv("E2E_BASE_URL", "http://localhost:5173")
email = f"cg-e2e-{secrets.token_hex(6)}@example.test"
password = f"Prueba!{secrets.token_urlsafe(20)}"
new_password = f"Nueva!{secrets.token_urlsafe(20)}"
artifacts = Path(__file__).resolve().parent / "artifacts"
artifacts.mkdir(exist_ok=True)
args = []
if os.getenv("E2E_DOCKER") == "true":
    # Mantiene el origen localhost (CORS/CSRF/cookies), cambiando solo DNS de Chromium.
    host_ip = socket.gethostbyname("host.docker.internal")
    args = [f"--host-resolver-rules=MAP localhost {host_ip}", "--no-proxy-server"]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=args)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{base_url}/dashboard")
    page.wait_for_url("**/login")
    expect(page.get_by_role("heading", name="Entra a tu espacio")).to_be_visible()
    page.screenshot(path=str(artifacts / "login-desktop.png"), full_page=True)
    print("PASS: ruta privada redirige al login")

    page.get_by_role("link", name="Crea una cuenta").click()
    page.get_by_label("Nombre", exact=True).fill("Lucía")
    page.get_by_label("Apellidos", exact=True).fill("Prueba")
    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_label("Confirmar contraseña", exact=True).fill("Diferente!123")
    page.get_by_role("button", name="Crear cuenta", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("no coinciden")
    page.get_by_label("Confirmar contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Crear cuenta", exact=True).click()
    page.wait_for_url("**/login")
    expect(page.get_by_role("status")).to_contain_text("Tu cuenta está lista")
    print("PASS: validación y registro real")

    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill("Incorrecta!123")
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("incorrectos")
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/dashboard")
    expect(page.get_by_role("heading", name="Bienvenido, Lucía")).to_be_visible()
    session = next(cookie for cookie in context.cookies() if cookie["name"] == "sessionid")
    assert session["httpOnly"] and session["sameSite"] == "Lax"
    page.reload()
    expect(page.get_by_role("heading", name="Bienvenido, Lucía")).to_be_visible()
    page.screenshot(path=str(artifacts / "dashboard-desktop.png"), full_page=True)
    print("PASS: login, cookie segura y persistencia tras recargar")

    page.get_by_role("link", name="Mi perfil", exact=True).click()
    page.get_by_label("Nombre", exact=True).fill("Lucía Actualizada")
    page.get_by_role("button", name="Guardar cambios").click()
    expect(page.get_by_role("status")).to_contain_text("actualizó correctamente")
    page.reload()
    expect(page.get_by_label("Nombre", exact=True)).to_have_value("Lucía Actualizada")
    page.screenshot(path=str(artifacts / "profile-desktop.png"), full_page=True)
    print("PASS: modificación y persistencia del perfil")

    page.get_by_role("link", name="Seguridad", exact=True).click()
    page.get_by_label("Contraseña actual", exact=True).fill(password)
    page.get_by_label("Nueva contraseña", exact=True).fill(new_password)
    page.get_by_label("Confirmar nueva contraseña", exact=True).fill(new_password)
    page.get_by_role("button", name="Cambiar contraseña").click()
    expect(page.get_by_role("status")).to_contain_text("Contraseña actualizada")
    page.reload()
    expect(page.get_by_role("heading", name="Actualiza tu contraseña")).to_be_visible()
    print("PASS: cambio de contraseña conserva la sesión actual")

    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("link", name="Inicio", exact=True).click()
    expect(page.get_by_role("heading", name="Bienvenido, Lucía Actualizada")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(artifacts / "dashboard-mobile.png"), full_page=True)
    page.get_by_role("button", name="Cerrar sesión", exact=True).click()
    page.wait_for_url("**/login")
    page.goto(f"{base_url}/perfil")
    page.wait_for_url("**/login")
    page.screenshot(path=str(artifacts / "login-mobile.png"), full_page=True)
    print("PASS: móvil sin desbordamiento, logout y protección de perfil")

    page.get_by_label("Correo electrónico", exact=True).fill(email)
    page.get_by_label("Contraseña", exact=True).fill(new_password)
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/perfil")
    expect(page.get_by_role("heading", name="Tus datos y preferencias")).to_be_visible()
    expect(page.get_by_label("Nombre", exact=True)).to_have_value("Lucía Actualizada")
    page.get_by_role("button", name="Cerrar sesión", exact=True).click()
    page.wait_for_url("**/login")
    page.goto(f"{base_url}/pagina-inexistente")
    expect(page.get_by_role("heading", name="Este camino no existe")).to_be_visible()
    page.screenshot(path=str(artifacts / "404-mobile.png"), full_page=True)
    assert not errors, errors
    print("PASS: nueva contraseña, redirección al destino previo, 404 y sin errores JavaScript")
    print(f"Cuenta sintética conservada: {email}")
    browser.close()
