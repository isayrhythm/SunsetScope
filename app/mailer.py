from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage
from typing import Dict, List, Optional

from app.config import Settings
from app.provider import Forecast
from app.sunsethue import MODEL


class Mailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_confirmation(
        self, recipient: str, cities: List[str], token: str, unsubscribe_token: str,
    ) -> None:
        city_label = "、".join(cities)
        url = "%s/confirm/%s" % (self.settings.base_url, token)
        unsubscribe_url = "%s/unsubscribe/%s" % (self.settings.base_url, unsubscribe_token)
        self._send(
            recipient,
            "确认你的 SunsetScope 订阅",
            "你订阅了 %s 的朝霞/晚霞预测。请打开以下链接确认：\n%s\n\n如非本人操作或想取消：\n%s"
            % (city_label, url, unsubscribe_url),
            "<p>你订阅了 <strong>%s</strong> 的朝霞/晚霞预测。</p><p><a href=\"%s\">确认订阅</a></p><p><a href=\"%s\">取消这项订阅</a></p>"
            % (html.escape(city_label), html.escape(url), html.escape(unsubscribe_url)),
        )

    def send_unsubscribe_management(self, recipient: str, subscriptions: List[Dict]) -> None:
        plain_rows = []
        html_rows = []
        for subscription in subscriptions:
            event_name = "朝霞" if subscription["event"] == "rise" else "晚霞"
            models = subscription.get("models") or [subscription.get("model")]
            cities = subscription.get("cities") or [subscription.get("city")]
            label = "%s · %s · %s" % ("、".join(cities), event_name, " + ".join(models))
            url = "%s/unsubscribe/%s" % (self.settings.base_url, subscription["unsubscribe_token"])
            plain_rows.append("%s\n%s" % (label, url))
            html_rows.append(
                '<li><strong>{}</strong><br><a href="{}">取消这项订阅</a></li>'.format(
                    html.escape(label), html.escape(url),
                )
            )
        self._send(
            recipient,
            "管理你的 SunsetScope 订阅",
            "以下是这个邮箱当前可取消的订阅：\n\n%s" % "\n\n".join(plain_rows),
            "<p>以下是这个邮箱当前可取消的订阅：</p><ul>%s</ul>" % "".join(html_rows),
        )

    def send_source_failure_report(self, recipient: str, errors: List[str]) -> None:
        plain_rows = "\n".join("- %s" % item for item in errors)
        html_rows = "".join("<li>%s</li>" % html.escape(item) for item in errors)
        self._send(
            recipient,
            "SunsetScope 预测数据源故障报告",
            "定时预测任务访问预测数据源时发生故障：\n\n%s" % plain_rows,
            "<h2>预测数据源故障</h2><p>定时预测任务访问预测数据源时发生故障：</p><ul>%s</ul>"
            % html_rows,
        )

    def send_alerts(
        self, recipient: str, forecasts: List[Forecast], threshold: float,
        trigger_mode: str, unsubscribe_token: str,
        missing_models: Optional[Dict[str, str]] = None,
        model_thresholds: Optional[Dict[str, float]] = None,
        trigger_reason: Optional[str] = None,
    ) -> None:
        if not forecasts:
            raise ValueError("cannot send an alert without forecasts")
        primary = forecasts[0]
        event_name = "朝霞" if primary.event == "rise" else "晚霞"
        unsubscribe_url = "%s/unsubscribe/%s" % (self.settings.base_url, unsubscribe_token)
        subject = "%s %s预测达到订阅条件" % (primary.city, event_name)
        mode_name = "任一模型达到" if trigger_mode == "any" else "所有有数据的模型达到"
        model_thresholds = model_thresholds or {item.model: threshold for item in forecasts}
        thresholds_label = "；".join(
            "%s %s %s" % ("Sunsethue" if model == MODEL else model,
                ">" if model == MODEL and trigger_reason else "≥",
                "%.0f 分" % (value * 100) if model == MODEL else "鲜艳度 %.2f" % value)
            for model, value in model_thresholds.items()
        )
        plain_rows = "\n".join(
            "%s：%s %s，预计 %s，AOD %s，时次 %s"
            % ("Sunsethue" if item.model == MODEL else item.model,
               "质量" if item.model == MODEL else "鲜艳度",
               item.quality_text, item.event_time, item.aod_text, item.forecast_run)
            for item in forecasts
        )
        missing_models = missing_models or {}
        if missing_models:
            plain_rows += "\n" + "\n".join(
                "%s：%s" % ("Sunsethue" if model == MODEL else model, status) for model, status in missing_models.items()
            )
        source_models = {item.model for item in forecasts} | set(missing_models)
        source_urls = []
        if source_models - {MODEL}:
            source_urls.append("https://sunsetbot.top/")
        if MODEL in source_models:
            source_urls.append("https://sunsethue.com/")
        plain = "%s %s预测达到订阅条件（%s；%s）。\n\n%s\n\n数据来源：%s\n退订：%s" % (
            primary.city, event_name, mode_name, thresholds_label, plain_rows, "、".join(source_urls), unsubscribe_url,
        )
        table_rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape("Sunsethue" if item.model == MODEL else item.model), html.escape(item.quality_text),
                html.escape(item.event_time), html.escape(item.aod_text),
            ) for item in forecasts
        )
        table_rows += "".join(
            '<tr><td>{}</td><td>{}</td><td>—</td><td>—</td></tr>'.format(
                html.escape("Sunsethue" if model == MODEL else model), html.escape(status),
            ) for model, status in missing_models.items()
        )
        body = """<h2>{city} {event_name}提醒</h2>
<p>提醒原因：<strong>{reason}</strong>。</p>
<p>设置：{mode_name}；{thresholds_label}</p>
<table cellpadding="8" cellspacing="0" border="1"><thead><tr><th>模型 / 来源</th><th>鲜艳度 / 质量评分</th><th>预计时间</th><th>AOD</th></tr></thead><tbody>{rows}</tbody></table>
<p>数据来源：{sources}</p>
<p><a href="{unsubscribe}">管理或退订</a></p>""".format(
            city=html.escape(primary.city), event_name=event_name, mode_name=mode_name,
            thresholds_label=html.escape(thresholds_label), rows=table_rows, unsubscribe=html.escape(unsubscribe_url),
            sources="、".join('<a href="{0}">{0}</a>'.format(url) for url in source_urls),
            reason=html.escape(trigger_reason or "订阅条件达标"),
        )
        if trigger_reason:
            plain = "提醒原因：%s\n%s" % (trigger_reason, plain)
        self._send(recipient, subject, plain, body)

    def _send(self, recipient: str, subject: str, plain: str, body: str) -> None:
        self.settings.require_mail()
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(plain)
        message.add_alternative(body, subtype="html")
        with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as server:
            server.login(self.settings.smtp_user, self.settings.smtp_password)
            server.send_message(message)
