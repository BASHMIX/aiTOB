from backend.core.provider_projection import reviewed_identity_projection


def test_reviewed_identity_projection_preserves_provider_fallback():
    result = reviewed_identity_projection({"slug": "cup", "provider_type": "startgg"}, {"name": "Provider Cup", "logo_url": "https://provider/logo"}, {"display_name": "Local Cup"})
    assert result["display_name"] == "Local Cup"
    assert result["logo_url"] == "https://provider/logo"
    assert result["provenance"]["display_name"] == "local"
