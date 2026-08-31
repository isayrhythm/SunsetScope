from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.captcha import CaptchaService
from app.config import ROOT, Settings
from app.mailer import Mailer
from app.provider import ProviderError, SunsetBotProvider
from app.rate_limit import RateLimiter
from app.service import SubscriptionService
from app.store import JsonStore


settings = Settings.from_env()
provider = SunsetBotProvider(settings.source_timeout)
service = SubscriptionService(JsonStore(settings.store_path), provider, Mailer(settings))
rate_limiter = RateLimiter()
captcha_service = CaptchaService(settings.captcha_ttl)

app = FastAPI(title="SunsetScope", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/cities")
def cities(q: str = ""):
    try:
        return {"cities": provider.suggest_cities(q)}
    except ProviderError as exc:
        return JSONResponse({"message": str(exc)}, status_code=502)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.get("/api/captcha")
def captcha(request: Request):
    ip = client_ip(request)
    if not rate_limiter.allow([("captcha:issue:%s" % ip, settings.captcha_issue_limit, 600)]):
        return JSONResponse(
            {"message": "验证码获取过于频繁，请稍后再试。"}, status_code=429,
            headers={"Retry-After": "600"},
        )
    challenge = captcha_service.create(ip)
    return JSONResponse(
        {"captcha_id": challenge.challenge_id, "image": challenge.data_url},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


def verify_captcha(request: Request, payload: Dict[str, Any]):
    ip = client_ip(request)
    if not rate_limiter.allow([("captcha:attempt:%s" % ip, settings.captcha_attempt_limit, 600)]):
        return JSONResponse(
            {"message": "验证码尝试过于频繁，请稍后再试。"}, status_code=429,
            headers={"Retry-After": "600"},
        )
    if not captcha_service.verify(
        str(payload.get("captcha_id", "")),
        str(payload.get("captcha_answer", "")),
        ip,
    ):
        return JSONResponse({"message": "验证码错误或已过期，请重新输入。"}, status_code=422)
    return None


def allow_mail_request(request: Request, email: str) -> bool:
    ip = client_ip(request)
    window = settings.rate_limit_window
    return rate_limiter.allow([
        ("mail:ip:%s" % ip, settings.rate_limit_ip, window),
        ("mail:email:%s" % email.strip().lower(), settings.rate_limit_email, window),
    ])


@app.post("/api/subscriptions")
def subscriptions(request: Request, payload: Dict[str, Any]):
    try:
        captcha_error = verify_captcha(request, payload)
        if captcha_error is not None:
            return captcha_error
        email = str(payload.get("email", ""))
        if not allow_mail_request(request, email):
            return JSONResponse(
                {"message": "请求过于频繁，请稍后再试。"}, status_code=429,
                headers={"Retry-After": str(settings.rate_limit_window)},
            )
        result = service.subscribe(payload)
        if result["status"] == "active":
            return {"message": "这个订阅已经生效，无需重复确认。"}
        return {"message": "确认邮件已发送，请打开邮件完成订阅。"}
    except ValueError as exc:
        return JSONResponse({"message": str(exc)}, status_code=422)
    except ProviderError as exc:
        return JSONResponse({"message": str(exc)}, status_code=502)
    except RuntimeError as exc:
        return JSONResponse({"message": str(exc)}, status_code=503)


@app.post("/api/unsubscribe-requests")
def unsubscribe_requests(request: Request, payload: Dict[str, Any]):
    try:
        captcha_error = verify_captcha(request, payload)
        if captcha_error is not None:
            return captcha_error
        email = str(payload.get("email", ""))
        if not allow_mail_request(request, email):
            return JSONResponse(
                {"message": "请求过于频繁，请稍后再试。"}, status_code=429,
                headers={"Retry-After": str(settings.rate_limit_window)},
            )
        service.request_unsubscribe(email)
        return {"message": "如果该邮箱存在订阅，退订管理邮件已发送，请查收。"}
    except ValueError as exc:
        return JSONResponse({"message": str(exc)}, status_code=422)
    except RuntimeError as exc:
        return JSONResponse({"message": str(exc)}, status_code=503)


@app.get("/confirm/{token}", response_class=HTMLResponse)
def confirm(request: Request, token: str):
    ok = service.confirm(token)
    return templates.TemplateResponse(
        "message.html",
        {"request": request, "title": "订阅已确认" if ok else "确认链接无效", "ok": ok,
         "message": "以后达到阈值时，我们会给你发送邮件。" if ok else "链接无效或来自修复前的旧版本。若第一次打开曾显示成功，订阅已经生效；也可以回到首页重复提交检查。"},
        status_code=200 if ok else 404,
    )


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(request: Request, token: str):
    subscription = service.find_by_unsubscribe_token(token)
    return templates.TemplateResponse(
        "unsubscribe.html",
        {"request": request, "subscription": subscription, "token": token},
        status_code=200 if subscription else 404,
    )


@app.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(request: Request, token: str):
    ok = service.unsubscribe(token)
    return templates.TemplateResponse(
        "message.html",
        {"request": request, "title": "已退订" if ok else "退订链接无效", "ok": ok,
         "message": "该订阅不会再收到提醒。" if ok else "没有找到对应的订阅。"},
        status_code=200 if ok else 404,
    )
