"""A standalone daily walking reminder, independent of forecast subscriptions."""
from __future__ import annotations

import argparse
import os
import secrets
import html
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from app.mailer import Mailer
from app.service import normalize_email
from app.store import JsonStore


def reminder_store(settings):
    return JsonStore(settings.store_path.with_name('steps-reminders.json'))


def china_now(now=None):
    return (now or datetime.now(ZoneInfo('Asia/Shanghai'))).astimezone(ZoneInfo('Asia/Shanghai'))


def find_day(store, token, now=None):
    if not token or len(token) > 100:
        raise ValueError('提醒链接无效')
    for day in store.read().get('steps_days', []):
        if secrets.compare_digest(day['token'], token):
            if day['date'] != china_now(now).date().isoformat():
                raise ValueError('这条提醒已经过期，请使用今天的邮件')
            return day
    raise ValueError('提醒链接无效')


def submit_status(store, token, action, now=None):
    if action not in {'done', 'remind'}:
        raise ValueError('无效的选项')
    local_now = china_now(now)
    def update(data):
        for day in data.get('steps_days', []):
            if not secrets.compare_digest(day['token'], token):
                continue
            if day['date'] != local_now.date().isoformat():
                raise ValueError('这条提醒已经过期，请使用今天的邮件')
            if action == 'done':
                day['status'] = 'done'
            elif day['status'] != 'done':
                if local_now.hour >= 23:
                    raise ValueError('今晚 23:00 的提醒时间已过，仍可提交已达成')
                day['status'] = 'remind'
            day['updated_at'] = local_now.isoformat()
            return dict(day)
        raise ValueError('提醒链接无效')
    return store.transact(update)


def send_reminder(recipient: str, settings: Optional[Settings] = None, mailer=None,
                  store=None, now: Optional[datetime] = None, followup: bool = False) -> bool:
    recipient = normalize_email(recipient)
    settings = settings or Settings.from_env()
    mailer = mailer or Mailer(settings)
    # Separate history: neither forecast deliveries nor subscriptions are changed.
    store = store or reminder_store(settings)
    local_now = china_now(now)
    date = local_now.date().isoformat()
    key = '%s|%s' % (recipient, date)

    def deliver(data):
        days = data.setdefault('steps_days', [])
        day = next((item for item in days if item['key'] == key), None)
        if followup:
            if local_now.hour != 23 or not day or day['status'] != 'remind' or day.get('followup_sent_at'):
                return False
        else:
            if any(item['key'] == key for item in data['deliveries']):
                return False
            day = {'key': key, 'recipient': recipient, 'date': date, 'token': secrets.token_urlsafe(32),
                   'status': 'unanswered', 'followup_sent_at': None}
        url = '%s/steps/%s' % (settings.base_url, day['token'])
        done_url = url + '?action=done'
        remind_url = url + '?action=remind'
        plain = '%s\n\n晚上好！今天的步数达到 7000 步了吗？\n\n已达成，提交：%s\n未达成，23:00 继续提醒：%s\n\n不选择则不追加提醒；提交已达成后不再追加提醒。' % (date, done_url, remind_url)
        body = '<h2>今天走够 7000 步了吗？</h2><p>%s</p><p>晚上好！记得查看一下今天的步数。</p>' % date
        body += '<p><a style="display:inline-block;padding:12px 18px;background:#287454;color:white;text-decoration:none;border-radius:8px" href="%s">已达成，提交</a></p>' % html.escape(done_url)
        if not followup:
            body += '<p><a style="display:inline-block;padding:12px 18px;background:#f1e4d3;color:#5d412d;text-decoration:none;border-radius:8px" href="%s">未达成，23:00 继续提醒</a></p><p>不选择则不追加提醒；提交已达成后不再追加提醒。</p>' % html.escape(remind_url)
        else:
            plain = '%s\n\n这是你选择的 23:00 提醒。今天走够 7000 步了吗？\n已达成，提交：%s\n\n今晚不会再追加提醒。' % (date, done_url)
            body += '<p>这是你选择的 23:00 提醒，今晚不会再追加提醒。</p>'
        mailer._send(
            recipient,
            '23:00 步数再提醒：达到 7000 步了吗？' if followup else '今日步数提醒：达到 7000 步了吗？',
            plain, body,
        )
        if followup:
            day['followup_sent_at'] = local_now.isoformat()
        else:
            days.append(day)
            data['deliveries'].append({'key': key, 'sent_at': local_now.isoformat()})
        return True

    # Hold the independent state lock during SMTP so concurrent runs cannot both send.
    return store.transact(deliver)


def main():
    parser = argparse.ArgumentParser(description='Send an independent daily 7000-step reminder.')
    parser.add_argument('--recipient', default=os.getenv('SUNSETSCOPE_STEPS_RECIPIENT', ''))
    parser.add_argument('--followup', action='store_true')
    args = parser.parse_args()
    if not args.recipient:
        parser.error('请配置 SUNSETSCOPE_STEPS_RECIPIENT 或 --recipient')
    print('steps_reminder=' + ('sent' if send_reminder(args.recipient, followup=args.followup) else 'skipped'))


if __name__ == '__main__':
    main()
