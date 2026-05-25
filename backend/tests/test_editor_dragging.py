import pytest
import os
import json
import aiosqlite

from backend.core.database import init_db, save_overlay, get_overlays, delete_overlay, DB_PATH
from backend.api.schemas import SaveOverlayRequest

TEST_DB_PATH = "backend/core/test_database.sqlite"

@pytest.fixture
async def setup_test_db():
    import backend.core.database
    
    orig_db_path = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    
    # Initialize the test database
    await init_db()
    
    yield
    
    # Clean up test database
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
            
    # Restore original paths
    backend.core.database.DB_PATH = orig_db_path


@pytest.mark.asyncio
async def test_save_and_retrieve_overlay_coordinates(setup_test_db):
    """Verify that we can successfully save an overlay with draggable elements and retrieve it."""
    overlay_name = "test_stream_overlay"
    
    # Simulating a state matching the DraggableElement and Rnd config structure
    overlay_config = {
        "elements": {
            "p1_name": {
                "id": "p1_name",
                "type": "text",
                "x": 400.6,  # Test float coordinates to ensure they are handled properly
                "y": 950.2,
                "width": 250.3,
                "height": 60.1,
                "fontSize": 48,
                "color": "#ffffff",
                "text": "Player 1",
                "visible": True,
                "zIndex": 10
            },
            "p1_avatar": {
                "id": "p1_avatar",
                "type": "image",
                "x": 250,
                "y": 850,
                "width": 180,
                "height": 180,
                "src": "/static/player_placeholder.jpg",
                "visible": True,
                "zIndex": 1
            }
        },
        "background_url": "/static/background.png",
        "global_font_url": "",
        "global_font_family": "Roboto"
    }
    
    # 1. Test Pydantic validation
    request = SaveOverlayRequest(name=overlay_name, config=overlay_config)
    assert request.name == overlay_name
    assert "p1_name" in request.config["elements"]
    
    # 2. In frontend-react, coordinates are rounded before saving (matching our dragging fixes)
    rounded_elements = {}
    for el_id, el in request.config["elements"].items():
        rounded_elements[el_id] = {
            **el,
            "x": round(el.get("x", 0)),
            "y": round(el.get("y", 0)),
            "width": round(el.get("width")) if el.get("width") is not None else None,
            "height": round(el.get("height")) if el.get("height") is not None else None,
        }
    
    assert rounded_elements["p1_name"]["x"] == 401
    assert rounded_elements["p1_name"]["y"] == 950
    assert rounded_elements["p1_name"]["width"] == 250
    assert rounded_elements["p1_name"]["height"] == 60
    
    # 3. Save to database
    config_to_save = {
        **overlay_config,
        "elements": rounded_elements
    }
    
    await save_overlay(overlay_name, config_to_save)
    
    # 4. Retrieve and verify
    overlays = await get_overlays()
    assert len(overlays) > 0
    
    target_overlay = next((o for o in overlays if o["name"] == overlay_name), None)
    assert target_overlay is not None
    
    saved_config = json.loads(target_overlay["config"])
    assert saved_config["background_url"] == "/static/background.png"
    assert saved_config["global_font_family"] == "Roboto"
    
    # Verify dragging coordinates are integers
    saved_p1 = saved_config["elements"]["p1_name"]
    assert isinstance(saved_p1["x"], int)
    assert isinstance(saved_p1["y"], int)
    assert isinstance(saved_p1["width"], int)
    assert isinstance(saved_p1["height"], int)
    
    assert saved_p1["x"] == 401
    assert saved_p1["y"] == 950
    assert saved_p1["width"] == 250
    assert saved_p1["height"] == 60
    
    # 5. Clean up
    await delete_overlay(overlay_name)
    overlays_after_delete = await get_overlays()
    assert not any(o["name"] == overlay_name for o in overlays_after_delete)
