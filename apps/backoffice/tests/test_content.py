"""Content management (M8.12, O10; M9.4 pages and FAQ): the hub gate and the guarded editors.

Content edits are gated per model, so a role without the content or catalog permission cannot
reach the editors.
"""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.common.factories import CategoryFactory, StaffUserFactory, login_staff_with_mfa
from apps.content.models import AnnouncementBar, FaqEntry, HomeSection, Page

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_hub_requires_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:content")).status_code == 404


def test_hub_renders(client):
    _staff_with(client, "view_announcementbar")
    assert client.get(reverse("backoffice:content")).status_code == 200


def test_announcement_create_requires_add(client):
    _staff_with(client, "view_announcementbar")
    assert client.get(reverse("backoffice:announcement_new")).status_code == 404


def test_announcement_create_saves(client):
    _staff_with(client, "add_announcementbar")

    client.post(
        reverse("backoffice:announcement_new"),
        {"text": "Free shipping over 999", "url": "/shop/", "is_active": "on"},
    )

    assert AnnouncementBar.objects.filter(text="Free shipping over 999").exists()


def test_category_edit_requires_change(client):
    category = CategoryFactory()
    _staff_with(client, "view_announcementbar")  # no catalog.change_category
    assert (
        client.get(reverse("backoffice:category_edit", kwargs={"pk": category.pk})).status_code
        == 404
    )


def test_category_edit_updates_copy(client):
    category = CategoryFactory(name="Tees", slug="tees", description="Old")
    _staff_with(client, "change_category")

    client.post(
        reverse("backoffice:category_edit", kwargs={"pk": category.pk}),
        {
            "name": "Tees",
            "slug": "tees",
            "description": "New copy",
            "display_order": "0",
            "is_active": "on",
        },
    )

    category.refresh_from_db()
    assert category.description == "New copy"


def test_home_section_edit_updates(client):
    # kind is unique and a content migration may already seed HERO, so reuse whatever row exists.
    section, _ = HomeSection.objects.get_or_create(kind=HomeSection.Kind.HERO)
    _staff_with(client, "change_homesection")

    client.post(
        reverse("backoffice:home_section_edit", kwargs={"pk": section.pk}),
        {"kind": "hero", "title": "New hero", "display_order": "0", "is_active": "on"},
    )

    section.refresh_from_db()
    assert section.title == "New hero"


def test_page_create_requires_add(client):
    _staff_with(client, "view_announcementbar")  # no content.add_page
    assert client.get(reverse("backoffice:page_new")).status_code == 404


def test_page_create_saves_and_sanitises(client):
    _staff_with(client, "add_page")
    client.post(
        reverse("backoffice:page_new"),
        {
            "slug": "about",
            "title": "About us",
            "body": "<p>Made in India</p><script>evil()</script>",
            "is_published": "on",
        },
    )
    page = Page.objects.get(slug="about")
    assert page.is_published is True
    assert "<script>" not in page.body


def test_faq_create_saves(client):
    _staff_with(client, "add_faqentry")
    client.post(
        reverse("backoffice:faq_new"),
        {"question": "Do you ship overseas?", "answer": "Not yet.", "display_order": "0"},
    )
    assert FaqEntry.objects.filter(question="Do you ship overseas?").exists()
