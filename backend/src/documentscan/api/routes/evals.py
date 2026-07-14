from fastapi import APIRouter
router = APIRouter()
@router.get("/report")
async def get_eval_report(): return {"status": "clean"}
