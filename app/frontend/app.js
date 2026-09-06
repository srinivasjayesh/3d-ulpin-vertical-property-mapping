const API_BASE = window.APP_CONFIG?.API_BASE || window.location.origin;

let profiles = [];
let currentProfile = "hyderabad";
let currentProfileConfig = null;
let currentBuilding = null;
let currentFloors = [];
let currentUnits = [];
let selectedFloorNumber = null;
let selectedUnitUid = null;
let viewMode = "BUILDING";
let exploded = false;
let belowGroundEnabled = false;
let belowGroundCompartments = [];
let isolateBuilding = false;
let ward3DMode = false;
let surveyContextEnabled = false;
let systemCapabilities = null;

let map;
let buildingsLayer;
let parcelsLayer;
let contextBuildings = [];
let contextRoads = [];
let roadsLayer = null;
let studyBoundaryLayer = null;
let wardFeature = null;
const buildingLayersById = new Map();
const parcelLayersById = new Map();
let selectedBuildingLayer = null;
let selectedParcelLayer = null;

let scene;
let camera;
let renderer;
let controls;
let cameraReadyForBuilding = false;
let modelGroup;
let parcelGroup;
let gridHelper;
let modelMeshes = [];
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const UNIT_DEFAULT_COLOR = 0x2f86b5;
const UNIT_SELECTED_COLOR = 0x5de0d2;


function safe(value, fallback = "N/A") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function numeric(value, digits = 1, suffix = "") {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : "N/A";
}


function field(label, value) {
    return `<div class="field"><span>${safe(label)}</span><span>${value}</span></div>`;
}


function setStatus(text) {
    document.getElementById("system-status").textContent = text;
}


function toggleSidePanel(side) {
    const main = document.querySelector("main");
    const left = side === "left";
    const collapsed = main.classList.toggle(left ? "left-collapsed" : "right-collapsed");
    const button = document.getElementById(left ? "toggle-map-panel" : "toggle-dossier-panel");
    button.textContent = left ? (collapsed ? "›" : "‹") : (collapsed ? "‹" : "›");
    button.title = collapsed ? `Expand ${left ? "left map" : "right dossier"}` : `Collapse ${left ? "left map" : "right dossier"}`;
    document.getElementById(left ? "reopen-map-panel" : "reopen-dossier-panel").hidden = !collapsed;
    if (left && map) setTimeout(() => map.invalidateSize(), 180);
}


function reopenSidePanel(side) {
    const main = document.querySelector("main");
    const left = side === "left";
    main.classList.remove(left ? "left-collapsed" : "right-collapsed");
    document.getElementById(left ? "toggle-map-panel" : "toggle-dossier-panel").textContent = left ? "‹" : "›";
    document.getElementById(left ? "toggle-map-panel" : "toggle-dossier-panel").title = `Collapse ${left ? "left map" : "right dossier"}`;
    document.getElementById(left ? "reopen-map-panel" : "reopen-dossier-panel").hidden = true;
    if (left && map) setTimeout(() => map.invalidateSize(), 180);
}


async function api(path, includeProfile = true) {
    const url = new URL(`${API_BASE}${path}`);
    if (includeProfile) url.searchParams.set("profile", currentProfile);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
    return response.json();
}


function initMap() {
    map = L.map("map", { zoomControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 20,
    }).addTo(map);
}


function clearProfileLayers() {
    if (buildingsLayer) map.removeLayer(buildingsLayer);
    if (parcelsLayer) map.removeLayer(parcelsLayer);
    buildingsLayer = null;
    parcelsLayer = null;
    if (roadsLayer) map.removeLayer(roadsLayer);
    roadsLayer = null;
    if (studyBoundaryLayer) map.removeLayer(studyBoundaryLayer);
    studyBoundaryLayer = null;
    wardFeature = null;
    buildingLayersById.clear();
    parcelLayersById.clear();
    selectedBuildingLayer = null;
    selectedParcelLayer = null;
}


function buildingStyle(feature) {
    const properties = feature.properties || {};
    const vertical = currentProfile === "mumbai" ? Number(properties.selected_height_m) > 0 : Number(properties.floor_count || 0) > 0;
    return {
        color: vertical ? "#71858a" : "#50595c",
        weight: 0.7,
        fillColor: vertical ? "#4e5f64" : "#343c3f",
        fillOpacity: vertical ? 0.55 : 0.28,
    };
}


function parcelStyle() {
    if (currentProfile === "manhattan") {
        return { color: "#8d806a", weight: 0.8, fillColor: "#766b59", fillOpacity: 0.07 };
    }
    return { color: "transparent", weight: 0, fillOpacity: 0 };
}


function selectedParcelStyle() {
    const properties = currentBuilding?.properties || {};
    const mode = properties.parcel_visibility_mode;
    if (currentProfile === "hyderabad" && mode === "HIDE") {
        return { color: "transparent", weight: 0, fillOpacity: 0 };
    }
    if (currentProfile === "hyderabad" && mode === "OPTIONAL_CONTEXT" && !surveyContextEnabled) {
        return { color: "transparent", weight: 0, fillOpacity: 0 };
    }
    return { color: "#a08d6f", weight: 2.2, fillColor: "#8c785b", fillOpacity: 0.12 };
}


function parcelId(properties) {
    return String(properties.tax_lot_id || properties.parcel_id || properties.official_parcel_no || "");
}


async function loadMapData() {
    clearProfileLayers();
    const [buildings, parcels, roads, ward] = await Promise.all([
        api("/api/buildings"),
        api("/api/parcels"),
        api("/api/roads").catch(() => ({ features: [] })),
        api("/api/ward").catch(() => ({ features: [] })),
    ]);
    contextBuildings = buildings.features || [];
    contextRoads = roads.features || [];
    wardFeature = ward.features?.[0] || null;
    const [south, west, north, east] = currentProfileConfig.bbox;
    if (wardFeature) {
        studyBoundaryLayer = L.geoJSON(wardFeature, { style: { color: "#34262d", weight: 3.2, fillColor: "#4c3843", fillOpacity: 0.07 }, interactive: false }).addTo(map);
        studyBoundaryLayer.bindTooltip(`${currentProfileConfig.label} — official MCGM ward boundary`, { sticky: true });
    } else {
        studyBoundaryLayer = L.rectangle([[south, west], [north, east]], {
            color: "#493a42", weight: 2.6, dashArray: "7 5", fillColor: "#493a42", fillOpacity: 0.025, interactive: false,
        }).addTo(map);
        studyBoundaryLayer.bindTooltip(`${currentProfileConfig.label} study boundary — keep analysis within this area`, { sticky: true });
    }
    roadsLayer = L.geoJSON(roads, {
        style: { color: "#d8a45f", weight: 1.15, opacity: 0.65, lineCap: "round" },
        interactive: false,
    }).addTo(map);
    parcelsLayer = L.geoJSON(parcels, {
        style: parcelStyle,
        onEachFeature(feature, layer) {
            parcelLayersById.set(parcelId(feature.properties || {}), layer);
        },
    }).addTo(map);
    buildingsLayer = L.geoJSON(buildings, {
        style: buildingStyle,
        onEachFeature(feature, layer) {
            const id = String(feature.properties?.building_id);
            buildingLayersById.set(id, layer);
            layer.bindTooltip(id, { sticky: true });
            layer.on("click", () => selectBuilding(id));
        },
    }).addTo(map);
    if (wardFeature) map.fitBounds(studyBoundaryLayer.getBounds(), { padding: [18, 18] });
    else map.setView(currentProfileConfig.center, currentProfileConfig.map_zoom);
}


function highlightMapBuilding(buildingId) {
    if (selectedBuildingLayer) selectedBuildingLayer.setStyle(buildingStyle(selectedBuildingLayer.feature));
    selectedBuildingLayer = buildingLayersById.get(buildingId) || null;
    if (selectedBuildingLayer) {
        selectedBuildingLayer.setStyle({ color: "#56e4cc", weight: 3, fillColor: "#167e82", fillOpacity: 0.78 });
        selectedBuildingLayer.bringToFront();
    }
    if (selectedParcelLayer) selectedParcelLayer.setStyle(parcelStyle());
    const properties = currentBuilding?.properties || {};
    const id = String(properties.matched_parcel_id || properties.tax_lot_id || "");
    selectedParcelLayer = parcelLayersById.get(id) || null;
    if (selectedParcelLayer) {
        selectedParcelLayer.setStyle(selectedParcelStyle());
        selectedParcelLayer.bringToFront();
    }
}


function focusMapBuilding() {
    if (selectedBuildingLayer) map.fitBounds(selectedBuildingLayer.getBounds(), { padding: [45, 45], maxZoom: 19 });
}


function initThree() {
    const container = document.getElementById("three-container");
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x09172a);
    camera = new THREE.PerspectiveCamera(44, container.clientWidth / container.clientHeight, 0.1, 5000);
    camera.position.set(80, 65, 100);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = true;
    controls.enableRotate = true;
    controls.enableZoom = true;
    controls.screenSpacePanning = true;
    scene.add(new THREE.HemisphereLight(0xdde7e7, 0x25282a, 1.35));
    const directional = new THREE.DirectionalLight(0xffffff, 0.65);
    directional.position.set(45, 90, 35);
    scene.add(directional);
    modelGroup = new THREE.Group();
    parcelGroup = new THREE.Group();
    gridHelper = new THREE.GridHelper(520, 52, 0x1d5275, 0x12314d);
    gridHelper.position.y = -0.18;
    scene.add(gridHelper, modelGroup, parcelGroup);
    renderer.domElement.addEventListener("click", onThreeClick);
    animate();
}


function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}


function disposeGroup(group) {
    while (group.children.length) {
        const object = group.children.pop();
        object.geometry?.dispose();
        if (Array.isArray(object.material)) object.material.forEach(material => material.dispose());
        else object.material?.dispose();
    }
}


function polygons(geometry) {
    if (!geometry) return [];
    if (geometry.type === "Polygon") return [geometry.coordinates];
    if (geometry.type === "MultiPolygon") return geometry.coordinates;
    return [];
}


function geometryCenter(geometry) {
    const points = polygons(geometry).flat(2);
    const xs = points.map(point => point[0]);
    const ys = points.map(point => point[1]);
    return { lon: (Math.min(...xs) + Math.max(...xs)) / 2, lat: (Math.min(...ys) + Math.max(...ys)) / 2 };
}


function localPoint(point, center) {
    const x = (point[0] - center.lon) * 111320 * Math.cos(center.lat * Math.PI / 180);
    const y = (point[1] - center.lat) * 110540;
    return [x, y];
}


function scaleGeometry(geometry, center, factor) {
    const transform = point => [
        center.lon + (point[0] - center.lon) * factor,
        center.lat + (point[1] - center.lat) * factor,
    ];
    return {
        type: geometry.type,
        coordinates: geometry.type === "Polygon"
            ? geometry.coordinates.map(ring => ring.map(transform))
            : geometry.coordinates.map(polygon => polygon.map(ring => ring.map(transform))),
    };
}


function deriveBelowGroundCompartments() {
    if (currentProfile === "mumbai") return []; // No verified Mumbai basement geometry.
    if (!currentBuilding?.geometry) return [];
    const center = geometryCenter(currentBuilding.geometry);
    const base = currentBuilding.geometry;
    const basementCode = String(currentBuilding.properties?.basement_type_code || "");
    const basementLabel = basementCode === "0" ? "PLUTO: no basement" : basementCode === "2" ? "PLUTO below-grade full basement" : basementCode === "4" ? "PLUTO below-grade partial basement" : basementCode ? `PLUTO basement type ${basementCode}` : "No source basement type";
    return [
        { number: -2, label: "B2 · Deep parking / services", factor: 0.88 },
        { number: -1, label: `B1 · Basement parking / plant · ${basementLabel}`, factor: 0.95 },
    ].map(item => ({
        type: "Feature",
        geometry: scaleGeometry(base, center, item.factor),
        properties: {
            profile_id: currentProfile,
            floor_number: item.number,
            floor_label: item.label,
            compartment_type: "BASEMENT_PARKING_DERIVED",
            relative_z_min_m: item.number === -2 ? -7 : -3.4,
            relative_z_max_m: item.number === -2 ? -4 : -0.4,
            floor_height_m: 3,
            floor_area_m2: null,
            volume_m3: null,
            prototype_id: `P3D-${currentProfile.toUpperCase()}-${currentBuilding.properties.building_id}-B${Math.abs(item.number)}`,
            geometry_source: "DERIVED_DEMO",
            basement_type_code: basementCode || null,
            basement_type_source: basementCode ? "NYC_DCP_PLUTO_BSMTCODE" : "NOT_AVAILABLE",
            is_synthetic: true,
            is_official: false,
        },
    }));
}


function shapesForGeometry(geometry, center) {
    return polygons(geometry).map(rings => {
        const outer = rings[0].map(point => localPoint(point, center));
        const shape = new THREE.Shape();
        outer.forEach(([x, y], index) => index ? shape.lineTo(x, y) : shape.moveTo(x, y));
        shape.closePath();
        for (const holeRing of rings.slice(1)) {
            const hole = new THREE.Path();
            holeRing.map(point => localPoint(point, center)).forEach(([x, y], index) => index ? hole.lineTo(x, y) : hole.moveTo(x, y));
            hole.closePath();
            shape.holes.push(hole);
        }
        return shape;
    });
}


function addVolume(feature, color, opacity, kind, center, yOffset = 0) {
    const properties = feature.properties || {};
    const height = Number(properties.floor_height_m || properties.relative_z_max_m - properties.relative_z_min_m || 3);
    const y = Number(properties.relative_z_min_m || 0) + yOffset;
    for (const shape of shapesForGeometry(feature.geometry, center)) {
        const geometry = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false });
        geometry.rotateX(-Math.PI / 2);
        const material = new THREE.MeshStandardMaterial({ color, transparent: opacity < 1, opacity, roughness: 0.72, metalness: 0.05 });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.y = y;
        mesh.userData = { kind, properties, baseColor: color, baseOpacity: opacity };
        modelGroup.add(mesh);
        modelMeshes.push(mesh);
        if (kind === "floor" || kind === "unit" || kind === "below") {
            const edgeGeometry = new THREE.EdgesGeometry(geometry);
            const edgeMaterial = new THREE.LineBasicMaterial({
                color: kind === "below" ? 0xb59cff : (kind === "floor" ? 0x07355b : 0xd5ffff),
                transparent: true,
                opacity: kind === "below" ? 0.72 : 0.9,
            });
            const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial);
            edges.position.copy(mesh.position);
            modelGroup.add(edges);
        }
    }
}


function addSourceFootprint(feature, center, selected = false) {
    for (const shape of shapesForGeometry(feature.geometry, center)) {
        const geometry = new THREE.ShapeGeometry(shape);
        geometry.rotateX(-Math.PI / 2);
        const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
            color: selected ? 0x90adb2 : 0x33434b, transparent: true,
            opacity: selected ? 0.8 : 0.65, side: THREE.DoubleSide,
        }));
        mesh.position.y = 0.02; // Drawing offset only, not a building height.
        modelGroup.add(mesh);
    }
}


function addContextBuilding(feature, center) {
    const properties = feature.properties || {};
    const buildingId = String(properties.building_id || "");
    if (!buildingId || buildingId === String(currentBuilding?.properties?.building_id)) return;
    const height = currentProfile === "mumbai" ? Number(properties.selected_height_m)
        : Math.max(2.5, Math.min(ward3DMode ? 80 : 42, Number(properties.selected_height_m || properties.height_m || properties.floor_count * 3 || 6)));
    if (currentProfile === "mumbai" && !(height > 0)) return addSourceFootprint(feature, center);
    for (const shape of shapesForGeometry(feature.geometry, center)) {
        const geometry = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false });
        geometry.rotateX(-Math.PI / 2);
        const material = new THREE.MeshStandardMaterial({ color: 0x1d5a7b, transparent: true, opacity: 0.38, roughness: 0.9, metalness: 0 });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.y = 0;
        modelGroup.add(mesh);
        const edges = new THREE.LineSegments(
            new THREE.EdgesGeometry(geometry),
            new THREE.LineBasicMaterial({ color: 0x397c9b, transparent: true, opacity: 0.5 })
        );
        edges.position.copy(mesh.position);
        modelGroup.add(edges);
    }
}


function addSelectedBuildingMass(center) {
    if (!currentBuilding?.geometry || currentFloors.length) return;
    const properties = currentBuilding.properties || {};
    const height = currentProfile === "mumbai" ? Number(properties.selected_height_m)
        : Math.max(4, Math.min(36, Number(properties.selected_height_m || properties.height_m || 6)));
    if (currentProfile === "mumbai" && !(height > 0)) return addSourceFootprint(currentBuilding, center, true);
    for (const shape of shapesForGeometry(currentBuilding.geometry, center)) {
        const geometry = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false });
        geometry.rotateX(-Math.PI / 2);
        const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0x2d8c99, transparent: true, opacity: 0.78, roughness: 0.7, metalness: 0.05 }));
        modelGroup.add(mesh);
        modelGroup.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({ color: 0x73f0df, transparent: true, opacity: 0.95 })));
    }
}


function renderContextBuildings(center) {
    if ((isolateBuilding && !ward3DMode) || !currentBuilding) return;
    const selectedId = String(currentBuilding.properties?.building_id || "");
    const nearby = contextBuildings
        .filter(feature => String(feature.properties?.building_id || "") !== selectedId)
        .map(feature => {
            const c = geometryCenter(feature.geometry);
            const [x, y] = localPoint([c.lon, c.lat], center);
            return { feature, distance: Math.hypot(x, y) };
        })
        .filter(item => (currentProfile === "mumbai" && ward3DMode) || item.distance < (ward3DMode ? 2800 : 420))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, currentProfile === "mumbai" && ward3DMode ? contextBuildings.length : ward3DMode ? 900 : 150);
    nearby.forEach(item => addContextBuilding(item.feature, center));
}


function renderContextRoads(center) {
    if ((isolateBuilding && !ward3DMode) || !contextRoads.length) return;
    const nearby = contextRoads
        .map(feature => {
            const coordinates = feature.geometry?.coordinates || [];
            const middle = coordinates[Math.floor(coordinates.length / 2)] || coordinates[0];
            if (!middle) return null;
            const [x, z] = localPoint(middle, center);
            return { feature, distance: Math.hypot(x, z) };
        })
        .filter(item => item && ((currentProfile === "mumbai" && ward3DMode) || item.distance < (ward3DMode ? 3000 : 480)))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, currentProfile === "mumbai" && ward3DMode ? contextRoads.length : ward3DMode ? 700 : 240);
    nearby.forEach(item => {
        const points = (item.feature.geometry.coordinates || []).map(point => {
            const [x, z] = localPoint(point, center);
            return new THREE.Vector3(x, 0.035, -z);
        });
        if (points.length < 2) return;
        const line = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(points),
            new THREE.LineBasicMaterial({ color: 0xc89150, transparent: true, opacity: 0.58 })
        );
        modelGroup.add(line);
    });
}


function renderWard3D(center) {
    const geometry = wardFeature?.geometry || {
        type: "Polygon",
        coordinates: [[
            [currentProfileConfig.bbox[1], currentProfileConfig.bbox[0]],
            [currentProfileConfig.bbox[3], currentProfileConfig.bbox[0]],
            [currentProfileConfig.bbox[3], currentProfileConfig.bbox[2]],
            [currentProfileConfig.bbox[1], currentProfileConfig.bbox[2]],
            [currentProfileConfig.bbox[1], currentProfileConfig.bbox[0]],
        ]],
    };
    if (!geometry || isolateBuilding) return;
    for (const rings of polygons(geometry)) {
        const points = rings[0].map(point => {
            const [x, z] = localPoint(point, center);
            return new THREE.Vector3(x, 0.11, -z);
        });
        if (points.length < 3) continue;
        const line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: 0x34262d, transparent: true, opacity: 0.9 }));
        modelGroup.add(line);
        const shape = new THREE.Shape();
        rings[0].map(point => localPoint(point, center)).forEach(([x, z], index) => index ? shape.lineTo(x, -z) : shape.moveTo(x, -z));
        shape.closePath();
        const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: 0x5b4350, transparent: true, opacity: ward3DMode ? 0.12 : 0.045, depthWrite: false, side: THREE.DoubleSide }));
        // ShapeGeometry is created in XY; rotate it onto the horizontal XZ ground plane.
        mesh.rotation.x = -Math.PI / 2;
        mesh.position.y = 0.105;
        modelGroup.add(mesh);
    }
}


function renderBelowGroundGuides(compartments, center) {
    for (const feature of compartments) {
        const y = Number(feature.properties?.relative_z_min_m || 0) + 0.02;
        for (const rings of polygons(feature.geometry)) {
            const points = rings[0].map(point => {
                const [x, z] = localPoint(point, center);
                return new THREE.Vector3(x, y, -z);
            });
            if (points.length < 3) continue;
            modelGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: feature.properties?.floor_number === -1 ? 0xe1b86a : 0xb59cff, transparent: true, opacity: 0.9 })));
        }
    }
}


function updateSelectedIdBanner(label, value) {
    const banner = document.getElementById("selected-id-banner");
    if (!banner) return;
    banner.innerHTML = `<span>${safe(label)}</span><strong>${safe(value)}</strong>`;
}


function renderParcel3D(center) {
    disposeGroup(parcelGroup);
    if (!selectedParcelLayer || selectedParcelStyle().weight === 0) return;
    const geometry = selectedParcelLayer.feature?.geometry;
    for (const polygon of polygons(geometry)) {
        const points = polygon[0].map(point => {
            const [x, z] = localPoint(point, center);
            return new THREE.Vector3(x, 0.08, -z);
        });
        const line = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(points),
            new THREE.LineBasicMaterial({ color: 0xa08d6f, transparent: true, opacity: 0.9 })
        );
        parcelGroup.add(line);
    }
}


function renderGroundSurface(center) {
    if (!currentBuilding) return;
    for (const shape of shapesForGeometry(currentBuilding.geometry, center)) {
        const geometry = new THREE.ShapeGeometry(shape);
        geometry.rotateX(-Math.PI / 2);
        const material = new THREE.MeshBasicMaterial({
            color: 0x5de0d2,
            transparent: true,
            opacity: 0.035,
            side: THREE.DoubleSide,
            depthWrite: false,
        });
        const surface = new THREE.Mesh(geometry, material);
        surface.position.y = 0.1;
        modelGroup.add(surface);
    }
}


function addUnitDeck(floor, center) {
    if (!floor?.geometry) return;
    for (const shape of shapesForGeometry(floor.geometry, center)) {
        const geometry = new THREE.ExtrudeGeometry(shape, { depth: 0.14, bevelEnabled: false });
        geometry.rotateX(-Math.PI / 2);
        const material = new THREE.MeshStandardMaterial({
            color: 0x123f5c,
            transparent: true,
            opacity: 0.72,
            roughness: 0.84,
            metalness: 0.05,
        });
        const deck = new THREE.Mesh(geometry, material);
        deck.position.y = Number(floor.properties?.relative_z_min_m || 0) - 0.08;
        modelGroup.add(deck);
        const edges = new THREE.LineSegments(
            new THREE.EdgesGeometry(geometry),
            new THREE.LineBasicMaterial({ color: 0x5aa9bd, transparent: true, opacity: 0.58 })
        );
        edges.position.copy(deck.position);
        modelGroup.add(edges);
    }
}


function insetUnitFeature(feature, factor = 0.965) {
    const center = geometryCenter(feature.geometry);
    return { ...feature, geometry: scaleGeometry(feature.geometry, center, factor) };
}


async function renderModel() {
    disposeGroup(modelGroup);
    modelMeshes = [];
    if (!currentBuilding) return;
    const center = geometryCenter(currentBuilding.geometry);
    renderParcel3D(center);
    renderWard3D(center);
    renderContextRoads(center);
    renderContextBuildings(center);
    addSelectedBuildingMass(center);
    if (belowGroundEnabled) {
        renderGroundSurface(center);
        belowGroundCompartments = deriveBelowGroundCompartments();
        renderBelowGroundGuides(belowGroundCompartments, center);
        for (const feature of belowGroundCompartments) {
            addVolume(feature, 0x7659b6, 0.62, "below", center);
        }
    }
    if (viewMode === "UNIT") {
        addUnitDeck(selectedFloor(), center);
        for (const feature of currentUnits) {
            const selected = feature.properties?.prototype_unit_uid === selectedUnitUid;
            const color = selected ? UNIT_SELECTED_COLOR : UNIT_DEFAULT_COLOR;
            const opacity = belowGroundEnabled ? (selected ? 0.38 : 0.16) : (selected ? 1 : 0.84);
            addVolume(insetUnitFeature(feature), color, opacity, "unit", center);
        }
    } else {
        for (const feature of currentFloors) {
            const number = Number(feature.properties?.floor_number);
            const selected = number === selectedFloorNumber;
            const offset = exploded ? number * 0.35 : 0;
            const opacity = viewMode === "FLOOR" && !selected ? 0.08 : (selected ? 0.98 : 0.68);
            const cutawayOpacity = belowGroundEnabled ? Math.min(opacity, 0.16) : opacity;
            const color = selected ? 0x168fe6 : 0x17679f;
            addVolume(feature, color, cutawayOpacity, "floor", center, offset);
        }
    }
    if (!cameraReadyForBuilding) {
        focusThreeModel();
        cameraReadyForBuilding = true;
    }
}


// Fit source geometry using both viewport angles, including portrait-sized viewers.
// This changes camera framing only; it never assigns missing building heights.
function fitMumbaiBounds(bounds) {
    const sphere = bounds.getBoundingSphere(new THREE.Sphere());
    const verticalAngle = THREE.MathUtils.degToRad(camera.fov) / 2;
    const horizontalAngle = Math.atan(Math.tan(verticalAngle) * camera.aspect);
    const distance = Math.max(20, sphere.radius) * 1.15 / Math.sin(Math.min(verticalAngle, horizontalAngle));
    const direction = new THREE.Vector3(1, 0.8, 1).normalize();
    camera.far = Math.max(5000, distance + sphere.radius * 3);
    camera.updateProjectionMatrix();
    controls.target.copy(sphere.center);
    camera.position.copy(sphere.center).addScaledVector(direction, distance);
    camera.lookAt(sphere.center);
    controls.update();
}

function focusThreeModel() {
    if (!currentBuilding) return;
    if (currentProfile === "mumbai") {
        const center = geometryCenter(currentBuilding.geometry);
        const bounds = new THREE.Box3();
        const height = Number(currentBuilding.properties?.selected_height_m) || 0;
        for (const point of polygons(currentBuilding.geometry).flat(2)) {
            const [x, z] = localPoint(point, center);
            bounds.expandByPoint(new THREE.Vector3(x, 0, -z));
            bounds.expandByPoint(new THREE.Vector3(x, height, -z));
        }
        fitMumbaiBounds(bounds);
        return;
    }
    const height = Math.max(15, Number(currentBuilding.properties?.selected_height_m || currentBuilding.properties?.height_m || (Number(currentBuilding.properties?.floor_count || 0) * 3.2) || 30));
    const radius = isolateBuilding ? Math.max(45, height * 1.15) : Math.max(95, height * 1.35);
    camera.position.set(radius, Math.max(35, height * 0.72), radius);
    controls.target.set(0, isolateBuilding ? height * 0.35 : height * 0.22, 0);
    controls.update();
}


function focusBelowGround() {
    if (!controls || !camera) return;
    const targetY = belowGroundEnabled ? -3.2 : 0.22;
    const delta = targetY - controls.target.y;
    controls.target.y = targetY;
    camera.position.y += delta;
    controls.update();
}


function focusWard3D() {
    if (!currentBuilding || !currentProfileConfig) return;
    ward3DMode = true;
    isolateBuilding = false;
    document.getElementById("isolate-btn").textContent = "Isolate Building";
    document.getElementById("isolate-btn").classList.remove("active-control");
    document.getElementById("ward-view-btn").classList.add("active-control");
    renderModel();
    const buildingCenter = geometryCenter(currentBuilding.geometry);
    const wardGeometry = wardFeature?.geometry || {
        type: "Polygon",
        coordinates: [[
            [currentProfileConfig.bbox[1], currentProfileConfig.bbox[0]],
            [currentProfileConfig.bbox[3], currentProfileConfig.bbox[0]],
            [currentProfileConfig.bbox[3], currentProfileConfig.bbox[2]],
            [currentProfileConfig.bbox[1], currentProfileConfig.bbox[2]],
            [currentProfileConfig.bbox[1], currentProfileConfig.bbox[0]],
        ]],
    };
    const wardCenter = geometryCenter(wardGeometry);
    const [tx, tz] = localPoint([wardCenter.lon, wardCenter.lat], buildingCenter);
    const wardPoints = polygons(wardGeometry).flat(2).map(point => localPoint(point, buildingCenter));
    const span = Math.max(...wardPoints.map(point => Math.hypot(point[0] - tx, point[1] - tz)), 120);
    if (currentProfile === "mumbai") {
        const bounds = new THREE.Box3();
        for (const [x, z] of wardPoints) bounds.expandByPoint(new THREE.Vector3(x, 0, -z));
        for (const feature of contextBuildings) {
            const height = Number(feature.properties?.selected_height_m) || 0;
            for (const point of polygons(feature.geometry).flat(2)) {
                const [x, z] = localPoint(point, buildingCenter);
                bounds.expandByPoint(new THREE.Vector3(x, height, -z));
            }
        }
        fitMumbaiBounds(bounds);
    } else {
        controls.target.set(tx, 0.2, -tz);
        camera.position.set(tx + span * 1.35, span * 1.05, -tz + span * 1.35);
        controls.update();
    }
    document.getElementById("scene-note").textContent = `${currentProfileConfig.label} Ward 3D: boundary footprint is the horizontal z=0 ground reference; buildings and streets are shown in context.`;
    setStatus(`${currentProfileConfig.label} Ward 3D view`);
}


function zoomThree(factor) {
    if (!camera || !controls) return;
    const offset = camera.position.clone().sub(controls.target).multiplyScalar(factor);
    camera.position.copy(controls.target).add(offset);
    controls.update();
}


function onThreeClick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hit = raycaster.intersectObjects(modelMeshes, false)[0];
    if (!hit) return;
    const properties = hit.object.userData.properties;
    if (hit.object.userData.kind === "unit") selectUnit(properties.prototype_unit_uid);
    else selectFloor(Number(properties.floor_number));
}


async function setViewMode(mode) {
    if (mode === "UNIT" && currentProfile !== "manhattan") {
        setStatus("Unit geometry is not available for this profile");
        return;
    }
    viewMode = mode;
    ["BUILDING", "FLOOR", "UNIT"].forEach(name => {
        document.getElementById(`${name.toLowerCase()}-mode-btn`).classList.toggle("active-control", name === mode);
    });
    if (mode === "UNIT" && selectedFloorNumber !== null) await loadFloorUnits(selectedFloorNumber);
    await renderModel();
    renderDossier();
}


async function loadFloorUnits(floorNumber) {
    if (currentProfile !== "manhattan" || !currentBuilding) {
        currentUnits = [];
        return;
    }
    const buildingId = currentBuilding.properties.building_id;
    const result = await api(`/api/buildings/${encodeURIComponent(buildingId)}/floors/${floorNumber}/units`);
    currentUnits = result.features || [];
    if (selectedUnitUid && !currentUnits.some(item => item.properties.prototype_unit_uid === selectedUnitUid)) selectedUnitUid = null;
}


async function selectFloor(floorNumber) {
    selectedFloorNumber = Number(floorNumber);
    selectedUnitUid = null;
    const floor = selectedFloor();
    updateSelectedIdBanner("Selected floor", floor?.properties?.prototype_id || `Floor ${floorNumber}`);
    if (viewMode === "UNIT") await loadFloorUnits(selectedFloorNumber);
    await renderModel();
    renderDossier();
}


async function selectUnit(uid) {
    if (!currentBuilding || currentProfile !== "manhattan") {
        setStatus("Select a Manhattan building before choosing a unit");
        return;
    }
    selectedUnitUid = uid;
    if (selectedFloorNumber !== null && !currentUnits.some(item => item.properties?.prototype_unit_uid === uid)) {
        await loadFloorUnits(selectedFloorNumber);
    }
    viewMode = "UNIT";
    updateSelectedIdBanner("Selected 3D ULPIN", uid);
    ["BUILDING", "FLOOR", "UNIT"].forEach(name => {
        document.getElementById(`${name.toLowerCase()}-mode-btn`).classList.toggle("active-control", name === "UNIT");
    });
    await renderModel();
    renderDossier();
}


function selectedFloor() {
    return currentFloors.find(item => Number(item.properties?.floor_number) === Number(selectedFloorNumber));
}


function selectedUnit() {
    return currentUnits.find(item => item.properties?.prototype_unit_uid === selectedUnitUid);
}


function floorPanel() {
    const floor = selectedFloor()?.properties;
    if (!floor) return "<div class=\"empty-state\">Select a floor.</div>";
    const absolute = floor.absolute_z_min_m === null || floor.absolute_z_min_m === undefined
        ? "Pending real ground elevation"
        : `${numeric(floor.absolute_z_min_m, 2)} – ${numeric(floor.absolute_z_max_m, 2, " m")}`;
    const warning = currentProfile === "mumbai" ? '<div class="synthetic-warning">Source-derived display stratum: equal division of tagged height and level count, not a verified floor boundary or floor plan.</div>' : "";
    return warning + [
        field("Floor", `<strong>${safe(floor.floor_number)}</strong>`),
        field("Relative Z", `${numeric(floor.relative_z_min_m, 2)} – ${numeric(floor.relative_z_max_m, 2, " m")}`),
        field("Absolute Z", absolute),
        field("Area", numeric(floor.floor_area_m2 || floor.footprint_area_m2, 2, " m²")),
        field("Volume", numeric(floor.volume_m3, 2, " m³")),
        field("Height source", safe(floor.floor_height_source || "SOURCE_ATTRIBUTE")),
        field("Prototype floor ID", `<span class="prototype-id">${safe(floor.prototype_id)}</span>`),
    ].join("");
}


function unitPanel() {
    if (currentProfile !== "manhattan") return "<div class=\"empty-state\">No unit geometry is loaded for this profile.</div>";
    const unit = selectedUnit()?.properties;
    const warning = `<div class="synthetic-warning">Synthetic unit subdivision for prototype demonstration. Not an authoritative floor plan or ownership boundary.</div>`;
    if (!unit) return `${warning}<div class="empty-state">Enter Unit mode and select a unit block.</div>`;
    return warning + [
        field("Unit", `<strong>${safe(unit.unit_label)}</strong>`),
        field("Area", numeric(unit.unit_area_m2, 2, " m²")),
        field("Volume", numeric(unit.unit_volume_m3, 2, " m³")),
        field("Relative Z", `${numeric(unit.relative_z_min_m, 2)} – ${numeric(unit.relative_z_max_m, 2, " m")}`),
        field("Prototype Vertical UID", `<button type="button" class="ulpin-link" data-unit="${safe(unit.prototype_unit_uid)}">${safe(unit.prototype_unit_uid)}</button>`),
        field("Geometry source", safe(unit.unit_geometry_source)),
        field("Geometry confidence", safe(unit.synthetic_layout_confidence)),
        field("Ownership status", safe(unit.ownership_status)),
        field("Official identifier", unit.prototype_uid_is_official ? "YES" : "NO"),
    ].join("");
}


function mumbaiGeometryEvidence(p) {
    const available = p.footprint_agreement_pct != null;
    const agreement = Number(p.footprint_agreement_pct);
    const style = !available ? "" : agreement >= 70 ? "confidence-good" : agreement >= 40 ? "confidence-moderate" : "confidence-low";
    return `<div class="confidence-card mumbai-geometry-evidence">
        <div class="metric-label">Geometry evidence · footprint agreement</div>
        <div class="confidence-line"><div class="confidence-score">${available ? numeric(agreement, 2, "%") : "Not available"}</div>
        <div class="confidence-badge ${style}">${available ? "OSM / BMC overlap" : "No reference overlap"}</div></div>
        <div class="confidence-note">${available ? "Measured intersection ÷ union of the OSM footprint and best overlapping BMC footprint (IoU). This is not positional accuracy or verified building identity." : "No overlapping BMC reference footprint was found. A confidence score cannot be inferred."}</div>
        ${available ? field("BMC reference feature", safe(p.reference_building_id)) + field("Other overlapping footprints", safe(Number(p.overlapping_reference_count || 0) - 1)) : ""}
        ${field("Cadastral confidence", "Unavailable — no surveyed parcel reference")}
    </div>`;
}


function renderDossier() {
    const container = document.getElementById("dossier");
    if (!currentBuilding) {
        container.innerHTML = '<div class="empty-state">Select a building to inspect.</div>';
        return;
    }
    const p = currentBuilding.properties || {};
    const manhattan = currentProfile === "manhattan";
    const mumbai = currentProfile === "mumbai";
    const score = manhattan ? p.match_confidence_score : p.cadastral_confidence_score;
    const label = manhattan ? p.match_confidence_label : (mumbai ? "SOURCE_GEOMETRY" : p.cadastral_confidence_text);
    const lotSection = manhattan
        ? [field("Tax Lot", safe(p.tax_lot_id)), field("Borough / Block / Lot", `${safe(p.borough)} / ${safe(p.block)} / ${safe(p.lot)}`)]
        : (mumbai
            ? [field("Ward", `${safe(p.ward_label)} (MCGM official boundary)`), field("Source building", safe(p.source_building_id))]
            : [field("Parcel / survey no.", safe(p.official_parcel_no)), field("Boundary label", safe(p.cadastral_boundary_label))]);
    const floorRows = currentFloors.map(item => {
        const f = item.properties;
        return `<div class="floor-row ${Number(f.floor_number) === selectedFloorNumber ? "selected-floor-row" : ""}" data-floor="${f.floor_number}"><strong>Floor ${safe(f.floor_number)}</strong><br>${numeric(f.relative_z_min_m, 2)} – ${numeric(f.relative_z_max_m, 2, " m")}<br><span class="prototype-id">${safe(f.prototype_id)}</span></div>`;
    }).join("");
    const unitRows = currentUnits.map(item => {
        const u = item.properties;
        return `<button class="unit-row ${u.prototype_unit_uid === selectedUnitUid ? "selected-unit-row" : ""}" data-unit="${safe(u.prototype_unit_uid)}"><span class="unit-swatch"></span><strong>${safe(u.unit_label)}</strong><br><small>${numeric(u.unit_area_m2, 1, " m²")} · ${safe(u.unit_geometry_source)}</small></button>`;
    }).join("");
    const belowRows = belowGroundCompartments.map(item => {
        const p = item.properties;
        return `<div class="below-row"><span class="below-chip">${safe(`B${Math.abs(p.floor_number)}`)}</span><div><strong>${safe(p.floor_label)}</strong><small>Relative Z ${numeric(p.relative_z_min_m, 1)} to ${numeric(p.relative_z_max_m, 1, " m")} · derived demo geometry</small></div></div>`;
    }).join("");
    container.innerHTML = `
        <div class="dossier-section"><h3>Building</h3>
            ${field("Building ID", `<strong>${safe(p.building_id)}</strong>`)}
            ${manhattan ? field("NYC source BIN", safe(p.source_building_id)) : field("Building type", safe(p.building))}
            ${field("Address / name", safe(p.address || p.name))}
            ${field("Height", mumbai && p.selected_height_m == null ? "Not available — footprint only" : numeric(p.selected_height_m || p.height_m, 1, " m"))}
            ${field("Floors", safe(p.floor_count))}
            ${field("Floor source", safe(p.floor_count_source || p.floor_source))}
            ${field("Floor count estimated", (p.floor_count_is_estimated ?? p.is_floor_estimated) ? "YES" : "NO")}
            ${mumbai ? field("Vertical evidence", safe(p.vertical_evidence_status)) : ""}
            ${manhattan ? field("Basement evidence", p.basement_type_code ? `PLUTO code ${safe(p.basement_type_code)}` : "Not available") : ""}
        </div>
        <div class="dossier-section"><h3>${manhattan ? "Tax Lot Relationship" : (mumbai ? "Ward Relationship" : "Cadastral Relationship")}</h3>
            ${lotSection.join("")}
            ${mumbai ? "" : `${field("Building covered", numeric(p.building_covered_by_lot_pct || p.building_covered_by_parcel_pct, 2, "%"))}${field(occupancyLabel(manhattan), numeric(p.lot_occupied_by_building_pct || p.parcel_occupied_by_building_pct, 2, "%"))}`}
            ${mumbai ? mumbaiGeometryEvidence(p) : `<div class="confidence-card"><div class="metric-label">Geometry confidence</div><div class="confidence-line"><div class="confidence-score">${numeric(score, 1, "/100")}</div><div class="confidence-badge confidence-good">${safe(label)}</div></div><div class="confidence-note">Prototype geometric confidence — not legal or survey accuracy.</div></div>`}
        </div>
        <div class="dossier-section selected-floor-section"><h3>Selected Floor</h3><div id="selected-floor-details">${floorPanel()}</div></div>
        <div class="dossier-section below-ground-section"><h3>Below-ground compartments</h3><div class="below-ground-note">${mumbai ? "No verified basement count, depth or floor plan is loaded for this building. No basement geometry is generated." : `${belowGroundEnabled ? "Derived basement/parking volumes are visible; above-ground floors are faded for a cutaway view." : "Toggle Show Below Ground to reveal derived basement/parking volumes."} Not official building plans.`}</div>${belowRows || '<div class="empty-state">No below-ground volumes currently displayed.</div>'}</div>
        <div class="dossier-section"><h3>Vertical Unit</h3><div id="selected-unit-details">${unitPanel()}</div>${unitRows ? `<div class="unit-list">${unitRows}</div>` : ""}</div>
        <div class="dossier-section"><h3>Data Provenance</h3>
            ${field("Building geometry", safe(p.building_geometry_source || (manhattan ? "NYC_OTI_BUILDING_FOOTPRINTS" : "OpenStreetMap — non-cadastral")))}
            ${field(manhattan ? "Lot geometry" : (mumbai ? "Ward geometry" : "Parcel source"), safe(manhattan ? p.tax_lot_source : (mumbai ? p.ward_source : p.parcel_source)))}
            ${field("Height", safe(p.selected_height_source || p.height_source))}
            ${field("Ground elevation", safe(p.ground_elevation_source || p.ground_elevation_status))}
            ${field("Unit geometry", safe(p.unit_geometry_mode || "NOT_AVAILABLE"))}
            ${mumbai ? field("Public floor plan", safe(p.public_floor_plan_status || "NOT_AVAILABLE")) : ""}
            ${field("Vertical reference", safe(p.vertical_reference || systemCapabilities?.absolute_z))}
        </div>
        <div class="dossier-section"><h3>Vertical Identities</h3><div class="floor-list">${floorRows || '<div class="empty-state">No floor model.</div>'}</div></div>
        <div class="disclaimer">${manhattan ? "NYC identifiers are retained only as source attributes. Prototype floor and unit identifiers are not official NYC or ULPIN identifiers." : (mumbai ? "MCGM G/South boundary and BMC reference footprints are official source context; displayed buildings and roads come from OpenStreetMap. Only source heights are extruded. Floor strata are equal divisions of source height, not surveyed floor plans. Unknown heights remain flat; no units or basements are invented." : "Cadastral polygons may represent survey or development parcels rather than individual property plots. Prototype 3D identifiers are not official ULPINs.")}</div>`;
    container.querySelectorAll("[data-floor]").forEach(row => row.addEventListener("click", () => selectFloor(Number(row.dataset.floor))));
    container.querySelectorAll("[data-unit]").forEach(row => row.addEventListener("click", () => selectUnit(row.dataset.unit)));
}


function occupancyLabel(isManhattan) {
    return isManhattan ? "Lot occupied by building" : "Parcel occupied by building";
}


async function selectBuilding(buildingId) {
    setStatus(`Loading ${buildingId}…`);
    try {
        const knownBuilding = contextBuildings.find(f => f.properties?.building_id === buildingId);
        const noMumbaiFloorModel = currentProfile === "mumbai" && knownBuilding?.properties?.floor_model_available === false;
        const [details, floorResult] = await Promise.all([
            api(`/api/buildings/${encodeURIComponent(buildingId)}`),
            noMumbaiFloorModel ? Promise.resolve({ features: [] }) : api(`/api/buildings/${encodeURIComponent(buildingId)}/floors`).catch(() => ({ features: [] })),
        ]);
        currentBuilding = details.building;
        document.getElementById("viewer-message").style.display = "none";
        currentFloors = floorResult.features || [];
        document.getElementById("floor-mode-btn").disabled = currentProfile === "mumbai" && !currentFloors.length;
        currentUnits = [];
        selectedUnitUid = null;
        ward3DMode = false;
        document.getElementById("ward-view-btn").classList.remove("active-control");
        selectedFloorNumber = currentFloors.length ? Number(currentFloors[0].properties.floor_number) : null;
        viewMode = "BUILDING";
        cameraReadyForBuilding = false;
        surveyContextEnabled = false;
        updateSelectedIdBanner("Selected building", buildingId);
        document.getElementById("viewer-title").textContent = buildingId;
        document.getElementById("viewer-subtitle").textContent = currentProfile === "manhattan"
            ? `NYC tax lot ${safe(currentBuilding.properties.tax_lot_id)} • ${safe(currentBuilding.properties.match_confidence_label)}`
            : (currentProfile === "mumbai"
                ? `${currentBuilding.properties.name || currentBuilding.properties.source_building_id} • G/South`
                : `${safe(currentBuilding.properties.cadastral_boundary_label)} • ${safe(currentBuilding.properties.cadastral_confidence_text)}`);
        highlightMapBuilding(buildingId);
        focusMapBuilding();
        await setViewMode("BUILDING");
        if (belowGroundEnabled) focusBelowGround();
        document.getElementById("survey-context-btn").classList.remove("active-control");
        document.getElementById("scene-note").textContent = currentProfile === "manhattan"
            ? "Official NYC footprint and tax-lot context. Unit mode uses labelled synthetic subdivisions; Show Below Ground uses the PLUTO basement-type code when available but keeps B1/B2 as clearly derived visual volumes because basement level counts are not published. Drag to orbit, right-drag to pan, wheel to zoom."
            : (currentProfile === "mumbai"
                ? "Official MCGM G/South ward and OSM streets. Buildings with source heights are shown at those heights; missing heights stay flat. Floor strata require both height and levels and are not surveyed floor plans. No invented units or basements. Drag to orbit, right-drag to pan, wheel to zoom."
                : "Hyderabad cadastral geometry is shown according to its contextual confidence and visibility rule. Show Below Ground fades the upper stack and focuses B1/B2 derived volumes. Drag to orbit, right-drag to pan, wheel to zoom.");
        setStatus(`${buildingId} loaded`);
    } catch (error) {
        console.error(error);
        setStatus("Load failed");
    }
}


function showSurveyContext() {
    surveyContextEnabled = true;
    if (selectedParcelLayer) {
        selectedParcelLayer.setStyle(selectedParcelStyle());
        map.fitBounds(selectedParcelLayer.getBounds(), { padding: [30, 30] });
    }
    document.getElementById("survey-context-btn").classList.add("active-control");
    renderModel();
}


function toggleExplode() {
    exploded = !exploded;
    document.getElementById("explode-btn").textContent = exploded ? "Collapse" : "Explode";
    renderModel();
}


function toggleBelowGround() {
    if (currentProfile === "mumbai") {
        setStatus("No verified Mumbai basement geometry is available");
        return;
    }
    belowGroundEnabled = !belowGroundEnabled;
    document.getElementById("below-ground-btn").textContent = belowGroundEnabled ? "Hide Below Ground" : "Show Below Ground";
    document.getElementById("below-ground-btn").classList.toggle("active-control", belowGroundEnabled);
    if (belowGroundEnabled) {
        belowGroundCompartments = deriveBelowGroundCompartments();
        setStatus("Derived basement + parking view enabled — cutaway focused below ground");
    } else {
        belowGroundCompartments = [];
        setStatus("Below-ground view hidden");
    }
    renderModel();
    renderDossier();
    focusBelowGround();
}


function toggleIsolation() {
    isolateBuilding = !isolateBuilding;
    ward3DMode = false;
    document.getElementById("ward-view-btn").classList.remove("active-control");
    const button = document.getElementById("isolate-btn");
    button.textContent = isolateBuilding ? "Show Surroundings" : "Isolate Building";
    button.classList.toggle("active-control", isolateBuilding);
    cameraReadyForBuilding = false;
    renderModel();
    if (belowGroundEnabled) focusBelowGround();
    setStatus(isolateBuilding ? "Isolated building view" : "Surrounding context view");
}


async function loadStats() {
    const stats = await api("/api/stats");
    document.getElementById("stat-buildings").textContent = stats.total_buildings;
    document.getElementById("stat-floors").textContent = stats.total_floor_units;
    document.getElementById("stat-full").textContent = stats.vertical_buildings ?? stats.processing_status?.FULL_3D_CADASTRAL ?? 0;
    document.getElementById("stat-errors").textContent = stats.topology_errors;
}


async function loadCapabilities() {
    systemCapabilities = await api("/api/system/capabilities");
    const entries = { ...systemCapabilities.sources, PostGIS: systemCapabilities.postgis, DEM: systemCapabilities.dem,
        "Ground elevation": systemCapabilities.ground_elevation, BIM: systemCapabilities.bim,
        "OpenTopography": systemCapabilities.opentopography, LiDAR: systemCapabilities.lidar,
        "Unit geometry": systemCapabilities.unit_geometry };
    document.getElementById("capabilities").innerHTML = `<div class="dossier-section"><h3>${safe(currentProfileConfig.label)} Capabilities</h3><div class="capability-grid">${Object.entries(entries).map(([name, value]) => `<span>${safe(name)}</span><span class="capability-state">${safe(value)}</span>`).join("")}</div></div>`;
}


function renderProfileControls() {
    document.getElementById("profile-switch").innerHTML = profiles.map(profile => `<button class="profile-btn ${profile.profile_id === currentProfile ? "active-profile" : ""}" data-profile="${profile.profile_id}">${safe(profile.label)}</button>`).join("");
    document.querySelectorAll("[data-profile]").forEach(button => button.addEventListener("click", () => switchProfile(button.dataset.profile)));
}


function renderHeroButtons() {
    const heroes = currentProfileConfig.hero_buildings || [];
    document.getElementById("hero-buttons").innerHTML = `<span>Demo</span>${heroes.map(id => `<button class="hero-btn" data-hero="${safe(id)}">${safe(id)}</button>`).join("")}`;
    document.querySelectorAll("[data-hero]").forEach(button => button.addEventListener("click", () => selectBuilding(button.dataset.hero)));
}


async function switchProfile(profileId) {
    if (!profiles.some(profile => profile.profile_id === profileId)) return;
    setStatus(`Switching to ${profileId}…`);
    currentProfile = profileId;
    currentProfileConfig = profiles.find(profile => profile.profile_id === profileId);
    currentBuilding = null;
    document.getElementById("viewer-message").style.display = "block";
    currentFloors = [];
    currentUnits = [];
    selectedFloorNumber = null;
    selectedUnitUid = null;
    viewMode = "BUILDING";
    exploded = false;
    isolateBuilding = false;
    ward3DMode = false;
    cameraReadyForBuilding = false;
    belowGroundEnabled = false;
    belowGroundCompartments = [];
    disposeGroup(modelGroup);
    disposeGroup(parcelGroup);
    renderProfileControls();
    renderHeroButtons();
    document.getElementById("map-subtitle").textContent = currentProfile === "manhattan"
        ? "NYC building footprints + Digital Tax Map lots"
        : (currentProfile === "mumbai" ? "G/South · Worli–Lower Parel · BMC + OSM sources"
            : (currentProfile === "amsterdam" ? "PDOK BAG/BGT + AHN open-data benchmark"
                : "OSM building footprints + Telangana cadastral context"));
    document.getElementById("dossier-subtitle").textContent = currentProfile === "manhattan"
        ? "Building, floor and synthetic unit demonstration"
        : (currentProfile === "mumbai" ? "Building, floors and MCGM/OSM source provenance"
            : (currentProfile === "amsterdam" ? "Open-data sources; local artifacts not loaded" : "Building, floors and cadastral interpretation"));
    document.getElementById("viewer-title").textContent = "No building selected";
    document.getElementById("viewer-subtitle").textContent = currentProfile === "amsterdam"
        ? "Download PDOK/AHN artifacts to enable the 3D view"
        : "Select a building from the map";
    document.getElementById("unit-mode-btn").disabled = currentProfile !== "manhattan";
    document.getElementById("floor-mode-btn").disabled = false;
    for (const id of ["below-ground-btn", "below-focus-btn"]) {
        document.getElementById(id).disabled = currentProfile === "mumbai";
        document.getElementById(id).title = currentProfile === "mumbai" ? "Unavailable: no verified basement geometry is loaded" : (id === "below-ground-btn" ? "Show derived basement and parking compartments" : "Center the camera on the below-ground cutaway");
    }
    document.getElementById("below-ground-btn").textContent = "Show Below Ground";
    document.getElementById("below-ground-btn").classList.remove("active-control");
    document.getElementById("isolate-btn").textContent = "Isolate Building";
    document.getElementById("isolate-btn").classList.remove("active-control");
    document.getElementById("ward-view-btn").classList.remove("active-control");
    updateSelectedIdBanner("Selected 3D identity", "Select a building");
    await Promise.all([loadStats(), loadCapabilities(), loadMapData()]);
    const hero = currentProfileConfig.default_hero || currentProfileConfig.hero_buildings?.[0];
    if (hero) await selectBuilding(hero);
    renderDossier();
    setStatus(contextBuildings.length ? `${currentProfileConfig.label} ready` : `${currentProfileConfig.label}: local data not loaded`);
}


async function performSearch() {
    const query = document.getElementById("search-input").value.trim();
    if (!query) return;
    setStatus(`Searching ${query}…`);
    try {
        let result = await api(`/api/search?q=${encodeURIComponent(query)}`);
        let resultProfile = currentProfile;
        if (!result.buildings?.length && !result.floor_units?.length && !result.units?.length) {
            for (const profile of profiles.map(item => item.profile_id).filter(id => id !== currentProfile)) {
                const alternate = await api(`/api/search?q=${encodeURIComponent(query)}&profile=${profile}`, false).catch(() => null);
                if (alternate?.buildings?.length || alternate?.floor_units?.length || alternate?.units?.length) {
                    result = alternate;
                    resultProfile = profile;
                    break;
                }
            }
        }
        if (resultProfile !== currentProfile) await switchProfile(resultProfile);
        const normalized = query.toLowerCase();
        const exactUnit = (result.units || []).find(item => String(item.properties?.prototype_unit_uid || "").toLowerCase() === normalized);
        const exactFloor = (result.floor_units || []).find(item => ["prototype_id", "prototype_3d_ulpin", "floor_id"].some(key => String(item.properties?.[key] || "").toLowerCase() === normalized));
        const exactBuilding = (result.buildings || []).find(item => ["building_id", "source_building_id", "tax_lot_id", "official_parcel_no"].some(key => String(item.properties?.[key] || "").toLowerCase() === normalized));
        if (exactUnit) {
            const unit = exactUnit?.properties || result.units[0].properties;
            await selectBuilding(unit.building_id);
            await selectFloor(unit.floor_number);
            await setViewMode("UNIT");
            return selectUnit(unit.prototype_unit_uid);
        }
        if (exactFloor) {
            const floor = (exactFloor || result.floor_units[0]).properties;
            await selectBuilding(floor.building_id);
            return selectFloor(floor.floor_number);
        }
        if (exactBuilding || result.buildings?.length) return selectBuilding((exactBuilding || result.buildings[0]).properties.building_id);
        if (result.floor_units?.length) {
            const floor = result.floor_units[0].properties;
            await selectBuilding(floor.building_id);
            return selectFloor(floor.floor_number);
        }
        if (result.units?.length) {
            const unit = result.units[0].properties;
            await selectBuilding(unit.building_id);
            await selectFloor(unit.floor_number);
            await setViewMode("UNIT");
            return selectUnit(unit.prototype_unit_uid);
        }
        setStatus(`No result for ${query}`);
    } catch (error) {
        console.error(error);
        setStatus(`Search failed for ${query}`);
    }
}


async function start() {
    try {
        initMap();
        initThree();
        const result = await api("/api/profiles", false);
        profiles = result.profiles;
        currentProfile = result.default_profile || "hyderabad";
        currentProfileConfig = profiles.find(profile => profile.profile_id === currentProfile) || profiles[0];
        document.getElementById("search-btn").addEventListener("click", performSearch);
        document.getElementById("search-input").addEventListener("keydown", event => { if (event.key === "Enter") performSearch(); });
        document.getElementById("building-mode-btn").addEventListener("click", () => setViewMode("BUILDING"));
        document.getElementById("floor-mode-btn").addEventListener("click", () => setViewMode("FLOOR"));
        document.getElementById("unit-mode-btn").addEventListener("click", () => setViewMode("UNIT"));
        document.getElementById("survey-context-btn").addEventListener("click", showSurveyContext);
        document.getElementById("explode-btn").addEventListener("click", toggleExplode);
        document.getElementById("below-ground-btn").addEventListener("click", toggleBelowGround);
        document.getElementById("below-focus-btn").addEventListener("click", () => {
            if (!belowGroundEnabled) toggleBelowGround();
            focusBelowGround();
        });
        document.getElementById("isolate-btn").addEventListener("click", toggleIsolation);
        document.getElementById("ward-view-btn").addEventListener("click", focusWard3D);
        document.getElementById("three-zoom-in").addEventListener("click", () => zoomThree(0.78));
        document.getElementById("three-zoom-out").addEventListener("click", () => zoomThree(1.28));
        document.getElementById("toggle-map-panel").addEventListener("click", () => toggleSidePanel("left"));
        document.getElementById("toggle-dossier-panel").addEventListener("click", () => toggleSidePanel("right"));
        document.getElementById("reopen-map-panel").addEventListener("click", () => reopenSidePanel("left"));
        document.getElementById("reopen-dossier-panel").addEventListener("click", () => reopenSidePanel("right"));
        window.addEventListener("resize", () => {
            const container = document.getElementById("three-container");
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
            map.invalidateSize();
        });
        await switchProfile(currentProfile);
    } catch (error) {
        console.error(error);
        setStatus("Application error");
    }
}


start();
