import json, urllib.request, os

API_BASE = 'https://dreadpit.com'

with open('graveyard_top50.json') as f:
    data = json.load(f)
items = data.get('items', [])

os.makedirs('portraits', exist_ok=True)

downloads = []
for f in items:
    wins = f.get('wins', 0)
    if wins < 5:
        continue
    name = f.get('name', '?')[:30]
    # Clean filename
    safe_name = ''
    for c in name:
        if c.isalnum() or c in '._- ':
            safe_name += c
        else:
            safe_name += '_'
    safe_name = safe_name.strip()
    fid = f.get('id', 'unknown')[:12]
    url = f.get('imageUrl', '')
    if not url:
        continue
    filename = f'{fid}_{safe_name}.png'
    path = os.path.join('portraits', filename)
    if os.path.exists(path):
        download_result = {'name': f.get('name','?'), 'wins': wins, 'file': filename, 'cached': True}
        downloads.append(download_result)
        continue
    try:
        r = urllib.request.urlopen(f'{API_BASE}{url}', timeout=15)
        with open(path, 'wb') as out:
            out.write(r.read())
        download_result = {'name': f.get('name','?'), 'wins': wins, 'file': filename, 'cached': False}
        downloads.append(download_result)
    except Exception as e:
        download_result = {'name': f.get('name','?'), 'wins': wins, 'file': None, 'error': str(e)}
        downloads.append(download_result)

ok = [d for d in downloads if d.get('file')]
fail = [d for d in downloads if d.get('error')]
print(f'Downloaded {len(ok)} portraits, {len(fail)} failed')
for d in downloads:
    status = 'OK' if d.get('file') else f"FAIL: {d.get('error','')}"
    print(f"  {d['wins']:2d} wins  {d['name'][:40]:40s} [{status}]")

with open('portrait_manifest.json', 'w') as mf:
    json.dump(downloads, mf, indent=1)
print('Manifest saved to portrait_manifest.json')
