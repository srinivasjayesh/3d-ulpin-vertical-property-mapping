"""Download source metadata and candidate ward extracts; never invent attributes."""
import json
from pathlib import Path
import requests
from shapely.geometry import shape
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data/profiles/mumbai/raw/ward_review'
BASE = 'https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer'

def fetch(url, params, filename):
    response = requests.get(url, params=params, timeout=90)
    response.raise_for_status()
    value = response.json()
    if 'error' in value:
        raise RuntimeError(value['error'])
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / filename).write_text(json.dumps(value), encoding='utf-8')
    return value

if __name__ == '__main__':
    for layer in [341, 283]:
        meta = fetch(f'{BASE}/{layer}', {'f':'json'}, f'layer_{layer}.json')
        print(layer, meta.get('name'), meta.get('geometryType'), [(f['name'], f.get('alias')) for f in meta.get('fields', [])], flush=True)
    wards = fetch(f'{BASE}/341/query', {'where':'1=1','outFields':'*','outSR':4326,'f':'geojson'}, 'wards.geojson')
    print('WARDS', [f['properties']['NAME'] for f in wards.get('features',[])], flush=True)
    for code in ['A', 'G/S', 'H/E', 'D']:
        feature = next(f for f in wards['features'] if f['properties']['NAME'] == code)
        bbox = shape(feature['geometry']).bounds
        slug = code.replace('/', '').lower()
        params = {'where':'1=1','geometry':','.join(map(str,bbox)), 'geometryType':'esriGeometryEnvelope', 'inSR':4326,'spatialRel':'esriSpatialRelIntersects','returnCountOnly':'true','f':'json'}
        count = fetch(f'{BASE}/283/query',params,f'building_count_{slug}.json')
        params.update({'returnCountOnly':'false','outFields':'*','returnGeometry':'false','resultRecordCount':3})
        sample = fetch(f'{BASE}/283/query',params,f'building_sample_{slug}.json')
        print('CANDIDATE',code,'official building bbox count',count,'sample',[f['attributes'] for f in sample.get('features',[])],flush=True)
    (RAW/'retrieved_at.txt').write_text(datetime.now(timezone.utc).isoformat(),encoding='utf-8')
