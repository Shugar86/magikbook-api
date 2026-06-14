"""Contract tests for Artist Glory: portfolio, feed author fields, my-uploads battles."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import BattleVote, Prompt, User
from src.routes.auth import create_access_token


@pytest.mark.asyncio
async def test_portfolio_unknown_user_404(client: AsyncClient) -> None:
    """GET portfolio for missing username returns 404."""
    resp = await client.get("/api/users/__no_such_user_99__/portfolio")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_only_published_media(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Portfolio lists only image/video with approved or published moderation."""
    user = User(id="u-portfolio-1", username="artist_portfolio_test", email=None)
    db_session.add(user)
    await db_session.commit()

    db_session.add_all(
        [
            Prompt(
                id="p-text-pub",
                title="t",
                prompt_text="x" * 30,
                media_type="text",
                category="cat",
                author_id=user.id,
                moderation_status="published",
            ),
            Prompt(
                id="p-img-pending",
                title="t2",
                prompt_text="x" * 30,
                media_type="image",
                category="cat",
                author_id=user.id,
                moderation_status="pending",
            ),
            Prompt(
                id="p-img-pub",
                title="t3",
                prompt_text="x" * 30,
                media_type="image",
                category="cat",
                author_id=user.id,
                moderation_status="published",
                elo_rating=1300,
            ),
            Prompt(
                id="p-img-rej",
                title="t4",
                prompt_text="x" * 30,
                media_type="image",
                category="cat",
                author_id=user.id,
                moderation_status="rejected",
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get("/api/users/artist_portfolio_test/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["username"] == "artist_portfolio_test"
    ids = [p["id"] for p in data["prompts"]]
    assert ids == ["p-img-pub"]
    assert all(p["author_username"] == "artist_portfolio_test" for p in data["prompts"])


@pytest.mark.asyncio
async def test_feed_prompt_has_author_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Feed items include author_username when prompt has author."""
    user = User(id="u-feed-author", username="feed_author_u", email=None)
    db_session.add(user)
    await db_session.commit()
    p = Prompt(
        id="p-feed-auth",
        title="tf",
        prompt_text="y" * 30,
        media_type="image",
        category="cat",
        author_id=user.id,
        moderation_status="published",
    )
    db_session.add(p)
    await db_session.commit()

    resp = await client.get("/api/prompts/feed?media_type=image&page_size=50")
    assert resp.status_code == 200
    data = resp.json()
    match = next((x for x in data["prompts"] if x["id"] == "p-feed-auth"), None)
    assert match is not None
    assert match.get("author_username") == "feed_author_u"


@pytest.mark.asyncio
async def test_my_uploads_includes_battle_aggregates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """my-uploads returns battle_wins, battle_total_votes, win_percentage."""
    user = User(id="u-battle-tab", username="battle_user", email=None)
    db_session.add(user)
    await db_session.commit()
    db_session.add_all(
        [
            Prompt(
                id="p-battle-1",
                title="tb",
                prompt_text="z" * 30,
                media_type="image",
                category="cat",
                author_id=user.id,
                moderation_status="pending",
            ),
            Prompt(
                id="p-other",
                title="other",
                prompt_text="z" * 30,
                media_type="image",
                category="cat",
                author_id=user.id,
                moderation_status="published",
            ),
        ]
    )
    await db_session.commit()

    for _ in range(3):
        db_session.add(
            BattleVote(
                winner_id="p-battle-1",
                loser_id="p-other",
                session_token=f"sv{_}",
            )
        )
    for i in range(2):
        db_session.add(
            BattleVote(
                winner_id="p-other",
                loser_id="p-battle-1",
                session_token=f"lv{i}",
            )
        )
    await db_session.commit()

    token = create_access_token(data={"sub": user.id})
    resp = await client.get(
        "/api/prompts/my-uploads",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    row = next(p for p in data["prompts"] if p["id"] == "p-battle-1")
    assert row["battle_wins"] == 3
    assert row["battle_total_votes"] == 5
    assert row["win_percentage"] == 60.0
    assert "elo_rating" in row
    assert "remixes" in row
