"""Generated image widths: the rules srcset depends on being true.

srcset is a promise to the browser. If it lists a width whose file does not exist the image
breaks, and if a 900px original is offered at 1600w the browser downloads an upscale. Both
are silent in a page that looks fine on a fast desktop, which is why they are tested here.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog import services
from apps.catalog.models import ProductImage
from apps.common.factories import ProductFactory

pytestmark = pytest.mark.django_db


def _png(width: int, height: int, name: str = "shot.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "#1f3d2b").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _image(width: int, height: int) -> ProductImage:
    return ProductImage.objects.create(
        product=ProductFactory(), image=_png(width, height), alt_text="A green tee"
    )


def test_every_recorded_width_has_a_file_behind_it():
    image = _image(2000, 2600)

    keys = services.build_image_widths(image)

    assert sorted(keys) == ["1600", "400", "800"]
    for key in keys.values():
        assert image.image.storage.exists(key)
        assert key.endswith(".webp")


def test_a_narrow_original_is_never_offered_at_a_width_it_does_not_have():
    keys = services.build_image_widths(_image(900, 1200))

    assert sorted(keys) == ["400", "800"]


def test_an_original_smaller_than_the_smallest_width_still_gets_one_derivative():
    keys = services.build_image_widths(_image(320, 420))

    assert list(keys) == ["320"]


def test_the_derivative_is_resized_not_just_re_encoded():
    image = _image(2000, 2600)

    keys = services.build_image_widths(image)

    with image.image.storage.open(keys["400"]) as handle:
        assert Image.open(handle).size == (400, 520)


def test_running_twice_converges_instead_of_piling_up_duplicates():
    image = _image(1000, 1000)

    first = services.build_image_widths(image)
    second = services.build_image_widths(image)

    assert first == second
    directory, files = image.image.storage.listdir("products")
    assert len(files) == 1 + len(second), files


def test_srcset_lists_the_widths_in_order_and_is_empty_without_them():
    image = _image(1000, 1000)

    assert services.srcset(image) == ""

    services.build_image_widths(image)
    value = services.srcset(image)

    assert [part.split()[-1] for part in value.split(", ")] == ["400w", "800w"]


def test_an_image_row_with_no_file_is_left_alone():
    image = ProductImage.objects.create(product=ProductFactory(), alt_text="Missing")

    assert services.build_image_widths(image) == {}
