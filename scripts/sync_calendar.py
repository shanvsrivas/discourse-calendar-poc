#!/usr/bin/env python3
"""Export PUBLIC test-calendar events for the static vanilla calendar.

Runs inside GitHub Actions; GOOGLE_CALENDAR_API_KEY belongs in Actions Secrets.
Never use this to publish private or sensitive company calendar data.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

CALENDAR_ID = '362ee36c65781b95a1bdf0c8708324fff0b86ba601f8e6052a3e5d727bfc3852@group.calendar.google.com'
OUTPUT = pathlib.Path('events.json')


def main():
    api_key = os.environ.get('GOOGLE_CALENDAR_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('Missing GOOGLE_CALENDAR_API_KEY GitHub Actions secret')

    today = dt.datetime.now(dt.timezone.utc)
    start = (today.replace(day=1) - dt.timedelta(days=40)).replace(day=1)
    # 18 future calendar months, and one previous month; additional 1-month padding.
    end_year = start.year + (start.month - 1 + 20) // 12
    end_month = (start.month - 1 + 20) % 12 + 1
    end = dt.datetime(end_year, end_month, 1, tzinfo=dt.timezone.utc)

    params = {
        'key': api_key, 'timeMin': start.isoformat().replace('+00:00', 'Z'),
        'timeMax': end.isoformat().replace('+00:00', 'Z'),
        'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': '2500',
    }
    items = []
    while True:
        url = ('https://www.googleapis.com/calendar/v3/calendars/'
               + urllib.parse.quote(CALENDAR_ID, safe='')
               + '/events?' + urllib.parse.urlencode(params))
        req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'community-calendar-poc-sync/1.0'})
        # Avoid exposing the complete URL (which includes the key) in errors/logs.
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Google Calendar API returned HTTP {exc.code}; cached file unchanged') from None
        except Exception as exc:
            raise RuntimeError(f'Google Calendar API fetch failed ({type(exc).__name__}); cached file unchanged') from None
        items.extend(payload.get('items', []))
        if len(items) > 20000:
            raise RuntimeError('Unexpectedly many events; cached file unchanged')
        page = payload.get('nextPageToken')
        if not page:
            break
        params['pageToken'] = page

    events = []
    for item in items:
        if item.get('status') == 'cancelled':
            continue
        # Explicit allowlist of fields appropriate for the PUBLIC test calendar.
        events.append({k: item[k] for k in ('id', 'summary', 'start', 'end', 'description', 'htmlLink', 'location') if k in item})

    output = {
        'description': 'PUBLIC TEST CALENDAR - automatically synced by GitHub Actions',
        'lastSyncedAt': today.isoformat().replace('+00:00', 'Z'),
        'events': events,
    }
    # All validation/fetching is complete before the previous cached data is replaced.
    tmp = OUTPUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(OUTPUT)
    print(f'Successfully synchronized {len(events)} public test events')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
