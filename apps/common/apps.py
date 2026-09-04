from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate

PLACEHOLDER = "example.com"


def set_site_domain(sender, **kwargs):
    """Point the Site row at the real domain, because sitemap.xml builds every URL from it.

    A `post_migrate` receiver rather than a migration: `django.contrib.sites` creates its row
    from this same signal, so at migration time there is nothing to update yet. Only Django's
    placeholder is replaced, which leaves a domain someone edited by hand alone (L4, A16).
    """
    from django.contrib.sites.models import Site

    using = kwargs.get("using")
    site = Site.objects.using(using).filter(pk=settings.SITE_ID).first()
    if site is None or site.domain != PLACEHOLDER:
        return
    site.domain = settings.SITE_DOMAIN
    site.name = "CivicForest Clothing"
    site.save(using=using, update_fields=["domain", "name"])


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"

    def ready(self):
        # Bound to the sites app's own dispatch, so it runs straight after the row is created.
        from django.apps import apps

        post_migrate.connect(set_site_domain, sender=apps.get_app_config("sites"))
