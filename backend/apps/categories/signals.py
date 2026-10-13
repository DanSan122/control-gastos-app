from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .catalog import seed_catalog


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def seed_new_user(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        seed_catalog(instance)
