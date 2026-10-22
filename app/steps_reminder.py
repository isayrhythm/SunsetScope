"""A standalone daily walking reminder, independent of forecast subscriptions."""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from app.mailer import Mailer
from app.service import normalize_email
from app.store import JsonStore


def send_reminder(recipient: str, settings: Optional[Settings] = None, mailer=None,
                  store=None, now: Optional[datetime] = None) -> bool:
    recipient = normalize_email(recipient)
    settings = settings or Settings.from_env()
    mailer = mailer or Mailer(settings)
    # Separate history: neither forecast deliveries nor subscriptions are changed.
    store = store or JsonStore(settings.store_path.with_name('steps-reminders.json'))
    local_now = now or datetime.now(ZoneInfo('Asia/Shanghai'))
    date = local_now.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    key = '%s|%s' % (recipient, date)

    def deliver(data):
        if any(item['key'] == key for item in data['deliveries']):
            return False
        mailer._send(
            recipient,
            '今日步数提醒：达到 7000 步了吗？',
            '%s\n\n晚上好！今天的步数达到 7000 步了吗？记得查看一下今天的步数。\n\n每日 22:00 步数提醒。' % date,
            '<h2>今天走够 7000 步了吗？</h2><p>%s</p><p>晚上好！记得查看一下今天的步数，看看是否达到 <strong>7000 步</strong>。</p><p>每日 22:00 步数提醒。</p>' % date,
        )
        data['deliveries'].append({'key': key, 'sent_at': local_now.isoformat()})
        return True

    # Hold the independent state lock during SMTP so concurrent runs cannot both send.
    return store.transact(deliver)


def main():
    parser = argparse.ArgumentParser(description='Send an independent daily 7000-step reminder.')
    parser.add_argument('--recipient', default=os.getenv('SUNSETSCOPE_STEPS_RECIPIENT', ''))
    args = parser.parse_args()
    if not args.recipient:
        parser.error('请配置 SUNSETSCOPE_STEPS_RECIPIENT 或 --recipient')
    print('steps_reminder=' + ('sent' if send_reminder(args.recipient) else 'already_sent'))


if __name__ == '__main__':
    main()
