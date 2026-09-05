"""Protect Mumbai source evidence from guessed heights and invented confidence."""
import json
from pathlib import Path
import pytest
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
from app.backend.providers import create_provider
from pipeline.mumbai.build_profile import height_metres, _levels

ROOT=Path(__file__).resolve().parents[1]
BMC_REFERENCE = ROOT/'data/profiles/mumbai/raw/ward_review/bmc_buildings_gs.geojson'

def test_height_and_level_parsing_is_strict():
    assert height_metres("35'") == pytest.approx(10.668)
    assert height_metres('20 m') == 20
    assert height_metres('10;20') is None
    assert height_metres('unknown') is None
    assert _levels({'building:levels':'3;7'}) is None
    assert _levels({'building:levels':'4.5'}) is None
    assert _levels({'building:levels':'4.0'}) == 4

def test_mumbai_no_invented_vertical_evidence():
    provider=create_provider('mumbai')
    buildings={f['properties']['building_id']:f for f in provider.building_features}
    assert provider.unit_features == []
    for f in provider.building_features:
        p=f['properties']
        assert p['ward_name']=='G/S'
        assert p['building_id'].startswith('MUM-GS-OSM-')
        assert p['floor_count']==_levels(p['source_tags'])
        assert p['geometry_confidence_score'] is None
        assert p['cadastral_confidence_score'] is None
        assert p['basement_count'] is None
        if p['selected_height_m'] is not None:
            assert p['selected_height_m']==pytest.approx(height_metres(p['source_tags']['height']))
        if not p['floor_model_available']:
            assert provider.floors(p['building_id'])['features']==[]
    for floor in provider.floor_features:
        p=floor['properties']; b=buildings[p['building_id']]['properties']
        assert b['selected_height_m'] is not None and b['floor_count'] is not None
        assert p['floor_number']>0 and p['floor_layout_verified'] is False
        assert p['relative_z_max_m']<=b['selected_height_m']+1e-6
        roof=height_metres(b['source_tags'].get('roof:height')) or 0
        assert p['floor_height_m']==pytest.approx((b['selected_height_m']-roof)/b['floor_count'])
        assert p['floor_height_source']=='DERIVED_EQUAL_STRATA_FROM_OSM_HEIGHT_AND_LEVELS'

@pytest.mark.skipif(not BMC_REFERENCE.exists(), reason='BMC reference snapshot is excluded from the public repository')
def test_agreement_is_reproducible_from_independent_source_geometry():
    provider=create_provider('mumbai')
    refs=json.loads(BMC_REFERENCE.read_text())
    index={str(f['properties']['OBJECTID']):f for f in refs['features']}
    project=Transformer.from_crs(4326,32643,always_xy=True).transform
    for bid in provider.profile_metadata()['hero_buildings']:
        f=provider.building(bid)['building'];p=f['properties']
        a=transform(project,shape(f['geometry']))
        b=transform(project,shape(index[p['reference_building_id']]['geometry']))
        expected=round(a.intersection(b).area/a.union(b).area*100,2)
        assert p['footprint_agreement_pct']==expected
        assert p['reference_height_units']=='UNDOCUMENTED_NOT_USED'
        assert provider.building(bid)['quality']['quality_score'] is None

def test_gsouth_boundaries_and_identifiers_are_consistent():
    provider=create_provider('mumbai')
    ward=shape(provider.ward()['features'][0]['geometry'])
    ids=[f['properties']['building_id'] for f in provider.building_features]
    assert len(ids)==len(set(ids))
    for feature in provider.building_features:
        assert ward.covers(shape(feature['geometry']).representative_point())
    for road in provider.roads()['features']:
        assert shape(road['geometry']).difference(ward).length<1e-8
