"""Download only public portrait URLs returned by Shown Space's player API."""
import base64, concurrent.futures, json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def fetch(p):
    url=p.get('portraitUrl')
    if not url:return p['id'],None
    path=ROOT/'data/portraits'/f"{p['id']}.webp"
    try:
        if not path.exists():path.write_bytes(urllib.request.urlopen(url,timeout=20).read())
        return p['id'],'data:image/webp;base64,'+base64.b64encode(path.read_bytes()).decode()
    except Exception:return p['id'],None
if __name__=='__main__':
    (ROOT/'data/portraits').mkdir(parents=True,exist_ok=True)
    players=json.loads((ROOT/'data/players.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:results=dict(pool.map(fetch,players))
    (ROOT/'src/content/assets').mkdir(parents=True,exist_ok=True)
    (ROOT/'src/content/assets/portraits.json').write_text(json.dumps({k:v for k,v in results.items() if v}))
    print(f'Portraits available: {sum(bool(v) for v in results.values())}/{len(players)}; missing images use initials.')
