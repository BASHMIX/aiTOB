from PIL import Image
from io import BytesIO
from backend.core.player_image_service import apply_image_policy, validate_player_image


def _png(size=(64, 64)):
    out = BytesIO(); Image.new("RGB", size, "red").save(out, format="PNG"); return out.getvalue()


def test_image_validation_is_deterministic_and_policy_aware():
    invalid = validate_player_image(_png())
    assert invalid.ok is True
    assert apply_image_policy("required", invalid) == "replace"
    assert apply_image_policy("disabled", invalid) == "skip"
