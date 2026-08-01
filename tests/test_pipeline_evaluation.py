import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from src.db.session import DATABASE_URL
from scripts.evaluate_pipeline import run_pipeline_evaluation

@pytest.mark.asyncio
async def test_pipeline_ground_truth_evaluation():
    """
    CI Regression Test: Runs whole-pipeline evaluation against Session 17 synthetic dataset
    and asserts defensible quality thresholds. Fails the build if model quality regresses.
    """
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    async with TestAsyncSessionLocal() as db:
        results = await run_pipeline_evaluation(session=db)

    # 1. Detection Recall Gate (>= 75.0% / at least 3 of 4 ground truth events detected)
    assert results["detection_recall"] >= 0.75, (
        f"Pipeline detection_recall ({results['detection_recall']*100:.1f}%) dropped below minimum threshold (75.0%)"
    )

    # 2. Classification Type Accuracy Gate (>= 75.0% correct type classification)
    assert results["classification_accuracy"] >= 0.75, (
        f"Pipeline classification_accuracy ({results['classification_accuracy']*100:.1f}%) dropped below threshold (75.0%)"
    )

    # 3. False Positive Rate Gate (<= 10.0% false positive rate on untouched periods)
    assert results["false_positive_rate"] <= 0.10, (
        f"Pipeline false_positive_rate ({results['false_positive_rate']*100:.1f}%) exceeded maximum threshold (10.0%)"
    )

    # 4. Driver Attribution Accuracy Gate (>= 66.0% / at least 2 of 3 segment-concentrated events)
    assert results["driver_accuracy"] >= 0.66, (
        f"Pipeline driver_accuracy ({results['driver_accuracy']*100:.1f}%) dropped below threshold (66.0%)"
    )

    # 5. Uniform Level-Shift Proportionality Check (Asserts ~15% step shift across all segments)
    assert results["uniform_shift_proportionality"] is True, (
        "Level-shift uniform shift proportionality check failed: segment step changes deviated from baseline shares"
    )

    # 6. Forecast 12-Week Backtest MAPE Gate (<= 15.0% MAPE on held-out backtest)
    assert results["forecast_MAPE"] is not None and results["forecast_MAPE"] <= 0.15, (
        f"Forecast 12-week MAPE ({results['forecast_MAPE']*100:.2f}%) exceeded maximum threshold (15.0%)"
    )

    # 7. Prediction Band Interval Coverage Gate (Between 60.0% and 95.0% for [p10, p90] band)
    assert results["interval_coverage"] is not None and (0.60 <= results["interval_coverage"] <= 0.95), (
        f"Forecast interval_coverage ({results['interval_coverage']*100:.2f}%) outside expected target band (60.0% .. 95.0%)"
    )
