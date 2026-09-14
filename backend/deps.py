"""Зависимости авторизации для FastAPI — замена Yii AccessControl + CompanyManager."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services import auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    if not token:
        return None
    payload = auth_service.decode_token(token)
    if not payload or not payload.get("sub"):
        return None
    try:
        uid = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = await auth_service.get_user_by_id(db, uid)
    if not user or user.get("blocked_at") is not None:
        return None
    pp = await auth_service.get_user_perms(db, uid)
    user["roles"] = pp["roles"]
    user["perms"] = pp["all"]
    return user


async def get_current_user(user: dict | None = Depends(get_optional_user)) -> dict:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    perms = set(user.get("perms", [])) | set(user.get("roles", []))
    if "admin" not in perms:
        raise HTTPException(status_code=403, detail="Нужна роль admin")
    return user
