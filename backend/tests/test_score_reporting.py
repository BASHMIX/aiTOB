import pytest
from unittest.mock import AsyncMock, patch
from backend.core import database
from backend.core.score_reporting import report_score_to_provider
from backend.core.contracts import ITournamentProvider, ProviderSetResult


@pytest.fixture(autouse=True)
async def score_context(monkeypatch):
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES ('workspace-score', 'workspace-score', 'Scores')"
        )
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name)
               VALUES ('score-account', 'workspace-score', 'workspace-score', 'challonge', 'remote', 'Scores')"""
        )
        await db.commit()
    await database.upsert_tournament(
        "score/event", "Scores", "", "", "", "{}", provider_type="challonge",
        provider_account_id="score-account", workspace_id="workspace-score",
    )
    await database.upsert_active_match(
        "set_1", tournament_slug="score/event", p1_name="One", p2_name="Two",
        p1_entrant_id="p1", p2_entrant_id="p2", workspace_id="workspace-score",
    )
    monkeypatch.setattr(
        "backend.core.score_reporting._schedule_post_result_verification", AsyncMock()
    )

@pytest.fixture
def mock_provider():
    provider = AsyncMock(spec=ITournamentProvider)
    provider.provider_type = "challonge"
    return provider

@pytest.mark.asyncio
async def test_report_score_to_provider_success(mock_provider):
    # Setup
    mock_provider.report_score.return_value = ProviderSetResult(
        success=True,
        set_id="set_1",
        error_message=None
    )

    # Execute
    result = await report_score_to_provider(
        set_id="set_1",
        winner_id="p1",
        p1_id="p1",
        p2_id="p2",
        p1_score=2,
        p2_score=1,
        provider=mock_provider
    )

    # Assert
    assert result.success is True
    assert result.set_id == "set_1"

    mock_provider.report_score.assert_called_once_with(
        set_id="set_1",
        winner_id="p1",
        entrant1_id="p1",
        entrant2_id="p2",
        entrant1_score=2,
        entrant2_score=1,
    )
    mock_provider.report_winner_only.assert_not_called()

@pytest.mark.asyncio
async def test_report_score_to_provider_fallback_success(mock_provider):
    # Setup
    mock_provider.report_score.return_value = ProviderSetResult(
        success=False,
        set_id="set_1",
        error_message="Scores cannot be reported"
    )

    mock_provider.report_winner_only.return_value = ProviderSetResult(
        success=True,
        set_id="set_1",
        error_message=None
    )

    # Execute
    result = await report_score_to_provider(
        set_id="set_1",
        winner_id="p1",
        p1_id="p1",
        p2_id="p2",
        p1_score=2,
        p2_score=1,
        provider=mock_provider
    )

    # Assert
    assert result.success is True
    assert result.set_id == "set_1"

    mock_provider.report_score.assert_called_once_with(
        set_id="set_1",
        winner_id="p1",
        entrant1_id="p1",
        entrant2_id="p2",
        entrant1_score=2,
        entrant2_score=1,
    )
    mock_provider.report_winner_only.assert_called_once_with("set_1", "p1")

@pytest.mark.asyncio
async def test_report_score_to_provider_fallback_failure(mock_provider):
    # Setup
    mock_provider.report_score.return_value = ProviderSetResult(
        success=False,
        set_id="set_1",
        error_message="Scores cannot be reported"
    )

    mock_provider.report_winner_only.return_value = ProviderSetResult(
        success=False,
        set_id="set_1",
        error_message="Winner cannot be reported either"
    )

    # Execute
    result = await report_score_to_provider(
        set_id="set_1",
        winner_id="p1",
        p1_id="p1",
        p2_id="p2",
        p1_score=2,
        p2_score=1,
        provider=mock_provider
    )

    # Assert
    assert result.success is False
    assert result.set_id == "set_1"
    assert "Full report failed: Scores cannot be reported" in result.error_message
    assert "Winner-only fallback also failed: Winner cannot be reported either" in result.error_message

    mock_provider.report_score.assert_called_once_with(
        set_id="set_1",
        winner_id="p1",
        entrant1_id="p1",
        entrant2_id="p2",
        entrant1_score=2,
        entrant2_score=1,
    )
    mock_provider.report_winner_only.assert_called_once_with("set_1", "p1")

@pytest.mark.asyncio
@patch('backend.core.score_reporting.get_provider_for_tournament', new_callable=AsyncMock)
async def test_report_score_to_provider_implicit_provider(mock_get_provider, mock_provider):
    # Setup
    mock_get_provider.return_value = mock_provider
    mock_provider.report_score.return_value = ProviderSetResult(
        success=True,
        set_id="set_1",
        error_message=None
    )

    # Execute (without passing provider)
    result = await report_score_to_provider(
        set_id="set_1",
        winner_id="p1",
        p1_id="p1",
        p2_id="p2",
        p1_score=2,
        p2_score=1
    )

    # Assert
    assert result.success is True
    mock_get_provider.assert_awaited_once_with("score/event", "workspace-score")
    mock_provider.report_score.assert_called_once()
