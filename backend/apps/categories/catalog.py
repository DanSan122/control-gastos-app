from apps.core.finance import owner_lock
from .models import Area, Category, Subcategory

AREAS = ["Alimentación", "Transporte", "Vivienda", "Educación", "Salud", "Entretenimiento", "Finanzas", "Compras personales", "Otros"]


def seed_catalog(user):
    with owner_lock(user):
        for index, name in enumerate(AREAS):
            code = f"area-{index}"
            area = Area.objects.filter(owner=user, family__isnull=True, seed_code=code).first()
            if area is None:
                area, _ = Area.objects.get_or_create(owner=user, family=None, name=name, defaults={"seed_code": code})
                if area.seed_code is None:
                    area.seed_code = code
                    area.save(update_fields=["seed_code"])
            category, _ = Category.objects.get_or_create(owner=user, family=None, seed_code=f"expense-{index}", defaults={
                "area": area, "name": "General", "kind": "EXPENSE",
            })
            Subcategory.objects.get_or_create(owner=user, family=None, seed_code=f"sub-{index}", defaults={"category": category, "name": "Otros"})
        finance = Area.objects.get(owner=user, family__isnull=True, seed_code="area-6")
        for code, name in [("salary", "Sueldo"), ("other-income", "Otros ingresos")]:
            Category.objects.get_or_create(owner=user, family=None, seed_code=code, defaults={"area": finance, "name": name, "kind": "INCOME"})
