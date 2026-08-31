from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage
from typing import Dict, List

from app.config import Settings
from app.provider import Forecast


class Mailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_confirmation(
        self, recipient: str, city: str, token: str, unsubscribe_token: str,
    ) -> None:
        url = "%s/confirm/%s" % (self.settings.base_url, token)
        unsubscribe_url = "%s/unsubscribe/%s" % (self.settings.base_url, unsubscribe_token)
        self._send(
            recipient,
            "确认你的 SunsetScope 订阅",
            "你订阅了 %s 的朝霞/晚霞预测。请打开以下链接确认：\n%s\n\n如非本人操作或想取消：\n%s"
            % (city, url, unsubscribe_url),
            "<p>你订阅了 <strong>%s</strong> 的朝霞/晚霞预测。</p><p><a href=\"%s\">确认订阅</a></p><p><a href=\"%s\">取消这项订阅</a></p>"
            % (html.escape(city), html.escape(url), html.escape(unsubscribe_url)),
        )

    def send_unsubscribe_management(self, recipient: str, subscriptions: List[Dict]) -> None:
        plain_rows = []
        html_rows = []
        for subscription in subscriptions:
            event_name = "朝霞" if subscription["event"] == "rise" else "晚霞"
            models = subscription.get("models") or [subscription.get("model")]
            label = "%s · %s · %s" % (subscription["city"], event_name, " + ".join(models))
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
            "定时预测任务访问 sunsetbot 时发生故障：\n\n%s" % plain_rows,
            "<h2>预测数据源故障</h2><p>定时预测任务访问 sunsetbot 时发生故障：</p><ul>%s</ul>"
            % html_rows,
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
