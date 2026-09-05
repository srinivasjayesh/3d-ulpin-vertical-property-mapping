"""Download every BMC reference footprint in a candidate ward envelope by ID."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
from shapely.geometry import shape

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/profiles/mumbai/raw/ward_review'
URL='https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/283/query'

def get(params):
    response=requests.get(URL,params=params,timeout=90)
    response.raise_for_status()
    result=response.json()
    if 'error' in result:raise RuntimeError(result['error'])
    if result.get('exceededTransferLimit'):raise RuntimeError('Truncated BMC response')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ward',default='G/S');args=parser.parse_args()
    ward=next(f for f in json.loads((RAW/'wards.geojson').read_text())['features'] if f['properties']['NAME']==args.ward)
    bbox=shape(ward['geometry']).bounds
    params={'where':'1=1','geometry':','.join(map(str,bbox)),'geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects','returnIdsOnly':'true','f':'json'}
    ids=get(params)['objectIds'];features=[]
    for start in range(0,len(ids),200):
        batch=get({'objectIds':','.join(map(str,ids[start:start+200])),'outFields':'*','outSR':4326,'f':'geojson'})
        features.extend(batch['features']);print('BMC reference',len(features),'/',len(ids),flush=True)
    if len(features)!=len(ids):raise RuntimeError('Incomplete BMC reference snapshot')
    slug=args.ward.replace('/','').lower()
    (RAW/f'bmc_buildings_{slug}.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8')
    (RAW/f'bmc_buildings_{slug}_provenance.json').write_text(json.dumps({'url':URL,'bbox':bbox,'ward':args.ward,'retrieved_at':datetime.now(timezone.utc).isoformat(),'object_ids':ids,'count':len(features),'height_units':'NOT_DOCUMENTED_DO_NOT_USE'}),encoding='utf-8')
