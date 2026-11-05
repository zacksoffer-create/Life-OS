"""The phone app's engine layer: the same API answered without a server (as it runs on the phone)."""
import json
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)


PHONE_SCRIPT = """sure! here you go:
```
=== Phone story
order: any

--- Locker jam  [freshman · always]
best friend: Your locker's stuck again.
* Kick it   | mood +
* Leave it

--- Lunch line  [freshman · always]
best friend: They're out of fries. {Again.|Classic.}
* Get pizza | mood +
* Skip lunch

texts chatter_vent:
monday again. why
```
"""


def test_local_api_answers_like_the_server(tmp_path):
    # runs in a fresh Python with the FastAPI stand-in first on the path, exactly like the phone app
    script = textwrap.dedent(f"""
        import sys, json, asyncio
        sys.path[:0] = [{os.path.join(BACKEND, 'standalone')!r}, {BACKEND!r}]
        import fastapi
        assert hasattr(fastapi, 'ROUTES'), 'the stand-in must shadow the real FastAPI'
        from lifeos import local_api
        from tests.test_story import spec
        info = local_api.boot({str(tmp_path / 'saves')!r})
        call = lambda m, p, b=None, q='': asyncio.run(local_api.handle(m, p, q, None if b is None else (b if isinstance(b, bytes) else json.dumps(b).encode())))
        js = lambda r: json.loads(r['body'])
        s = spec(per=6); s['family']['pet'] = {{'species': 'dog', 'name': 'Buster'}}
        assert call('POST', '/api/story/new', {{'spec': s}})['status'] == 200
        st = js(call('GET', '/api/phone/state'))
        assert st['active'] and st['moments'] and st['pets'][0]['name'] == 'Buster'
        assert call('POST', f"/api/phone/moment/{{st['moments'][0]['id']}}", {{'index': 0}})['status'] == 200
        assert js(call('POST', '/api/story/advance', {{'until': 'decision'}}))['status'] == 'done'
        r = call('POST', '/api/story/advance', {{'until': 'moment'}})
        assert js(r)['status'] == 'running'
        while local_api.pump(0.2):
            pass
        assert js(call('GET', '/api/sim/job'))['status'] == 'done'
        # a storyline pasted on the phone (a story script), kept in the phone's own storage
        r = call('POST', '/api/dialogue/packs', {{'text': {PHONE_SCRIPT!r}}})
        assert r['status'] == 200, r['body'][:300]
        import os
        assert os.path.exists({str(tmp_path / 'dialogue' / 'phone_story.story')!r})
        # episodes back to back: Next episode runs on the phone the same way, a bit at a time, and stops at a scene
        assert js(call('POST', '/api/story/control', {{'binge': True}}))['binge'] is True
        js(call('POST', '/api/story/advance', {{'until': 'episode'}}))
        while local_api.pump(0.2):
            pass
        j = js(call('GET', '/api/sim/job'))
        assert j['status'] == 'done' and j['stop'] == 'episode', j
        st = js(call('GET', '/api/phone/state'))
        assert st['control']['binge'] and st['stories']['binge'] and st['moments'] and st['moments'][0]['storyline']
        sched = js(call('GET', '/api/story/schedule'))  # play a storyline start to finish, on a copy, on the phone too
        line = next(x['pack'] for x in sched['storylines'] if x['played'] + x['eligible'] + x['waiting'] + x['queued'] > 0)
        r = call('POST', '/api/story/playline/start', {{'pack': line}})
        assert r['status'] == 200, r['body'][:300]
        if js(r).get('moment'):
            assert call('POST', '/api/story/playline/choose', {{'index': 0}})['status'] == 200
        sp = call('GET', '/api/phone/sports')  # the Sports tab
        assert sp['status'] == 200 and 'teams' in js(sp), sp['body'][:300]
        lad = call('GET', '/api/phone/ladder')  # the Scene tab's ladder
        assert lad['status'] == 200 and js(lad)['you']['rank'] >= 1, lad['body'][:300]
        m = call('GET', '/api/phone/mlb')  # MLB in the background: the real data file ships in the phone's engine
        assert m['status'] == 200 and js(m)['my_team']['team'] == 'NYY', m['body'][:300]
        r = call('POST', '/api/phone/mlb/whatif', {{'id': 'harper_2019', 'on': True}})
        assert r['status'] == 200 and js(r)['view']['on'], r['body'][:300]
        lg = call('GET', '/api/phone/league', q='lg=mbb')  # college and the pros: the season files ship in the engine too
        assert lg['status'] == 200 and js(lg)['my_team']['name'] == 'UConn Huskies', lg['body'][:300]
        up = call('GET', '/api/story/order')  # up next, played forward on a copy, on the phone too
        assert up['status'] == 200 and js(up)['list'], up['body'][:300]
        threads = js(call('GET', '/api/phone/threads'))['threads']
        # the phone screens encode thread ids ("dm:bf" -> "dm%3Abf"), just like a browser talking to the server
        from urllib.parse import quote
        dm = next(t for t in threads if t['id'].startswith('dm:'))
        r = call('GET', '/api/phone/thread/' + quote(dm['id'], safe=''))
        assert r['status'] == 200, r['body'][:200]
        t = js(r)
        ask = next((m for m in reversed(t['msgs']) if m.get('replies') and m.get('chosen') is None), None)
        if ask:
            r = call('POST', '/api/phone/thread/' + quote(dm['id'], safe='') + '/reply', {{'msg': ask['id'], 'index': 0}})
            assert r['status'] == 200, r['body'][:200]
        assert call('GET', '/api/characters/zack-soffer')['status'] == 200
        # read and edit a script on the phone; a bad edit is refused with its line number
        src = js(call('GET', '/api/dialogue/packs/yours%3Aphone_story/script'))['text']
        fixed = call('POST', '/api/dialogue/packs/yours%3Aphone_story/script', {{'text': src.replace('mood +', 'zzqx +', 1)}})
        assert fixed['status'] == 200 and js(fixed)['notes'][0].startswith('line 6: the effect'), fixed['body'][:300]
        assert call('POST', '/api/dialogue/packs/yours%3Aphone_story/enabled', {{'enabled': False}})['status'] == 200
        assert not any(p['id'] == 'yours:phone_story' and p['enabled'] for p in js(call('GET', '/api/dialogue/packs'))['packs'])
        assert call('GET', '/api/nope')['status'] == 404
        assert call('POST', '/api/story/control', {{'focus': 'nonsense'}})['status'] == 422
        b = call('GET', '/api/phone/backup')
        assert b['status'] == 200 and len(b['body']) > 1000
        assert local_api.flush() or True
        assert js(call('POST', '/api/phone/restore', b['body']))['story']
        from lifeos import api
        assert api.lab.w.rules['history.event_window_days'] == 21, 'the phone keeps history lean'
        print('OK', info['routes'])
    """)
    out = subprocess.run([sys.executable, "-c", script], cwd=BACKEND, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-3000:]
    assert out.stdout.strip().startswith("OK")
