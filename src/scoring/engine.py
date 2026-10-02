"""Multi-factor scoring coordinator and database persistence engine."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import AssetClass, Timeframe
from src.database.models import Asset, Feature, HolderMetric, OnchainMetric, Score, Tokenomics
from src.scoring.altcoin import AltcoinScorer
from src.scoring.base import BaseScorer, ScoreCard
from src.scoring.core import CoreScorer
from src.scoring.meme import MemeScorer
from src.scoring.smallcap import SmallCapScorer
from src.utils.logging import get_logger

logger = get_logger("scoring.engine")

# Registry of asset-class scorers
_SCORERS: dict[str, BaseScorer] = {
    AssetClass.CORE.value: CoreScorer(),
    AssetClass.ALTCOIN.value: AltcoinScorer(),
    AssetClass.MID_CAP.value: AltcoinScorer(),
    AssetClass.SMALL_CAP.value: SmallCapScorer(),
    AssetClass.MEME.value: MemeScorer(),
}


def get_scorer_for_asset(asset_class: str) -> BaseScorer:
    """Return appropriate scoring model instance for an asset class."""
    return _SCORERS.get(asset_class.upper(), _SCORERS[AssetClass.ALTCOIN.value])


async def score_single_asset(
    session: AsyncSession,
    asset_id: str,
    timeframe: Timeframe = Timeframe.H1,
    custom_weights: dict[str, float] | None = None,
) -> ScoreCard | None:
    """Score a single cryptocurrency asset using its metadata, latest features, and fundamentals."""
    # 1. Fetch asset metadata
    asset_res = await session.execute(select(Asset).where(Asset.id == asset_id))
    asset = asset_res.scalar_one_or_none()
    if not asset:
        logger.warning("asset_not_found_for_scoring", asset_id=asset_id)
        return None

    # 2. Fetch latest features
    feat_res = await session.execute(
        select(Feature)
        .where(Feature.asset_id == asset_id, Feature.timeframe == timeframe.value)
        .order_by(desc(Feature.time))
        .limit(1)
    )
    features = feat_res.scalar_one_or_none()
    if not features:
        logger.warning("features_not_found_for_scoring", asset_id=asset_id, timeframe=timeframe.value)
        return None

    # 3. Optional tokenomics, onchain, holder metrics
    tok_res = await session.execute(select(Tokenomics).where(Tokenomics.asset_id == asset_id))
    tokenomics = tok_res.scalar_one_or_none()

    onchain_res = await session.execute(
        select(OnchainMetric)
        .where(OnchainMetric.asset_id == asset_id)
        .order_by(desc(OnchainMetric.time))
        .limit(1)
    )
    onchain = onchain_res.scalar_one_or_none()

    holder_res = await session.execute(
        select(HolderMetric)
        .where(HolderMetric.asset_id == asset_id)
        .order_by(desc(HolderMetric.time))
        .limit(1)
    )
    holder_metrics = holder_res.scalar_one_or_none()

    # 4. Score with specialized model
    scorer = get_scorer_for_asset(asset.asset_class)
    card = scorer.calculate_score(
        asset_id=asset.id,
        features=features,
        tokenomics=tokenomics,
        onchain=onchain,
        holder_metrics=holder_metrics,
        weights=custom_weights,
    )

    # 5. Persist to database `scores` table
    score_time = features.time
    existing_res = await session.execute(
        select(Score).where(
            Score.time == score_time,
            Score.asset_id == asset.id,
            Score.model_type == scorer.model_type,
        )
    )
    db_score = existing_res.scalar_one_or_none()

    breakdown_data = {
        name: {
            "name": comp.name,
            "score": comp.score,
            "weight": comp.weight,
            "contribution": comp.contribution,
        }
        for name, comp in card.components.items()
    }
    penalties_data = [
        {"flag": p.flag, "deduction": p.deduction, "reason": p.reason}
        for p in card.penalties
    ]
    breakdown_data["_penalties"] = penalties_data
    breakdown_data["_summary"] = card.explainability_summary
    breakdown_data["_partial_data"] = card.partial_data
    breakdown_data["_missing_inputs"] = card.missing_inputs
    breakdown_data["_model_version"] = card.model_version

    if not db_score:
        db_score = Score(
            time=score_time,
            asset_id=asset.id,
            model_type=scorer.model_type,
            opportunity_score=card.opportunity_score,
            quality_score=card.quality_score,
            risk_score=card.risk_score,
            trend_score=card.trend_score,
            momentum_score=card.momentum_score,
            relative_strength_score=card.relative_strength_score,
            liquidity_score=card.liquidity_score,
            breakdown_json=breakdown_data,
            risk_flags=card.risk_flags,
        )
        session.add(db_score)
    else:
        db_score.opportunity_score = card.opportunity_score
        db_score.quality_score = card.quality_score
        db_score.risk_score = card.risk_score
        db_score.trend_score = card.trend_score
        db_score.momentum_score = card.momentum_score
        db_score.relative_strength_score = card.relative_strength_score
        db_score.liquidity_score = card.liquidity_score
        db_score.breakdown_json = breakdown_data
        db_score.risk_flags = card.risk_flags

    await session.commit()
    logger.info(
        "asset_scored_successfully",
        asset=asset.id,
        model=scorer.model_type,
        opportunity=card.opportunity_score,
    )
    return card


async def score_universe(
    session: AsyncSession,
    timeframe: Timeframe = Timeframe.H1,
) -> list[ScoreCard]:
    """Score all active assets in the database and return ranking sorted by Opportunity Score."""
    res = await session.execute(select(Asset).where(Asset.is_active.is_(True)))
    assets = res.scalars().all()

    cards: list[ScoreCard] = []
    for asset in assets:
        card = await score_single_asset(session, asset.id, timeframe=timeframe)
        if card:
            cards.append(card)

    cards.sort(key=lambda c: c.opportunity_score, reverse=True)
    logger.info("universe_scored_and_ranked", total=len(cards))
    return cards
