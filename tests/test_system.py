from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.adapters.bim import BIMAdapter
from app.backend.adapters.lidar import LiDARAdapter
from app.backend.main import app
from app.backend.providers import create_provider
from app.backend.providers.file_provider import FileProvider
from database.connection import postgis_status


ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)

PROTECTED_HASHES = {
    "01_pull_buildings.py": "2A05E22411B9518027B70F94CB994491F2ADEFEFF7D245C5EA06FD9999DD6B53",
    "02_prepare_buildings.py": "5C595D21B2444B85C491CCD9B96C997C663A57DABB4E97AAD1E28C42804F166F",
    "03_hero_candidates.py": "339690B077C2ACC48EB67CD7064B60238A09B129361B460579DDC83F899FCEDF",
    "04_select_hero_buildings.py": "8A1A02CC2711D19A989F111AB25306901BCB1AC44F64F05FD3078CCC8B77A4E2",
    "05_hero_locations.py": "4711E6AFA1DBE00486B40CDC89EA56ACD639C886550EB3E26E243E2E7F7CD378",
    "06_query_parcel.py": "91728EAD62ED854840FEFDF98736539BD51CCD785E679D3A384624D3C8088CB1",
    "07_query_all_hero_parcels.py": "EC5D9458FB9BD4B48420250358D5F67C8D984946F01E4EFBC0F494582CAE2CD7",
    "08_save_hero_parcels.py": "F2E5FF93DCF32F96B6910E80FD31C2D3D919DC54EAA95ACA70B4B14C52691BA5",
    "09_match_buildings_parcels.py": "6D363EBB0823483781F9D01AF797926ED00A54CB207642C354B9734DBD49F80B",
    "10_find_best_matches.py": "D5A4E693375F6D76FFCC80DF8DFDE78497585009ED0AF56A80557FD42930CCC7",
    "11_prepare_vertical_baseline.py": "9223B9977D0ADF1911DB59D9EC4FE2DD1FF09F0983F5392D7D0B0242F79436B2",
    "12_check_osm_vertical_tags.py": "D60DD2A07F08636F67F8583B3735FB76DF532E80E0F1DE77572355FC5B755F30",
    "13_inspect_height_raster.py": "0AE919FBB8DE3EC24C52567727B2603765FAD765DC5A5BABD11C94ECE5D08030",
    "14_extract_google_heights.py": "D16F8BAD57E590CED049CD9107749F34CB17F3E37745882360FACD517EC4C3E3",
    "15_estimate_floor_counts.py": "A3B6764DA9153987E67EA15316F9CEF996BE25DABFD139F206CC423D2F4EB8FF",
    "16_generate_floor_volumes.py": "2C36012F719BE6D505D3714AABC719F65DE72755A1AA6779F8C91B622B38D313",
    "17_generate_3d_ulpins.py": "355B4D94AA66A628300D44828E28FBD951AD13A374F11250F5F60EDC1D65D5AA",
    "18_validate_vertical_topology.py": "755D43AAC1B76399B2378300BBE7F9294315944BAD26C7A03767C993ECE09567",
    "19_create_conflict_test.py": "E1FCC351B8ABDE3A3EC3172F7CE8C984CE05818535DAFEDC40F6C539E16C3E75",
    "20_validate_conflict_test.py": "F7868DA435C731D5405F65CC0EC153E8C9762D64499018127B887F660FCEB5B9",
    "21_build_3d_viewer.py": "94B59302FEF78444EAAD51C86A6A8EC73C28C062881B0BA87E9A62986CE9CEC5",
}


def test_api_health_and_counts():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["buildings_loaded"] == 635
    assert health.json()["floor_units_loaded"] == 2100
    assert health.json()["parcels_loaded"] in {0, 194}


def test_api_stats():
    result = client.get("/api/stats")
    assert result.status_code == 200
    stats = result.json()
    assert stats["total_buildings"] == 635
    assert stats["total_floor_units"] == 2100
    assert stats["topology_errors"] == 0
    assert stats["topology_warnings"] == 7


@pytest.mark.parametrize(
    ("building_id", "confidence", "floors"),
    [("B0595", 97.9, 23), ("B0612", 88.0, 18), ("B0589", 88.0, 10)],
)
def test_hero_buildings(building_id, confidence, floors):
    details = client.get(f"/api/buildings/{building_id}")
    assert details.status_code == 200
    properties = details.json()["building"]["properties"]
    assert properties["cadastral_confidence_score"] == pytest.approx(confidence)
    assert properties["selected_height_source"] == "GOOGLE_OPEN_BUILDINGS_2_5D"
    floor_result = client.get(f"/api/buildings/{building_id}/floors")
    assert floor_result.status_code == 200
    assert len(floor_result.json()["features"]) == floors


def test_prototype_ids_are_unique_and_unofficial():
    provider = FileProvider()
    values = [
        feature["properties"]["prototype_id"] for feature in provider.floor_features
    ]
    assert len(values) == 2100
    assert len(set(values)) == 2100
    assert all(feature["properties"]["ulpin_is_official"] is False for feature in provider.floor_features)


def test_provider_fallback(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "unsupported-test-backend")
    provider = create_provider()
    assert provider.backend_name == "file"
    assert provider.health()["fallback"] is True


def test_capabilities_are_honest():
    capabilities = client.get("/api/system/capabilities")
    assert capabilities.status_code == 200
    values = capabilities.json()
    assert values["data_backend"] == "file"
    assert values["postgis"] == "CODE_READY"
    assert values["dem"] == "PENDING"
    assert values["bim"] == "NOT_LOADED"
    assert values["lidar"] == "NOT_LOADED"
    assert values["absolute_z"] == "RELATIVE_Z_ONLY"


def test_bim_and_lidar_empty_states():
    bim = client.get("/api/buildings/B0595/bim")
    units = client.get("/api/buildings/B0595/units")
    assert bim.status_code == units.status_code == 200
    assert bim.json()["status"] == "BIM_NOT_LOADED"
    assert bim.json()["spaces"] == []
    assert units.json()["units"] == []
    assert LiDARAdapter().analyze_building(
        FileProvider().building("B0595")["building"]
    )["status"] == "LIDAR_NOT_LOADED"


def test_relative_z_warnings_are_not_legal_conflicts():
    issues = client.get("/api/conflicts").json()
    assert len(issues) == 7
    assert all(item["z_reference"] == "RELATIVE_Z_ONLY" for item in issues)
    assert all(item["issue_class"] == "TOPOLOGY_WARNING" for item in issues)
    assert all(item["legal_status"] == "NOT_A_LEGAL_DETERMINATION" for item in issues)


def test_postgis_provider_if_available():
    if postgis_status().get("status") != "ACTIVE":
        pytest.skip("PostgreSQL/PostGIS is not available on this host")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATA_BACKEND", "postgis")
    try:
        provider = create_provider()
        assert provider.backend_name == "postgis"
        assert provider.stats()["total_buildings"] == 635
    finally:
        monkeypatch.undo()


def test_protected_root_scripts_unchanged():
    actual = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper()
        for name in PROTECTED_HASHES
    }
    assert actual == PROTECTED_HASHES


def test_profiles_and_manhattan_stats():
    result = client.get("/api/profiles")
    assert result.status_code == 200
    assert {item["profile_id"] for item in result.json()["profiles"]} == {"hyderabad", "manhattan", "mumbai"}
    stats = client.get("/api/stats?profile=manhattan")
    assert stats.status_code == 200
    values = stats.json()
    assert values["total_buildings"] == 133
    assert values["total_tax_lots"] == 164
    assert values["total_floor_units"] == 1827
    assert values["total_vertical_units"] == 8130
    assert values["topology_errors"] == 0


def test_manhattan_units_are_deterministic_and_synthetic():
    provider = create_provider("manhattan")
    units = provider.unit_features
    assert len(units) == 8130
    uids = [feature["properties"]["prototype_unit_uid"] for feature in units]
    assert len(uids) == len(set(uids))
    assert all(feature["properties"]["unit_geometry_is_synthetic"] is True for feature in units)
    assert all(feature["properties"]["prototype_uid_is_official"] is False for feature in units)
    sample = uids[0]
    assert provider.unit_lookup(sample)["properties"]["prototype_unit_uid"] == sample


def test_manhattan_profile_endpoints():
    building = client.get("/api/buildings/NYC-B107?profile=manhattan")
    assert building.status_code == 200
    properties = building.json()["building"]["properties"]
    assert properties["profile_id"] == "manhattan"
    assert properties["floor_count"] > 0
    assert properties["ground_elevation_status"] in {"SOURCE_ATTRIBUTE_AVAILABLE", "GROUND_ELEVATION_PENDING"}
    floors = client.get("/api/buildings/NYC-B107/floors?profile=manhattan")
    assert floors.status_code == 200
    floor_number = floors.json()["features"][0]["properties"]["floor_number"]
    units = client.get(f"/api/buildings/NYC-B107/floors/{floor_number}/units?profile=manhattan")
    assert units.status_code == 200
    assert units.json()["units"]
    uid = units.json()["units"][0]["properties"]["prototype_unit_uid"]
    lookup = client.get(f"/api/units/{uid}?profile=manhattan")
    assert lookup.status_code == 200
    assert lookup.json()["properties"]["unit_geometry_source"] == "SYNTHETIC_SUBDIVISION"


def test_profile_capabilities_are_distinct():
    hyderabad = client.get("/api/system/capabilities?profile=hyderabad").json()
    manhattan = client.get("/api/system/capabilities?profile=manhattan").json()
    assert hyderabad["data_profile"] == "hyderabad"
    assert hyderabad["unit_geometry"] == "NOT_AVAILABLE"
    assert manhattan["data_profile"] == "manhattan"
    assert manhattan["unit_geometry"] == "SYNTHETIC_DEMO"
    assert manhattan["ground_elevation"] == "ACTIVE_SOURCE_ATTRIBUTE"
    mumbai = client.get("/api/system/capabilities?profile=mumbai").json()
    assert mumbai["data_profile"] == "mumbai"
    assert mumbai["unit_geometry"] == "NOT_AVAILABLE"
    assert mumbai["sources"]["MCGM G/South Ward Boundary"] == "ACTIVE"
    assert mumbai["sources"]["BMC Reference Footprints"] == "ACTIVE_GEOMETRY_COMPARISON"


def test_mumbai_profile_endpoints():
    health = client.get("/api/health?profile=mumbai")
    assert health.status_code == 200
    assert health.json()["buildings_loaded"] == 4626
    assert health.json()["roads_loaded"] == 1803
    stats = client.get("/api/stats?profile=mumbai")
    assert stats.status_code == 200
    assert stats.json()["total_floor_units"] == 1046
    roads = client.get("/api/roads?profile=mumbai")
    assert roads.status_code == 200
    assert roads.json()["features"]
    ward = client.get("/api/ward?profile=mumbai")
    assert ward.status_code == 200
    assert ward.json()["features"][0]["properties"]["ward_name"] == "G/S"


def test_frontend_below_ground_and_unit_ulpin_controls():
    index = (ROOT / "app/frontend/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/frontend/app.js").read_text(encoding="utf-8")
    styles = (ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert 'id="below-ground-btn"' in index
    assert 'id="ward-view-btn"' in index
    assert 'id="toggle-map-panel"' in index
    assert 'id="toggle-dossier-panel"' in index
    assert 'id="reopen-map-panel"' in index
    assert 'id="three-zoom-out"' in index
    assert "Ward 3D" in index
    assert "deriveBelowGroundCompartments" in script
    assert "B1 · Basement parking / plant" in script
    assert 'class="ulpin-link"' in script
    assert "Select a Manhattan building before choosing a unit" in script
    assert ".ulpin-link" in styles
    assert "renderContextBuildings" in script
    assert "cameraReadyForBuilding" in script
    assert "Show Surroundings" in script
    assert "UNIT_DEFAULT_COLOR" in script
    assert "UNIT_SELECTED_COLOR" in script
    assert "exactBuilding" in script
    assert "addUnitDeck" in script
    assert "studyBoundaryLayer" in script
    assert "focusBelowGround" in script
    assert "cutawayOpacity" in script
    assert "study-boundary-line" in index
    assert "renderContextRoads" in script
    assert "addSelectedBuildingMass" in script
    assert "ward3DMode" in script
    assert "renderWard3D" in script
    assert "focusWard3D" in script
    assert "zoomThree" in script
    assert "z=0 ground reference" in script
    assert "left-collapsed" in styles
    assert "mumbai" in script


def test_manhattan_unit_search_returns_direct_match():
    provider = create_provider("manhattan")
    uid = provider.unit_features[0]["properties"]["prototype_unit_uid"]
    result = client.get("/api/search", params={"profile": "manhattan", "q": uid})
    assert result.status_code == 200
    assert result.json()["units"][0]["properties"]["prototype_unit_uid"] == uid
