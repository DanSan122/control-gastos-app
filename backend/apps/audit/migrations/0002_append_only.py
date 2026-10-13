from django.db import migrations


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION controlgastos_audit_immutable() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'audit events are append-only';
            END $$;
            CREATE TRIGGER audit_event_immutable
            BEFORE UPDATE OR DELETE ON audit_auditevent
            FOR EACH ROW EXECUTE FUNCTION controlgastos_audit_immutable();
        """)


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER audit_event_immutable ON audit_auditevent; DROP FUNCTION controlgastos_audit_immutable();"
        )


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunPython(protect, unprotect)]
