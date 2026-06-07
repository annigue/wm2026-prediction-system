from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings

router = APIRouter()


@router.post("/matches/{match_id}/predict")
async def predict_match_endpoint(match_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.prediction_engine import predict_match
    result = await predict_match(match_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Spiel nicht gefunden oder Teams unbekannt")
    await db.commit()
    return result


@router.post("/predict-all")
async def predict_all(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    if authorization and (authorization or "").replace("Bearer ", "").strip() != settings.admin_token:
        raise HTTPException(status_code=401, detail="Ungültiges Admin-Token")
    from app.services.prediction_engine import predict_all_scheduled
    count = await predict_all_scheduled(db)
    return {"status": "ok", "predictions_computed": count}
