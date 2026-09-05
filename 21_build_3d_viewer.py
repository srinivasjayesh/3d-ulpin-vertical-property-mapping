import geopandas as gpd
import json
import os

FLOORS_FILE = "data/hero_floor_ulpins.geojson"
PARCELS_FILE = "data/hero_parcels.geojson"

OUTPUT_DIR = "viewer"
OUTPUT_FILE = "viewer/index.html"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# Load data
# --------------------------------------------------

floors = gpd.read_file(FLOORS_FILE).to_crs("EPSG:32644")
parcels = gpd.read_file(PARCELS_FILE).to_crs("EPSG:32644")

bounds = floors.total_bounds

center_x = (bounds[0] + bounds[2]) / 2
center_y = (bounds[1] + bounds[3]) / 2


def polygon_to_coords(geom):

    if geom.geom_type == "Polygon":
        geoms = [geom]

    elif geom.geom_type == "MultiPolygon":
        geoms = list(geom.geoms)

    else:
        return []

    result = []

    for poly in geoms:

        coords = []

        for x, y in poly.exterior.coords:

            coords.append([
                float(x - center_x),
                float(y - center_y)
            ])

        result.append(coords)

    return result


# --------------------------------------------------
# Prepare floors
# --------------------------------------------------

floor_data = []

for _, row in floors.iterrows():

    for coords in polygon_to_coords(row.geometry):

        floor_data.append({
            "floor_id": str(row["floor_id"]),
            "building_id": str(row["building_id"]),
            "floor_number": int(row["floor_number"]),
            "z_min": float(row["z_min_m"]),
            "z_max": float(row["z_max_m"]),
            "height": float(row["floor_height_m"]),
            "volume": float(row["volume_m3"]),
            "ulpin": str(row["prototype_3d_ulpin"]),
            "height_source": str(row["height_source"]),
            "floor_source": str(row["floor_source"]),
            "confidence": str(row["vertical_confidence"]),
            "estimated": bool(row["is_floor_estimated"]),
            "coords": coords
        })


# --------------------------------------------------
# Prepare parcels
# --------------------------------------------------

parcel_data = []

for _, row in parcels.iterrows():

    for coords in polygon_to_coords(row.geometry):

        parcel_data.append({
            "building_id": str(row.get("building_id", "")),
            "parcel_no": str(row.get("official_parcel_no", "")),
            "village": str(row.get("V_Name", "")),
            "mandal": str(row.get("M_Name", "")),
            "district": str(row.get("D_Name", "")),
            "coords": coords
        })


floors_json = json.dumps(floor_data)
parcels_json = json.dumps(parcel_data)


# --------------------------------------------------
# HTML template
# --------------------------------------------------

html = """
<!DOCTYPE html>
<html>

<head>

<meta charset="UTF-8">

<title>3D ULPIN Viewer</title>

<style>

body {
    margin: 0;
    overflow: hidden;
    font-family: Arial, sans-serif;
    background: #07111f;
}

#viewer {
    width: 100vw;
    height: 100vh;
}

.panel {
    position: absolute;
    background: rgba(5, 15, 30, 0.94);
    color: white;
    border-radius: 10px;
    padding: 14px;
    z-index: 10;
}

#title {
    top: 20px;
    left: 20px;
}

#title h2 {
    margin: 0;
}

#title p {
    margin: 5px 0 0;
    color: #9db7d3;
    font-size: 12px;
}

#controls {
    top: 110px;
    left: 20px;
    display: flex;
    flex-direction: column;
    gap: 7px;
}

button {
    border: none;
    padding: 9px 12px;
    border-radius: 6px;
    background: #173452;
    color: white;
    cursor: pointer;
}

button:hover {
    background: #285984;
}

#info {
    top: 20px;
    right: 20px;
    width: 320px;
}

#info h3 {
    color: #74c7ff;
    margin-top: 0;
}

.label {
    color: #8fa8bf;
    font-size: 11px;
    margin-top: 10px;
}

.value {
    font-size: 13px;
    margin-top: 3px;
    word-break: break-word;
}

#legend {
    bottom: 20px;
    left: 20px;
    font-size: 12px;
}

</style>

<script type="importmap">
{
    "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/"
    }
}
</script>

</head>

<body>

<div id="viewer"></div>

<div id="title" class="panel">
    <h2>3D ULPIN</h2>
    <p>Vertical Property Mapping — Hyderabad</p>
</div>

<div id="controls" class="panel">

    <button onclick="focusBuilding('B0595')">
        B0595 — Office Tower
    </button>

    <button onclick="focusBuilding('B0612')">
        B0612 — Apartments
    </button>

    <button onclick="focusBuilding('B0162')">
        B0162 — Residential
    </button>

    <button onclick="focusAll()">
        View All
    </button>

</div>

<div id="info" class="panel">

    <h3>Vertical Property</h3>

    <div class="value">
        Click a floor in the model.
    </div>

</div>

<div id="legend" class="panel">

    Individual 3D floor volumes<br>
    Official cadastral parcel outlines

</div>


<script type="module">

import * as THREE from 'three';

import {
    OrbitControls
} from 'three/addons/controls/OrbitControls.js';


const floors = __FLOORS_DATA__;
const parcels = __PARCELS_DATA__;


// ------------------------------------------------
// Scene
// ------------------------------------------------

const scene = new THREE.Scene();

scene.background = new THREE.Color(0x07111f);


// ------------------------------------------------
// Camera
// ------------------------------------------------

const camera = new THREE.PerspectiveCamera(
    45,
    window.innerWidth / window.innerHeight,
    0.1,
    10000
);

camera.position.set(250, 180, 300);


// ------------------------------------------------
// Renderer
// ------------------------------------------------

const renderer = new THREE.WebGLRenderer({
    antialias: true
});

renderer.setPixelRatio(window.devicePixelRatio);

renderer.setSize(
    window.innerWidth,
    window.innerHeight
);

document
    .getElementById("viewer")
    .appendChild(renderer.domElement);


// ------------------------------------------------
// Controls
// ------------------------------------------------

const controls = new OrbitControls(
    camera,
    renderer.domElement
);

controls.enableDamping = true;


// ------------------------------------------------
// Lights
// ------------------------------------------------

scene.add(
    new THREE.AmbientLight(
        0xffffff,
        1.5
    )
);

const light = new THREE.DirectionalLight(
    0xffffff,
    2
);

light.position.set(
    100,
    300,
    150
);

scene.add(light);


// ------------------------------------------------
// Ground grid
// ------------------------------------------------

const grid = new THREE.GridHelper(
    1200,
    60,
    0x4d6980,
    0x1a344a
);

scene.add(grid);


// ------------------------------------------------
// Groups
// ------------------------------------------------

const floorGroup = new THREE.Group();
const parcelGroup = new THREE.Group();

scene.add(parcelGroup);
scene.add(floorGroup);

const clickableMeshes = [];


// ------------------------------------------------
// Colors
// ------------------------------------------------

const colors = {

    B0595: 0x38a8ff,
    B0612: 0x7bde8c,
    B0162: 0xffbd59

};


// ------------------------------------------------
// Parcels
// ------------------------------------------------

parcels.forEach(function(parcel) {

    const points = parcel.coords.map(
        function(p) {

            return new THREE.Vector3(
                p[0],
                0.25,
                -p[1]
            );

        }
    );

    const geometry =
        new THREE.BufferGeometry()
        .setFromPoints(points);

    const material =
        new THREE.LineBasicMaterial({
            color: 0xffff33
        });

    const line =
        new THREE.Line(
            geometry,
            material
        );

    parcelGroup.add(line);

});


// ------------------------------------------------
// Floor volumes
// ------------------------------------------------

floors.forEach(function(floor) {

    if (floor.coords.length < 3) {
        return;
    }

    const shape = new THREE.Shape();

    floor.coords.forEach(
        function(point, index) {

            if (index === 0) {

                shape.moveTo(
                    point[0],
                    point[1]
                );

            } else {

                shape.lineTo(
                    point[0],
                    point[1]
                );

            }

        }
    );

    const geometry =
        new THREE.ExtrudeGeometry(
            shape,
            {
                depth: floor.height,
                bevelEnabled: false
            }
        );

    // Convert extrusion Z into scene vertical Y
    geometry.rotateX(
        -Math.PI / 2
    );

    const material =
        new THREE.MeshStandardMaterial({
            color:
                colors[floor.building_id]
                || 0xaaaaaa,

            transparent: true,
            opacity: 0.85,
            roughness: 0.75
        });

    const mesh =
        new THREE.Mesh(
            geometry,
            material
        );

    mesh.position.y = floor.z_min;

    mesh.userData = floor;

    floorGroup.add(mesh);

    clickableMeshes.push(mesh);


    // Floor boundary lines

    const edgeGeometry =
        new THREE.EdgesGeometry(
            geometry
        );

    const edgeMaterial =
        new THREE.LineBasicMaterial({
            color: 0x07111f
        });

    const edges =
        new THREE.LineSegments(
            edgeGeometry,
            edgeMaterial
        );

    edges.position.y = floor.z_min;

    floorGroup.add(edges);

});


// ------------------------------------------------
// Click detection
// ------------------------------------------------

const raycaster =
    new THREE.Raycaster();

const mouse =
    new THREE.Vector2();


renderer.domElement.addEventListener(
    "click",
    function(event) {

        mouse.x =
            (event.clientX /
            window.innerWidth) * 2 - 1;

        mouse.y =
            -(event.clientY /
            window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(
            mouse,
            camera
        );

        const hits =
            raycaster.intersectObjects(
                clickableMeshes,
                false
            );

        if (hits.length > 0) {

            showInfo(
                hits[0].object.userData
            );

        }

    }
);


// ------------------------------------------------
// Info
// ------------------------------------------------

function showInfo(d) {

    const info =
        document.getElementById("info");

    info.innerHTML =
        "<h3>" + d.floor_id + "</h3>" +

        "<div class='label'>BUILDING</div>" +
        "<div class='value'>" +
        d.building_id +
        "</div>" +

        "<div class='label'>FLOOR NUMBER</div>" +
        "<div class='value'>" +
        d.floor_number +
        "</div>" +

        "<div class='label'>VERTICAL RANGE</div>" +
        "<div class='value'>" +
        d.z_min.toFixed(2) +
        " m - " +
        d.z_max.toFixed(2) +
        " m</div>" +

        "<div class='label'>VOLUME</div>" +
        "<div class='value'>" +
        d.volume.toFixed(2) +
        " m³</div>" +

        "<div class='label'>PROTOTYPE 3D ULPIN</div>" +
        "<div class='value'>" +
        d.ulpin +
        "</div>" +

        "<div class='label'>HEIGHT SOURCE</div>" +
        "<div class='value'>" +
        d.height_source +
        "</div>" +

        "<div class='label'>FLOOR SOURCE</div>" +
        "<div class='value'>" +
        d.floor_source +
        "</div>" +

        "<div class='label'>CONFIDENCE</div>" +
        "<div class='value'>" +
        d.confidence +
        "</div>";

}


// ------------------------------------------------
// Camera focusing
// ------------------------------------------------

function focusObjects(objects) {

    if (objects.length === 0) {
        return;
    }

    const box = new THREE.Box3();

    objects.forEach(
        function(obj) {
            box.expandByObject(obj);
        }
    );

    const center =
        box.getCenter(
            new THREE.Vector3()
        );

    const size =
        box.getSize(
            new THREE.Vector3()
        );

    const maxSize =
        Math.max(
            size.x,
            size.y,
            size.z
        );

    const distance =
        Math.max(
            maxSize * 1.8,
            80
        );

    camera.position.set(
        center.x + distance,
        center.y + distance * 0.7,
        center.z + distance
    );

    controls.target.copy(center);

    controls.update();

}


window.focusBuilding =
function(buildingId) {

    const selected =
        clickableMeshes.filter(
            function(mesh) {

                return (
                    mesh.userData.building_id
                    === buildingId
                );

            }
        );

    focusObjects(selected);

};


window.focusAll =
function() {

    focusObjects(clickableMeshes);

};


// ------------------------------------------------
// Resize
// ------------------------------------------------

window.addEventListener(
    "resize",
    function() {

        camera.aspect =
            window.innerWidth /
            window.innerHeight;

        camera.updateProjectionMatrix();

        renderer.setSize(
            window.innerWidth,
            window.innerHeight
        );

    }
);


// ------------------------------------------------
// Render loop
// ------------------------------------------------

function animate() {

    requestAnimationFrame(animate);

    controls.update();

    renderer.render(
        scene,
        camera
    );

}

animate();

window.focusBuilding("B0595");

</script>

</body>

</html>
"""


# Inject JSON without Python f-string braces
html = html.replace(
    "__FLOORS_DATA__",
    floors_json
)

html = html.replace(
    "__PARCELS_DATA__",
    parcels_json
)


# --------------------------------------------------
# Save
# --------------------------------------------------

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(html)


print("\n=== 3D VIEWER CREATED ===")
print("Floor volumes:", len(floor_data))
print("Parcel polygons:", len(parcel_data))

print("\nCreated:")
print(OUTPUT_FILE)

print("\nRun:")
print("python -m http.server 8000")

print("\nOpen:")
print("http://localhost:8000/viewer/")