"""Authorization dependencies for FastAPI."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services import auth_service


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    payload = auth_service.decode_token(token)
    if not payload or not payload.get("sub"):
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = await auth_service.get_user_by_id(db, user_id)
    if not user or user.get("blocked_at") is not None:
        return None
    pp = await auth_service.get_user_perms(db, user_id)
    user["roles"] = pp["roles"]
    user["perms"] = pp["all"]
    return user


async def get_current_user(request: Request, user: dict | None = Depends(get_optional_user)) -> dict:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    roles = set(user.get("roles", [])) | set(user.get("perms", []))
    if "global_admin" not in roles and "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нужна роль admin/global_admin")
    return user


async def require_seo(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Доступ к SEO/конкурентам: global_admin/admin или явный перм viewSeo (порт matchCallback viewSeo|admin)."""
    if await auth_service.is_global_admin(db, user["id"]):
        return user
    if "viewSeo" in await auth_service.effective_perms(db, user["id"]):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="seo access denied (need viewSeo)")


async def _resolve_company_id(request: Request) -> int | None:
    cid = request.path_params.get("company_id")
    if cid is not None:
        try:
            return int(cid)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid company_id in path")
    q = request.query_params.get("company_id")
    if q:
        try:
            return int(q)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid company_id query")
    header_value = request.headers.get("X-Company-Id")
    if header_value and header_value != "all":
        try:
            return int(header_value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid X-Company-Id")
    return None


async def _validate_company_access(db: AsyncSession, user_id: int, company_id: int | None) -> int | None:
    if company_id is None:
        if await auth_service.is_global_admin(db, user_id):
            return None
        companies = await auth_service.get_user_companies(db, user_id)
        if len(companies) == 1:
            return companies[0]["id"]
        if not companies:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступных компаний")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_id is required")
    if await auth_service.is_global_admin(db, user_id):
        company = await auth_service.get_company_by_id(db, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="company not found")
        return company_id
    member = await auth_service.get_company_member(db, company_id, user_id)
    if not member or member.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="company access denied")
    return company_id


async def get_current_company(
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> int | None:
    selected = await _resolve_company_id(request)
    return await _validate_company_access(db, user["id"], selected)


async def require_company_admin(
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    company_id = await _resolve_company_id(request)
    if company_id is not None and await auth_service.can_manage_company(db, user["id"], company_id):
        return user
    if company_id is None and await auth_service.is_global_admin(db, user["id"]):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="company admin access denied")


async def require_company_owner(
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    company_id = await _resolve_company_id(request)
    if company_id is None and await auth_service.is_global_admin(db, user["id"]):
        return user
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_id required")
    if await auth_service.is_global_admin(db, user["id"]):
        return user
    member = await auth_service.get_company_member(db, company_id, user["id"])
    if not member or member.get("status") != "active" or member.get("role") != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="company owner access denied")
    return user
