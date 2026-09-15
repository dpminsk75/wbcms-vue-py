from typing import Literal

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_user, require_company_admin
from backend.services import auth_service

router = APIRouter(prefix="/api/companies", tags=["companies"])


class CompanyCreateIn(BaseModel):
    name: str
    abbreviation: str | None = None
    inn: str | None = None
    seo_model: str | None = None
    seo_summary_model: str | None = None
    seo_summary_max_tokens: int | None = None
    seo_daily_limit: int | None = None
    seo_desc_min: int | None = None
    seo_desc_max: int | None = None
    seo_anti_spam_days: int | None = None
    seo_openrouter_key: str | None = None
    seo_openrouter_referer: str | None = None
    seo_openrouter_title: str | None = None
    seo_prompt: str | None = None
    seo_competitor_prompt: str | None = None
    seo_summary_prompt: str | None = None


class MemberInviteIn(BaseModel):
    email: str
    role: Literal["admin", "member", "viewer"] = "member"
    # Явные пермы сверх базы по роли (v2): только из того, что есть у приглашающего.
    perms: list[str] = []


class CompanyUpdateIn(BaseModel):
    name: str | None = None
    abbreviation: str | None = None
    inn: str | None = None
    api_key: str | None = None
    is_active: bool | None = None
    fbs_deduct_enabled: bool | None = None
    fbs_deduct_test: bool | None = None
    seo_model: str | None = None
    seo_summary_model: str | None = None
    seo_summary_max_tokens: int | None = None
    seo_daily_limit: int | None = None
    seo_desc_min: int | None = None
    seo_desc_max: int | None = None
    seo_anti_spam_days: int | None = None
    seo_openrouter_key: str | None = None
    seo_openrouter_referer: str | None = None
    seo_openrouter_title: str | None = None
    seo_prompt: str | None = None
    seo_competitor_prompt: str | None = None
    seo_summary_prompt: str | None = None


class MemberUpdateIn(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"]
    status: Literal["active", "blocked", "invited"] = "active"


async def _make_unique_username(db: AsyncSession, email: str) -> str:
    local = email.split("@", 1)[0].strip().lower()
    username = "".join(ch if ch.isalnum() or ch in ("_", ".") else "_" for ch in local)[:50].strip(".")
    username = username or "user"
    candidate = username
    suffix = 2
    while await auth_service.get_user_by_username(db, candidate):
        candidate = f"{username[:45]}_{suffix}"
        suffix += 1
    return candidate


@router.get("")
async def companies(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await auth_service.get_user_companies(db, user["id"])


@router.post("")
async def create_company(
    payload: CompanyCreateIn, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    # Self-service (2026-09-15): любую компанию может создать любой залогиненный,
    # создатель становится owner. Было require_admin — owner не мог добавить себе компанию.
    try:
        # deps уже открыли autobegin-транзакцию SELECT'ами — сбрасываем перед db.begin()
        await db.rollback()
        async with db.begin():
            company = await auth_service.create_company(
                db,
                owner_id=user["id"],
                name=payload.name,
                abbreviation=payload.abbreviation,
                inn=payload.inn,
                seo_model=payload.seo_model,
                seo_summary_model=payload.seo_summary_model,
                seo_summary_max_tokens=payload.seo_summary_max_tokens,
                seo_daily_limit=payload.seo_daily_limit,
                seo_desc_min=payload.seo_desc_min,
                seo_desc_max=payload.seo_desc_max,
                seo_anti_spam_days=payload.seo_anti_spam_days,
                seo_openrouter_key=payload.seo_openrouter_key,
                seo_openrouter_referer=payload.seo_openrouter_referer,
                seo_openrouter_title=payload.seo_openrouter_title,
                seo_prompt=payload.seo_prompt,
                seo_competitor_prompt=payload.seo_competitor_prompt,
                seo_summary_prompt=payload.seo_summary_prompt,
            )
            return auth_service.public_company(company)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="company creation failed")
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{company_id}", response_model=None)
async def get_company(company_id: int = Path(..., ge=1), db: AsyncSession = Depends(get_db), user: dict = Depends(require_company_admin)):
    # Полная запись для формы редактирования (yii2 company/update). Секреты — только менеджерам.
    company = await auth_service.get_company_full(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="company not found")
    return company


@router.patch("/{company_id}")
async def update_company(
    company_id: int = Path(..., ge=1),
    payload: CompanyUpdateIn = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_company_admin),
):
    # Порт yii2 CompanyController update: имя/ИНН/API-ключ/SEO. Секреты (api_key,
    # seo_openrouter_key) принимаются, но наружу через public_company не отдаются.
    # Гейты полей (п.4): FBS-блок — только manageFbsStocks, SEO-блок — только viewSeo,
    # global_admin — всё. Фронт такие поля не показывает, бэк перестраховывает.
    data = payload.model_dump(exclude_unset=True)
    if not await auth_service.is_global_admin(db, user["id"]):
        perms = await auth_service.effective_perms(db, user["id"])
        if any(k in data and data[k] is not None for k in auth_service.FBS_FIELDS) and "manageFbsStocks" not in perms:
            raise HTTPException(status_code=403, detail="fbs fields require manageFbsStocks")
        if any(k in data and data[k] is not None for k in auth_service.SEO_FIELDS) and "viewSeo" not in perms:
            raise HTTPException(status_code=403, detail="seo fields require viewSeo")
    try:
        await db.rollback()  # сбрасываем autobegin от deps/gates перед begin (B6)
        async with db.begin():
            company = await auth_service.update_company(db, company_id, data)
            return auth_service.public_company(company)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400 if str(exc) != "company not found" else 404, detail=str(exc))


@router.get("/{company_id}/members")
async def get_members(company_id: int = Path(..., ge=1), db: AsyncSession = Depends(get_db), user: dict = Depends(require_company_admin)):
    company = await auth_service.get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="company not found")
    return {"company": auth_service.public_company(company), "members": await auth_service.get_company_members(db, company_id)}


@router.post("/{company_id}/members")
async def invite_member(company_id: int = Path(..., ge=1), payload: MemberInviteIn = Body(...), db: AsyncSession = Depends(get_db), user: dict = Depends(require_company_admin)):
    try:
        # см. create_company выше: сбрасываем autobegin-транзакцию от deps перед db.begin()
        await db.rollback()
        async with db.begin():
            company = await auth_service.get_company_by_id(db, company_id)
            if not company:
                raise HTTPException(status_code=404, detail="company not found")

            target = await auth_service.get_user_by_email(db, payload.email)
            if target and target.get("blocked_at") is not None:
                raise HTTPException(status_code=403, detail="user is blocked")
            if target:
                member = await auth_service.get_company_member(db, company_id, target["id"])
                if member and member.get("status") == "active":
                    raise HTTPException(status_code=409, detail="user is already an active company member")
            else:
                target = await auth_service.create_user(
                    db,
                    await _make_unique_username(db, payload.email),
                    payload.email,
                    secrets.token_urlsafe(12),
                )

            # v2: явные пермы — валидируем по выдающему (делегирование), выдаём сразу
            # предсозданному/существующему и кладём в токен (применятся при регистрации).
            try:
                granted = await auth_service.validate_grant(db, user["id"], payload.perms)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            if granted:
                await auth_service.grant_perms(db, target["id"], granted)

            await auth_service.upsert_company_member(
                db,
                company_id,
                target["id"],
                payload.role,
                "invited",
                user["id"],
            )
            token = await auth_service.create_user_invite_token(
                db,
                created_by=user["id"],
                company_id=company_id,
                email=payload.email or "",
                role=payload.role,
                perms=granted,
            )
            return {
                "invite_token": token,
                # дефолтный срок user-токена 7 дней (см. create_user_invite_token) — раньше отдавался utcnow()
                "expires_at": (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat() + "Z",
                "company": auth_service.public_company(company),
                "member": {
                    "user": auth_service.public_user(target),
                    "role": payload.role,
                    "status": "invited",
                },
            }
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


class MemberPermsIn(BaseModel):
    add: list[str] = []
    remove: list[str] = []


@router.patch("/{company_id}/members/{user_id}/perms")
async def update_member_perms(
    company_id: int = Path(..., ge=1),
    user_id: int = Path(..., ge=1),
    payload: MemberPermsIn = Body(...),
    db: AsyncSession = Depends(get_db),
    actor: dict = Depends(require_company_admin),
):
    # Добавление/снятие явных пермов члену своей компании. add — только делегированное
    # (validate_grant), remove — только из GRANTABLE_PERMS (роли снимает global через /admin).
    try:
        await db.rollback()
        async with db.begin():
            member = await auth_service.get_company_member(db, company_id, user_id)
            if not member:
                raise HTTPException(status_code=404, detail="member not found")
            try:
                added = await auth_service.validate_grant(db, actor["id"], payload.add)
                removable = [p for p in (payload.remove or []) if p in auth_service.GRANTABLE_PERMS]
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            if added:
                await auth_service.grant_perms(db, user_id, added)
            if removable:
                await auth_service.revoke_perms(db, user_id, removable)
            items = await auth_service.get_user_explicit_items(db, user_id)
            return {"company_id": company_id, "id": user_id, "perms": [i["name"] for i in items]}
    except HTTPException:
        raise


@router.patch("/{company_id}/members/{user_id}/password")
async def set_member_password(
    company_id: int = Path(..., ge=1),
    user_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    actor: dict = Depends(require_company_admin),
):
    # Смена пароля члену СВОЕЙ компании (owner/admin). Чужим компаниям — 403/404 через guard+проверку.
    try:
        await db.rollback()
        async with db.begin():
            member = await auth_service.get_company_member(db, company_id, user_id)
            if not member:
                raise HTTPException(status_code=404, detail="member not found")
            try:
                await auth_service.update_user_password(db, user_id, (payload or {}).get("password") or "")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            return {"company_id": company_id, "id": user_id}
    except HTTPException:
        raise


@router.patch("/{company_id}/members/{user_id}")
async def update_member(company_id: int = Path(..., ge=1), user_id: int = Path(..., ge=1), payload: MemberUpdateIn = Body(...), db: AsyncSession = Depends(get_db), actor: dict = Depends(require_company_admin)):
    try:
        # см. create_company выше: сбрасываем autobegin-транзакцию от deps перед db.begin()
        await db.rollback()
        async with db.begin():
            if not await auth_service.get_company_by_id(db, company_id):
                raise HTTPException(status_code=404, detail="company not found")
            await auth_service.update_company_member(db, company_id, user_id, payload.role, payload.status)
            member = await auth_service.get_company_member(db, company_id, user_id)
            user = await auth_service.get_user_by_id(db, user_id)
            return {"company_id": company_id, "member": {"user": auth_service.public_user(user), **member}}
    except HTTPException:
        raise
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{company_id}/members/{user_id}")
async def delete_member(company_id: int = Path(..., ge=1), user_id: int = Path(..., ge=1), db: AsyncSession = Depends(get_db), actor: dict = Depends(require_company_admin)):
    try:
        # см. create_company выше: сбрасываем autobegin-транзакцию от deps перед db.begin()
        await db.rollback()
        async with db.begin():
            if not await auth_service.get_company_by_id(db, company_id):
                raise HTTPException(status_code=404, detail="company not found")
            await auth_service.delete_company_member(db, company_id, user_id)
            return {"deleted": True}
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
