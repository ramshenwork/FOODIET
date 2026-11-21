"""Table QR codes and the public, server-rendered menu page."""
import io
import uuid
from pathlib import Path

import segno
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.settings import get_settings
from app.services.businesses import service as businesses
from app.services.menus import service as menus
from app.services.qr.schemas import QrOut

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=select_autoescape(["html"]))


def public_url(code: str) -> str:
    return f"{get_settings().APP_BASE_URL.rstrip('/')}/q/{code}"


async def qr_for_branch(session: AsyncSession, user_id: uuid.UUID, branch_id: uuid.UUID) -> QrOut:
    branch = await businesses.branch_of_member(session, user_id, branch_id)
    url = public_url(branch.code)
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=10, border=2, dark="#101814", light="#ffffff", xmldecl=False)
    return QrOut(branch_code=branch.code, url=url, svg=buf.getvalue().decode())


async def public_menu_html(session: AsyncSession, code: str, ip: str) -> tuple[int, str]:
    rate_limit.check(f"qr-ip:{ip}", limit=60, window_seconds=60)
    rate_limit.check(f"qr-code:{code}", limit=600, window_seconds=60)
    s = get_settings()
    branch = await businesses.branch_by_code(session, code)
    if branch is None:
        return 404, _env.get_template("not_found.html").render(app_name=s.APP_NAME)
    menu = await menus.menu_out(session, branch.business_id, branch, published_only=True)
    sections = [(c.name, c.items) for c in menu.categories if c.items]
    if menu.uncategorised:
        sections.append(("More dishes" if sections else "Menu", menu.uncategorised))
    # A subscription started from this page is credited to the outlet (used by billing in phase 5).
    subscribe_url = f"{s.APP_BASE_URL.rstrip('/')}/?ref={branch.code}"
    return 200, _env.get_template("menu.html").render(app_name=s.APP_NAME, branch=branch, sections=sections,
                                                      subscribe_url=subscribe_url)
