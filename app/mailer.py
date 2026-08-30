from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage
from typing import List

from app.config import Settings
from app.provider import Forecast


class Mailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_confirmation(self, recipient: str, city: str, token: str) -> None:
        url = "%s/confirm/%s" % (self.settings.base_url, token)
        self._send(
            recipient,
            "确认你的 SunsetScope 订阅",
            "你订阅了 %s 的朝霞/晚霞预测。请打开以下链接确认：\n%s" % (city, url),
            "<p>你订阅了 <strong>%s</strong> 的朝霞/晚霞预测。</p><p><a href=\"%s\">确认订阅</a></p>"
            % (html.escape(city), html.escape(url)),
        )

    def send_alerts(
        self, recipient: str, forecasts: List[Forecast], threshold: float,
        trigger_mode: str, unsubscribe_token: str,
    ) -> None:
        if not forecasts:
            raise ValueError("cannot send an alert without forecasts")
        primary = max(forecasts, key=lambda item: item.quality)
        event_name = "朝霞" if primary.event == "rise" else "晚霞"
        unsubscribe_url = "%s/unsubscribe/%s" % (self.settings.base_url, unsubscribe_token)
        subject = "%s %s预测达到 %.2f" % (primary.city, event_name, primary.quality)
        mode_name = "任一模型达到" if trigger_mode == "any" else "所有模型达到"
        plain_rows = "\n".join(
            "%s：鲜艳度 %s，预计 %s，AOD %s，时次 %s"
            % (item.model, item.quality_text, item.event_time, item.aod_text, item.forecast_run)
            for item in forecasts
        )
        plain = "%s %s预测达到订阅条件（%s %.2f）。\n\n%s\n\n数据来源：https://sunsetbot.top/\n退订：%s" % (
            primary.city, event_name, mode_name, threshold, plain_rows, unsubscribe_url,
        )
        table_rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(item.model), html.escape(item.quality_text),
                html.escape(item.event_time), html.escape(item.aod_text),
            ) for item in forecasts
        )
        body = """<h2>{city} {event_name}提醒</h2>
<p>已满足订阅条件：<strong>{mode_name} {threshold:.2f}</strong>。</p>
<table cellpadding="8" cellspacing="0" border="1"><thead><tr><th>模型</th><th>鲜艳度</th><th>预计时间</th><th>AOD</th></tr></thead><tbody>{rows}</tbody></table>
<p>数据来源：<a href="https://sunsetbot.top/">sunsetbot</a></p>
<p><a href="{unsubscribe}">管理或退订</a></p>""".format(
            city=html.escape(primary.city), event_name=event_name, mode_name=mode_name,
            threshold=threshold, rows=table_rows, unsubscribe=html.escape(unsubscribe_url),
        )
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
