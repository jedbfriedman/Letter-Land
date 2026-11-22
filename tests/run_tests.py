"""Letter Land regression checks. Run before every deploy:

    python3 tests/run_tests.py          # everything (takes a few minutes)
    python3 tests/run_tests.py quick    # skips the full audio + offline checks

Needs Python Playwright with Chromium. Starts its own local web server."""
import asyncio, json, os, re, subprocess, sys, time, socket, contextlib
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUICK = 'quick' in sys.argv
FAIL = []
def check(ok, what):
    print(('  ok   ' if ok else '  FAIL ') + what, flush=True)
    if not ok: FAIL.append(what)

def free_port():
    with contextlib.closing(socket.socket()) as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

GAMES = [  # (name, js that starts it, screen id)
    ('Find It', "startFind('A')", 'find'),
    ('Say It', "show('say');startSay(true)", 'say'),
    ('Write It', "startWrite()", 'write'),
    ('Sound It Out', "startSound()", 'sound'),
    ('Mad Math Minute', "startMad(true,true)", 'mad'),
    ('Number Defender', "startDef(true,true)", 'def'),
    ('Time Teller', "startTime()", 'time'),
    ('Fill It In', "startAdv('fill')", 'fill'),
    ("What's That Word", "startAdv('mean')", 'fill'),
    ('Treasure room', "show('room');renderRoom()", 'room'),
]

async def main():
    port = free_port()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    URL = f'http://localhost:{port}/index.html'
    time.sleep(0.8)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
            # ---------- every game on iPad and iPhone: starts, no errors, no scrolling
            for vp, nm in [((820, 1180), 'iPad'), ((390, 844), 'iPhone')]:
                print(f'== {nm} screens')
                ctx = await b.new_context(viewport={'width': vp[0], 'height': vp[1]}, service_workers='block')
                pg = await ctx.new_page(); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                await pg.goto(URL); await pg.wait_for_timeout(1500)
                X = lambda c: pg.evaluate('c=>window.__LG.ev(c)', c)
                check(not errs, f'{nm}: page loads with no errors {errs[:2]}')
                for g, js, scr in GAMES:
                    errs.clear()
                    try:
                        await X("closeOv&&closeOv()"); await X(js); await pg.wait_for_timeout(900)
                        await X("closeOv&&closeOv()"); await pg.wait_for_timeout(200)
                        c = await X('cur')
                        sc = await X('document.scrollingElement.scrollHeight>innerHeight+2')
                        check(c == scr and not errs, f'{nm}: {g} starts (screen {c}) {errs[:1]}')
                        check(not sc, f'{nm}: {g} fits without scrolling')
                    except Exception as e:
                        check(False, f'{nm}: {g} crashed: {str(e)[:120]}')
                await ctx.close()

            # ---------- Mythics and the things they do
            print('== Mythics')
            ctx = await b.new_context(viewport={'width': 820, 'height': 1180}, service_workers='block')
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(URL); await pg.wait_for_timeout(1500)
            X = lambda c: pg.evaluate('c=>window.__LG.ev(c)', c)
            myth = await X("Object.entries(MYTHIC).map(([k,m])=>[k,m.id,PRIZE_BY[m.id]?PRIZE_BY[m.id].key:null])")
            for k, mid, key in myth:
                errs.clear()
                check(key is not None, f'Mythic {k}: prize {mid} exists')
                await X(f"closeOv();S['{k}Given']=0;superReward(()=>{{}},'{k}')"); await pg.wait_for_timeout(900)
                shown = await X("!$('#ov').hidden")
                check(shown and not errs, f'Mythic {k}: award screen shows {errs[:1]}')
                act = await X(f"!!(ACT['{key}']&&ACT['{key}'].snd)")
                if act:
                    await X(f"closeOv();ACT['{key}'].snd({{}})"); await pg.wait_for_timeout(1200); await X("typeof fwAimStop==='function'&&fwAimStop()")
                    check(not errs, f'Mythic {k}: its action runs ({key}) {errs[:1]}')
            await X('closeOv()')
            # telescope shapes: every star index valid, every star used, no line drawn twice
            geo = await X("""[...CONSTEL.map(c=>[c[0],c[2].length,c[3]]),...TELE_SHAPES.map(t=>[t[0],t[2].length,t[3]||[...t[2].keys(),...(t[1]?[0]:[])]])]""")
            for name, n, seq in geo:
                lines = [tuple(sorted((seq[i - 1], seq[i]))) for i in range(1, len(seq))]
                ok = all(0 <= i < n for i in seq) and set(seq) == set(range(n)) and len(lines) == len(set(lines))
                check(ok, f'Telescope: {name} connects cleanly')
            # play one constellation all the way through by tapping
            await X("const R=Math.random;Math.random=()=>0.01;starView();Math.random=R"); await pg.wait_for_timeout(400)
            for _ in range(20):
                ring = await pg.query_selector('#scGo circle')
                if not ring: break
                bb = await ring.bounding_box(); await pg.mouse.click(bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2); await pg.wait_for_timeout(120)
            await pg.wait_for_timeout(900)
            check(await X("!!$('#conBtn')"), 'Telescope: finishing a constellation shows its story button')
            await X('closeOv()')
            # bubble wand: bubbles appear and stay on screen (fresh page)
            await pg.reload(); await pg.wait_for_timeout(1500)
            await X("if(!S.owned.includes(BW_ID))S.owned.push(BW_ID);S.placed[BW_ID]={x:300,y:300};S.bwP={s:0,w:0};show('room');renderRoom()")
            await pg.wait_for_timeout(700)
            el = await pg.query_selector('#items [data-id="bubblewand.gold.plain"]')
            if el:
                bb = await el.bounding_box(); x = bb['x'] + bb['width'] / 2; y = bb['y'] + bb['height'] / 2
                await pg.mouse.move(x, y); await pg.mouse.down()
                for i in range(60): await pg.mouse.move(x + i * 6, y - 60 + 40 * ((i % 10) - 5) / 5, steps=2); await pg.wait_for_timeout(30)
                await pg.mouse.up(); await pg.wait_for_timeout(300); await X('closeOv()')
                n1 = await X('BW.b.length'); await pg.wait_for_timeout(6000); n2 = await X('BW.b.length')
                check(n1 > 0 and n2 == n1, f'Bubble wand: {n1} bubbles blown, still {n2} after 6 s')
            else:
                check(False, 'Bubble wand: wand found in the room')
            # grown-up pages
            for js, what in [("showProgress()", 'Progress report'), ("showStats('find')", 'Letter stats'), ("showMathStats()", 'Math stats'), ("show('settings')", 'Settings')]:
                errs.clear(); await X('closeOv()'); await X(js); await pg.wait_for_timeout(500)
                check(not errs, f'{what} opens {errs[:1]}')
            await ctx.close()

            if not QUICK:
                # ---------- every voice line has a recording
                print('== Audio')
                ctx = await b.new_context(service_workers='block'); pg = await ctx.new_page(); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                await pg.goto(URL); await pg.wait_for_timeout(1500)
                X = lambda c: pg.evaluate('c=>window.__LG.ev(c)', c)
                await X("needChunks(Object.keys(LINES))"); await pg.wait_for_timeout(500)
                for _ in range(120):
                    if await X("Object.values(VCH).length&&true"): pass
                    await pg.wait_for_timeout(500)
                    if await X("typeof PV_LOADED!=='undefined'"): break
                await X("Promise.all(Object.values(VCH))"); await pg.wait_for_timeout(20000)
                miss = await X("Object.keys(LINES).filter(k=>!(clips()||{})[k]&&!(window.SAY_CLIPS||{})[k])")
                # keys only spoken by the device voice on purpose (made up on the fly)
                miss = [k for k in miss if not re.match(r'^(pz_|x_|tmp_)', k)]
                check(len(miss) == 0, f'Audio: every voice line has a recording ({len(miss)} missing: {miss[:12]})')
                files = await X("OFF_FILES()")
                check(all(os.path.exists(os.path.join(ROOT, f)) for f in files), f'Audio: all {len(files)} voice files exist')
                await ctx.close()

                # ---------- offline: save everything, unplug, reload
                print('== Offline')
                ctx = await b.new_context(viewport={'width': 820, 'height': 1180}); pg = await ctx.new_page(); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                await pg.goto(URL); await pg.wait_for_timeout(2500); await pg.reload(); await pg.wait_for_timeout(2500)
                X = lambda c: pg.evaluate('c=>window.__LG.ev(c)', c)
                check(await X("!!navigator.serviceWorker.controller"), 'Offline: helper is running')
                await X("offlineSync(true)")
                for _ in range(600):
                    st = await X("[OFF.done,OFF.total,OFF.busy]")
                    if st[1] and not st[2]: break
                    await pg.wait_for_timeout(1000)
                st = await X("[OFF.done,OFF.total]")
                check(st[1] > 0 and st[0] == st[1], f'Offline: saved {st[0]} of {st[1]} files')
                await ctx.set_offline(True)
                await pg.reload(); await pg.wait_for_timeout(3000)
                ok = await X("typeof startAdv==='function'")
                await X("needChunks(['fi_5_400f','ww_stripes'])"); await pg.wait_for_timeout(2500)
                aud = await X("!!(clips()['fi_5_400f']&&clips()['ww_stripes'])")
                check(ok and aud and not errs, f'Offline: game and voices load with no internet {errs[:1]}')
                await ctx.close()
            await b.close()
    finally:
        srv.terminate()
    print()
    print('ALL GOOD' if not FAIL else f'{len(FAIL)} PROBLEM(S):\n - ' + '\n - '.join(FAIL))
    sys.exit(1 if FAIL else 0)

asyncio.run(main())
