"""Compare actual mapped vertical coverage for candidate Mumbai wards."""
import json
import re
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from shapely.geometry import Polygon, shape

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT/'data/profiles/mumbai/raw/ward_review'
ENDPOINTS = ['https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']

def download(code, feature, cached=False):
    slug = code.replace('/','').lower()
    geom = shape(feature['geometry'])
    west,south,east,north = geom.bounds
    query = f'[out:json][timeout:180];(way["building"]({south},{west},{north},{east});way["building:part"]({south},{west},{north},{east});way["highway"]({south},{west},{north},{east}););out meta geom;'
    target = RAW/f'osm_{slug}.json'
    if cached and not target.exists():
        return {'ward':code,'status':'DOWNLOAD_UNAVAILABLE_NOT_COMPARED'}
    if not target.exists():
        for endpoint in ENDPOINTS:
            try:
                r = requests.get(endpoint,params={'data':query},headers={'User-Agent':'ULPIN-research-prototype/1.0'},timeout=(15,180))
                r.raise_for_status()
                data = r.json()
                if data.get('remark'): raise RuntimeError(data['remark'])
                target.write_text(json.dumps(data),encoding='utf-8')
                (RAW/f'osm_{slug}_provenance.json').write_text(json.dumps({'url':endpoint,'query':query,'retrieved_at':datetime.now(timezone.utc).isoformat(),'osm_base':data.get('osm3s',{}),'license':'OpenStreetMap contributors, ODbL 1.0'}),encoding='utf-8')
                break
            except Exception as exc:
                print(code,endpoint,type(exc).__name__,str(exc)[:120],flush=True)
        else: raise RuntimeError(f'All downloads failed for {code}')
    data = json.loads(target.read_text(encoding='utf-8'))
    buildings=[]
    for e in data.get('elements',[]):
        t=e.get('tags',{})
        if not (t.get('building') or t.get('building:part')): continue
        points=[(p['lon'],p['lat']) for p in e.get('geometry',[])]
        if len(points)<4 or points[0]!=points[-1]:continue
        polygon=Polygon(points)
        if not polygon.is_valid or not geom.covers(polygon.representative_point()):continue
        buildings.append(e)
    levels=[e for e in buildings if re.fullmatch(r'\d+(?:\.0+)?',str(e['tags'].get('building:levels','')))]
    heights=[e for e in buildings if re.fullmatch(r'\d+(?:\.\d+)?(?:\s*m)?',str(e['tags'].get('height','')))]
    result={'ward':code,'buildings_and_parts':len(buildings),'explicit_levels':len(levels),'explicit_heights':len(heights),'height_and_levels':sum(e in heights for e in levels),'max_tagged_levels':max([int(float(e['tags']['building:levels'])) for e in levels],default=0)}
    print(result,flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cached',action='store_true');args=parser.parse_args()
    wards=json.loads((RAW/'wards.geojson').read_text(encoding='utf-8'))['features']
    codes=['G/S','H/E','D']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda code:download(code,next(f for f in wards if f['properties']['NAME']==code),args.cached),codes))
    (RAW/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
