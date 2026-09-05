/* ==========================================================================
   3D ULPIN HYDERABAD — UNIFIED DASHBOARD APPLICATION LOGIC
   ========================================================================== */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// --------------------------------------------------------------------------
// Global Application State
// --------------------------------------------------------------------------
const state = {
    buildingsClean: null,
    heroBuildings: null,
    heroParcels: null,
    heroFloors: null,

    selectedBuildingId: 'B0595', // Default starting hero building
    selectedFloorId: null,
    
    // GIS Reference Center Point (Financial District / Nanakramguda)
    centerLat: 17.42007,
    centerLon: 78.35068,

    // Three.js instances
    scene: null,
    camera: null,
    renderer: null,
    controls: null,
    gridHelper: null,
    floorMeshes: [],
    floorGroup: null,
    parcelGroup: null,
    raycaster: new THREE.Raycaster(),
    mouse: new THREE.Vector2(),

    // Mapbox instance
    map2d: null,
    usingFallbackMap: false
};

// Hero Building Color Theme Map
const HERO_COLORS = {
    B0595: 0x38a8ff, // Office Tower (Blue)
    B0612: 0x7bde8c, // Apartments (Green)
    B0162: 0xffbd59  // Residential (Amber)
};

const HERO_COLORS_HEX = {
    B0595: '#38a8ff',
    B0612: '#7bde8c',
    B0162: '#ffbd59'
};

// --------------------------------------------------------------------------
// Initialization Entry Point
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    console.log("Initializing 3D ULPIN Dashboard Application...");

    await loadDatasets();
    init3DViewer();
    setupUIEventListeners();
    init2DMap();
    
    // Explicitly select initial hero building B0595
    selectBuilding('B0595');
});

// --------------------------------------------------------------------------
// 1. Data Ingestion (Fetch Local GeoJSON Files)
// --------------------------------------------------------------------------
async function loadDatasets() {
    try {
        const [resClean, resHeroes, resParcels, resFloors] = await Promise.all([
            fetch('../data/buildings_clean.geojson'),
            fetch('../data/hero_buildings.geojson'),
            fetch('../data/hero_parcels.geojson'),
            fetch('../data/hero_floor_ulpins.geojson')
        ]);

        state.buildingsClean = await resClean.json();
        state.heroBuildings = await resHeroes.json();
        state.heroParcels = await resParcels.json();
        state.heroFloors = await resFloors.json();

        console.log("Loaded GeoJSON Datasets:", {
            cleanCount: state.buildingsClean.features.length,
            heroCount: state.heroBuildings.features.length,
            parcelCount: state.heroParcels.features.length,
            floorCount: state.heroFloors.features.length
        });

        // Update UI Header Counters
        document.getElementById('counter-osm-buildings').innerText = state.buildingsClean.features.length;
        document.getElementById('counter-hero-buildings').innerText = state.heroBuildings.features.length;
        document.getElementById('counter-floor-units').innerText = state.heroFloors.features.length;

    } catch (err) {
        console.error("Failed to load local GeoJSON datasets:", err);
    }
}

// --------------------------------------------------------------------------
// 2. 2D Map Integration (Mapbox GL JS + Safe Canvas Fallback)
// --------------------------------------------------------------------------
function init2DMap() {
    const token = window.APP_CONFIG?.MAPBOX_TOKEN;
    const banner = document.getElementById('map-banner');

    const isValidToken = token && token.startsWith('pk.') && token !== 'YOUR_MAPBOX_PUBLIC_TOKEN';

    if (!isValidToken) {
        console.warn("Mapbox Public Token not configured or placeholder detected.");
        banner.style.display = 'block';
        banner.className = 'map-overlay-banner info-notice';
        banner.innerHTML = `
            <strong>ℹ️ Mapbox Token Setup Required:</strong><br>
            Copy <code>dashboard/config.example.js</code> to <code>dashboard/config.js</code> and set your Mapbox token to enable Mapbox satellite/vector maps.<br>
            <em>Interactive fallback canvas preview active below.</em>
        `;
        initFallback2DMap();
        return;
    }

    try {
        mapboxgl.accessToken = token;
        state.map2d = new mapboxgl.Map({
            container: 'map2d',
            style: 'mapbox://styles/mapbox/dark-v11',
            center: [state.centerLon, state.centerLat],
            zoom: 16,
            pitch: 0
        });

        state.map2d.addControl(new mapboxgl.NavigationControl(), 'top-left');

        state.map2d.on('load', () => {
            console.log("Mapbox GL JS 2D Map loaded successfully.");
            
            // Add All 635 OSM Context Buildings Source
            state.map2d.addSource('buildings-clean', {
                type: 'geojson',
                data: state.buildingsClean
            });

            // Add BhuNaksha Cadastral Parcels Source
            state.map2d.addSource('hero-parcels', {
                type: 'geojson',
                data: state.heroParcels
            });

            // Add Hero Buildings Source
            state.map2d.addSource('hero-buildings', {
                type: 'geojson',
                data: state.heroBuildings
            });

            // Layer 1: Context Buildings Fill (Dark Muted)
            state.map2d.addLayer({
                id: 'buildings-clean-fill',
                type: 'fill',
                source: 'buildings-clean',
                paint: {
                    'fill-color': '#1e293b',
                    'fill-opacity': 0.6
                }
            });

            // Layer 2: Context Buildings Outline
            state.map2d.addLayer({
                id: 'buildings-clean-line',
                type: 'line',
                source: 'buildings-clean',
                paint: {
                    'line-color': '#334155',
                    'line-width': 1
                }
            });

            // Layer 3: Cadastral Parcels Fill & Line (Yellow)
            state.map2d.addLayer({
                id: 'hero-parcels-fill',
                type: 'fill',
                source: 'hero-parcels',
                paint: {
                    'fill-color': '#ffd700',
                    'fill-opacity': 0.15
                }
            });

            state.map2d.addLayer({
                id: 'hero-parcels-line',
                type: 'line',
                source: 'hero-parcels',
                paint: {
                    'line-color': '#ffd700',
                    'line-width': 2,
                    'line-dasharray': [2, 1]
                }
            });

            // Layer 4: Hero Buildings Highlight Fill
            state.map2d.addLayer({
                id: 'hero-buildings-fill',
                type: 'fill',
                source: 'hero-buildings',
                paint: {
                    'fill-color': [
                        'match',
                        ['get', 'building_id'],
                        'B0595', HERO_COLORS_HEX.B0595,
                        'B0612', HERO_COLORS_HEX.B0612,
                        'B0162', HERO_COLORS_HEX.B0162,
                        '#38a8ff'
                    ],
                    'fill-opacity': 0.85
                }
            });

            state.map2d.addLayer({
                id: 'hero-buildings-line',
                type: 'line',
                source: 'hero-buildings',
                paint: {
                    'line-color': '#ffffff',
                    'line-width': 2
                }
            });

            // Map Click Event Handling
            state.map2d.on('click', (e) => {
                // Check if Hero building clicked
                const heroFeatures = state.map2d.queryRenderedFeatures(e.point, { layers: ['hero-buildings-fill'] });
                if (heroFeatures.length > 0) {
                    const bId = heroFeatures[0].properties.building_id;
                    selectBuilding(bId);
                    return;
                }

                // Check if general OSM building clicked
                const cleanFeatures = state.map2d.queryRenderedFeatures(e.point, { layers: ['buildings-clean-fill'] });
                if (cleanFeatures.length > 0) {
                    const props = cleanFeatures[0].properties;
                    selectNonHeroBuilding(props);
                }
            });

            // Change cursor on hover over buildings
            state.map2d.on('mouseenter', 'hero-buildings-fill', () => { state.map2d.getCanvas().style.cursor = 'pointer'; });
            state.map2d.on('mouseleave', 'hero-buildings-fill', () => { state.map2d.getCanvas().style.cursor = ''; });
            state.map2d.on('mouseenter', 'buildings-clean-fill', () => { state.map2d.getCanvas().style.cursor = 'pointer'; });
            state.map2d.on('mouseleave', 'buildings-clean-fill', () => { state.map2d.getCanvas().style.cursor = ''; });
        });

    } catch (err) {
        console.error("Mapbox GL JS initialization failed:", err);
        initFallback2DMap();
    }
}

// Interactive Fallback 2D Map Canvas (Runs if no Mapbox API Token)
function initFallback2DMap() {
    state.usingFallbackMap = true;
    const container = document.getElementById('map2d');
    container.innerHTML = `<canvas id="fallback-canvas" style="width:100%; height:100%; display:block; cursor:crosshair;"></canvas>`;
    const canvas = document.getElementById('fallback-canvas');
    const ctx = canvas.getContext('2d');

    function resize() {
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        render();
    }

    // Convert WGS84 Lat/Lon to Canvas Pixel X/Y
    function latLonToPixel(lon, lat) {
        const dLon = (lon - state.centerLon) * 125000;
        const dLat = (lat - state.centerLat) * 125000;
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        return [cx + dLon, cy - dLat];
    }

    function drawPolygon(geom, fillColor, strokeColor, lineWidth = 1) {
        if (!geom) return;
        const coordsList = geom.type === 'MultiPolygon' ? geom.coordinates : [geom.coordinates];

        ctx.beginPath();
        for (const poly of coordsList) {
            const exterior = poly[0];
            exterior.forEach((pt, idx) => {
                const [px, py] = latLonToPixel(pt[0], pt[1]);
                if (idx === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            });
        }
        ctx.closePath();

        if (fillColor) {
            ctx.fillStyle = fillColor;
            ctx.fill();
        }
        if (strokeColor) {
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = lineWidth;
            ctx.stroke();
        }
    }

    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Background
        ctx.fillStyle = '#091321';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw Grid
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 1;
        const step = 40;
        for (let x = 0; x < canvas.width; x += step) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
        }
        for (let y = 0; y < canvas.height; y += step) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }

        // Draw 635 Context OSM Buildings
        if (state.buildingsClean) {
            state.buildingsClean.features.forEach(f => {
                drawPolygon(f.geometry, 'rgba(30, 41, 59, 0.7)', '#334155', 0.8);
            });
        }

        // Draw BhuNaksha Parcels
        if (state.heroParcels) {
            state.heroParcels.features.forEach(f => {
                drawPolygon(f.geometry, 'rgba(255, 215, 0, 0.12)', '#ffd700', 2);
            });
        }

        // Draw Hero Buildings
        if (state.heroBuildings) {
            state.heroBuildings.features.forEach(f => {
                const bId = f.properties.building_id;
                const isSelected = (bId === state.selectedBuildingId);
                const color = HERO_COLORS_HEX[bId] || '#38a8ff';
                drawPolygon(
                    f.geometry, 
                    isSelected ? color : color + 'aa', 
                    isSelected ? '#ffffff' : color, 
                    isSelected ? 3 : 1.5
                );
            });
        }
    }

    // Raycast click check for fallback canvas
    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // 1. Check if Hero Building clicked
        if (state.heroBuildings) {
            for (const f of state.heroBuildings.features) {
                if (pointInFeature(mouseX, mouseY, f.geometry, latLonToPixel)) {
                    selectBuilding(f.properties.building_id);
                    render();
                    return;
                }
            }
        }

        // 2. Check if general OSM building clicked (Exclude hero buildings to prevent accidental override)
        if (state.buildingsClean) {
            for (const f of state.buildingsClean.features) {
                const bId = f.properties.building_id;
                if (['B0595', 'B0612', 'B0162'].includes(bId)) {
                    continue; // Skip hero buildings here
                }
                if (pointInFeature(mouseX, mouseY, f.geometry, latLonToPixel)) {
                    selectNonHeroBuilding(f.properties);
                    render();
                    return;
                }
            }
        }
    });

    window.addEventListener('resize', resize);
    resize();
}

// Point in polygon helper for fallback canvas
function pointInFeature(px, py, geometry, transformFn) {
    if (!geometry) return false;
    const coordsList = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
    for (const poly of coordsList) {
        const exterior = poly[0];
        let inside = false;
        for (let i = 0, j = exterior.length - 1; i < exterior.length; j = i++) {
            const [xi, yi] = transformFn(exterior[i][0], exterior[i][1]);
            const [xj, yj] = transformFn(exterior[j][0], exterior[j][1]);
            const intersect = ((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        if (inside) return true;
    }
    return false;
}

// --------------------------------------------------------------------------
// 3. Center Panel - Three.js 3D Viewer Engine
// --------------------------------------------------------------------------
function init3DViewer() {
    const container = document.getElementById('viewer3d');
    
    // Scene
    state.scene = new THREE.Scene();
    state.scene.background = new THREE.Color(0x07111f);

    // Camera
    state.camera = new THREE.PerspectiveCamera(
        45, 
        container.clientWidth / container.clientHeight, 
        0.1, 
        3000
    );
    state.camera.position.set(120, 100, 150);

    // Renderer
    state.renderer = new THREE.WebGLRenderer({ antialias: true });
    state.renderer.setSize(container.clientWidth, container.clientHeight);
    state.renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(state.renderer.domElement);

    // Controls
    state.controls = new OrbitControls(state.camera, state.renderer.domElement);
    state.controls.enableDamping = true;
    state.controls.dampingFactor = 0.05;

    // Dual Lights for clear 360-degree 3D illumination
    state.scene.add(new THREE.AmbientLight(0xffffff, 1.2));
    
    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.8);
    dirLight1.position.set(200, 400, 200);
    state.scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x90b0ff, 0.8);
    dirLight2.position.set(-200, 200, -200);
    state.scene.add(dirLight2);

    // Ground Grid Helper
    state.gridHelper = new THREE.GridHelper(600, 40, 0x334155, 0x1e293b);
    state.scene.add(state.gridHelper);

    // Groups
    state.floorGroup = new THREE.Group();
    state.parcelGroup = new THREE.Group();
    state.scene.add(state.parcelGroup);
    state.scene.add(state.floorGroup);

    // Click Detection (Raycaster)
    state.renderer.domElement.addEventListener('click', on3DViewerClick);

    // Window Resize Handler
    window.addEventListener('resize', () => {
        state.camera.aspect = container.clientWidth / container.clientHeight;
        state.camera.updateProjectionMatrix();
        state.renderer.setSize(container.clientWidth, container.clientHeight);
    });

    // Render Animation Loop
    function animate() {
        requestAnimationFrame(animate);
        state.controls.update();
        state.renderer.render(state.scene, state.camera);
    }
    animate();

    console.log("Three.js 3D Viewer Initialized.");
}

// Convert WGS84 (Lon, Lat) to Local Metric Plane (X, Z) in meters
function latLonToMetricLocal(lon, lat) {
    const latRad = state.centerLat * Math.PI / 180;
    const x = (lon - state.centerLon) * Math.PI / 180 * 6378137 * Math.cos(latRad);
    const z = -(lat - state.centerLat) * Math.PI / 180 * 6378137;
    return [x, z];
}

// Render 3D Floor Volumes for Selected Hero Building
function render3DFloors(buildingId) {
    if (!state.heroFloors || !state.heroParcels) return;

    // Clear existing meshes
    while (state.floorGroup.children.length > 0) {
        const obj = state.floorGroup.children.pop();
        if (obj.geometry) obj.geometry.dispose();
    }
    while (state.parcelGroup.children.length > 0) {
        const obj = state.parcelGroup.children.pop();
        if (obj.geometry) obj.geometry.dispose();
    }
    state.floorMeshes = [];

    // 1. Draw Cadastral Parcel Outlines for this building
    const matchingParcels = state.heroParcels.features.filter(f => f.properties.building_id === buildingId);
    matchingParcels.forEach(parcelFeature => {
        const coordsList = parcelFeature.geometry.type === 'MultiPolygon' ? parcelFeature.geometry.coordinates : [parcelFeature.geometry.coordinates];
        coordsList.forEach(poly => {
            const points = poly[0].map(pt => {
                const [mx, mz] = latLonToMetricLocal(pt[0], pt[1]);
                return new THREE.Vector3(mx, 0.2, mz);
            });
            const geom = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineBasicMaterial({ color: 0xffd700, linewidth: 2 });
            state.parcelGroup.add(new THREE.Line(geom, mat));
        });
    });

    // 2. Extrude 3D Floor Volumes
    const matchingFloors = state.heroFloors.features.filter(f => f.properties.building_id === buildingId);
    const colorHex = HERO_COLORS[buildingId] || 0x38a8ff;

    matchingFloors.forEach(floorFeature => {
        const props = floorFeature.properties;
        const coords = floorFeature.geometry.coordinates[0]; // Polygon exterior ring

        const shape = new THREE.Shape();
        coords.forEach((pt, idx) => {
            const [mx, mz] = latLonToMetricLocal(pt[0], pt[1]);
            if (idx === 0) shape.moveTo(mx, -mz);
            else shape.lineTo(mx, -mz);
        });

        const extrudeSettings = {
            depth: props.floor_height_m,
            bevelEnabled: false
        };

        const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
        geometry.rotateX(-Math.PI / 2); // Flip extrusion Z to world Y

        const material = new THREE.MeshStandardMaterial({
            color: colorHex,
            transparent: true,
            opacity: 0.85,
            roughness: 0.3,
            metalness: 0.2,
            side: THREE.DoubleSide // Ensure double-sided 3D volume rendering
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.y = props.z_min_m;
        mesh.userData = props;

        // Wireframe edges for visible floor boundaries
        const edgeGeometry = new THREE.EdgesGeometry(geometry);
        const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x07111f });
        const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial);
        edges.position.y = props.z_min_m;

        state.floorGroup.add(mesh);
        state.floorGroup.add(edges);
        state.floorMeshes.push(mesh);
    });

    console.log(`Rendered 3D Building ${buildingId}: ${state.floorMeshes.length} floor meshes added.`);

    // Camera Focus on extruded building
    focusBuildingCamera();
}

// Adjust camera target to fit the active building & ground grid
function focusBuildingCamera() {
    if (state.floorMeshes.length === 0) return;

    state.floorGroup.updateMatrixWorld(true);

    const box = new THREE.Box3();
    state.floorMeshes.forEach(mesh => {
        if (mesh.geometry) mesh.geometry.computeBoundingBox();
        box.expandByObject(mesh);
    });

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);

    const distance = Math.max(maxDim * 1.8, 45);

    state.camera.position.set(
        center.x + distance * 0.8,
        center.y + distance * 0.7,
        center.z + distance * 0.8
    );
    state.controls.target.copy(center);
    state.controls.update();

    // Align ground grid Helper beneath active building
    if (state.gridHelper) {
        state.gridHelper.position.set(center.x, 0, center.z);
    }
}

// Handle Raycaster Click on 3D Floors
function on3DViewerClick(event) {
    const container = document.getElementById('viewer3d');
    const rect = container.getBoundingClientRect();

    state.mouse.x = ((event.clientX - rect.left) / container.clientWidth) * 2 - 1;
    state.mouse.y = -((event.clientY - rect.top) / container.clientHeight) * 2 + 1;

    state.raycaster.setFromCamera(state.mouse, state.camera);
    const intersects = state.raycaster.intersectObjects(state.floorMeshes, false);

    if (intersects.length > 0) {
        const clickedMesh = intersects[0].object;
        const floorProps = clickedMesh.userData;
        
        // Highlight clicked floor
        state.selectedFloorId = floorProps.floor_id;
        state.floorMeshes.forEach(m => {
            if (m.userData.floor_id === floorProps.floor_id) {
                m.material.emissive.setHex(0xffffff);
                m.material.emissiveIntensity = 0.35;
            } else {
                m.material.emissive.setHex(0x000000);
            }
        });

        // Update Dossier with Floor Unit details
        renderFloorDossier(floorProps);
    }
}

// --------------------------------------------------------------------------
// 4. Selection Logic & Right Panel Dossier Renderer
// --------------------------------------------------------------------------

// Select one of the 3 Hero Buildings
function selectBuilding(buildingId) {
    console.log(`Selecting Hero Building: ${buildingId}`);
    state.selectedBuildingId = buildingId;
    state.selectedFloorId = null;

    // Update UI Selector Buttons
    document.querySelectorAll('.btn-building').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.id === buildingId);
    });

    // Update Badge
    const badge = document.getElementById('active-building-badge');
    badge.innerText = `Building: ${buildingId}`;
    badge.style.borderColor = HERO_COLORS_HEX[buildingId];

    // Render 3D Scene
    render3DFloors(buildingId);

    // Update 2D Map Selection (if Mapbox)
    if (state.map2d && !state.usingFallbackMap) {
        const heroFeat = state.heroBuildings.features.find(f => f.properties.building_id === buildingId);
        if (heroFeat) {
            const centroid = heroFeat.geometry.coordinates[0][0]; // approximate coords
            state.map2d.flyTo({ center: centroid, zoom: 17, duration: 1000 });
        }
    }

    // Render Building Level Dossier
    renderBuildingDossier(buildingId);
}

// Select a non-hero OSM building
function selectNonHeroBuilding(props) {
    const bId = props.building_id || 'OSM Building';
    console.log(`Selected Non-Hero Building: ${bId}`);

    // DO NOT clear or wipe the 3D hero building model in the center panel!
    // Display context notice in the right dossier panel while preserving active 3D model.

    const badge = document.getElementById('active-building-badge');
    badge.innerText = `Building: ${state.selectedBuildingId} | Selected Context: ${bId}`;

    // Render Unsupported Dossier Notice
    renderNonHeroDossier(props);
}

// Render Dossier for Hero Building Overview
function renderBuildingDossier(buildingId) {
    const container = document.getElementById('dossier-container');
    const heroFeat = state.heroBuildings?.features.find(f => f.properties.building_id === buildingId);
    const parcelFeat = state.heroParcels?.features.find(f => f.properties.building_id === buildingId);
    const floorsList = state.heroFloors?.features.filter(f => f.properties.building_id === buildingId) || [];
    
    const sampleFloor = floorsList[0]?.properties || {};
    const pProps = parcelFeat?.properties || {};

    const isEstimated = sampleFloor.is_floor_estimated;
    const confidence = sampleFloor.vertical_confidence || 'medium';

    const html = `
        <div class="dossier-card">
            <div class="dossier-card-title">
                <span>🏢 Building Overview</span>
                <span class="confidence-pill confidence-${confidence}">${confidence} confidence</span>
            </div>
            <div class="dossier-grid">
                <div class="dossier-field">
                    <span class="field-label">Building ID</span>
                    <span class="field-value">${buildingId}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Official Parcel No.</span>
                    <span class="field-value">${pProps.official_parcel_no || 'Parcel ' + pProps.parcel_id}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Village</span>
                    <span class="field-value">${pProps.V_Name || pProps.village || 'Nanakramguda'}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Mandal / District</span>
                    <span class="field-value">${pProps.M_Name || 'Serilingampally'} / ${pProps.D_Name || 'Ranga Reddy'}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Building Height</span>
                    <span class="field-value">${sampleFloor.building_height_m || 'N/A'} m</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Total Floor Count</span>
                    <span class="field-value">${sampleFloor.building_floor_count || floorsList.length} floors ${isEstimated ? '(Estimated)' : ''}</span>
                </div>
            </div>
        </div>

        <div class="dossier-card">
            <div class="dossier-card-title">
                <span>🛰️ Data Sources & Verification</span>
            </div>
            <div class="dossier-grid">
                <div class="dossier-field full-width">
                    <span class="field-label">Cadastral Source</span>
                    <span class="field-value">Telangana TGRAC BhuNaksha Cadastral</span>
                </div>
                <div class="dossier-field full-width">
                    <span class="field-label">Height Source</span>
                    <span class="field-value">${sampleFloor.height_source || 'Google Open Buildings 2.5D (2023)'}</span>
                </div>
                <div class="dossier-field full-width">
                    <span class="field-label">Floor Source</span>
                    <span class="field-value">${sampleFloor.floor_source || 'Derived'}</span>
                </div>
            </div>
        </div>

        <div class="dossier-card">
            <div class="dossier-card-title">
                <span>🥞 Vertical Floor Units (${floorsList.length})</span>
            </div>
            <div class="floor-list-preview">
                ${floorsList.map(f => `
                    <div class="floor-chip" data-floorid="${f.properties.floor_id}">
                        F${f.properties.floor_number}
                    </div>
                `).join('')}
            </div>
            <p style="font-size:10px; color:var(--text-muted); margin-top:4px;">Click floor chip above or 3D volume in center panel to view full 3D ULPIN.</p>
        </div>

        <div class="legal-disclaimer-box">
            <strong>⚠️ Legal Domain Notice:</strong><br>
            Prototype 3D ULPINs are spatial research identifiers and <u>NOT</u> officially issued government land titles. Topology flags represent 3D geometric overlaps, not legal ownership disputes.
        </div>
    `;

    container.innerHTML = html;

    // Attach click listeners to floor chips
    container.querySelectorAll('.floor-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const fId = chip.dataset.floorid;
            const floorFeat = floorsList.find(f => f.properties.floor_id === fId);
            if (floorFeat) {
                // Highlight floor in 3D
                on3DViewerClickDirect(fId);
                renderFloorDossier(floorFeat.properties);
            }
        });
    });
}

// Programmatic 3D Floor Selection from Chip
function on3DViewerClickDirect(floorId) {
    state.selectedFloorId = floorId;
    state.floorMeshes.forEach(m => {
        if (m.userData.floor_id === floorId) {
            m.material.emissive.setHex(0xffffff);
            m.material.emissiveIntensity = 0.35;
        } else {
            m.material.emissive.setHex(0x000000);
        }
    });
}

// Render Dossier for Specific 3D Floor Unit
function renderFloorDossier(props) {
    const container = document.getElementById('dossier-container');
    const isEstimated = props.is_floor_estimated;
    const confidence = props.vertical_confidence || 'medium';

    const html = `
        <div class="dossier-card" style="border-color: var(--accent-b0595);">
            <div class="dossier-card-title">
                <span>🔑 Floor Unit Dossier — F${props.floor_number}</span>
                <button id="btn-back-building" class="btn-action" style="padding:2px 8px; font-size:10px;">← Building</button>
            </div>
            
            <div class="dossier-field full-width">
                <span class="field-label">Prototype 3D ULPIN</span>
                <span class="field-value highlight-ulpin">${props.prototype_3d_ulpin || 'P3D-GEN-PENDING'}</span>
            </div>

            <div class="dossier-grid" style="margin-top:6px;">
                <div class="dossier-field">
                    <span class="field-label">Floor ID</span>
                    <span class="field-value">${props.floor_id}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Floor Number</span>
                    <span class="field-value">Floor ${props.floor_number}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Vertical Range ($Z$)</span>
                    <span class="field-value">${props.z_min_m?.toFixed(2)}m – ${props.z_max_m?.toFixed(2)}m</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Floor Height ($\Delta z$)</span>
                    <span class="field-value">${props.floor_height_m?.toFixed(2)} m</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Footprint Area</span>
                    <span class="field-value">${props.footprint_area_m2?.toFixed(1)} m²</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Volumetric Capacity</span>
                    <span class="field-value">${props.volume_m3?.toFixed(1)} m³</span>
                </div>
            </div>
        </div>

        <div class="dossier-card">
            <div class="dossier-card-title">
                <span>📊 Stratum Metadata</span>
                <span class="confidence-pill confidence-${confidence}">${confidence} confidence</span>
            </div>
            <div class="dossier-grid">
                <div class="dossier-field">
                    <span class="field-label">ULPIN Type</span>
                    <span class="field-value">${props.ulpin_type || 'PROTOTYPE_3D_VERTICAL_ID'}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Floor Estimated</span>
                    <span class="field-value">${isEstimated ? 'YES (Satellite derived)' : 'NO (OSM tagged)'}</span>
                </div>
                <div class="dossier-field full-width">
                    <span class="field-label">Height Source</span>
                    <span class="field-value">${props.height_source}</span>
                </div>
                <div class="dossier-field full-width">
                    <span class="field-label">Floor Source</span>
                    <span class="field-value">${props.floor_source}</span>
                </div>
            </div>
        </div>

        <div class="legal-disclaimer-box">
            <strong>⚠️ Prototype 3D ULPIN Notice:</strong><br>
            Not an officially issued government ULPIN. Demonstrates deterministic spatial hashing using SHA-256 canonical string indexing.
        </div>
    `;

    container.innerHTML = html;

    document.getElementById('btn-back-building').addEventListener('click', () => {
        renderBuildingDossier(props.building_id);
    });
}

// Render Dossier for Non-Hero Building
function renderNonHeroDossier(props) {
    const container = document.getElementById('dossier-container');
    const bId = props.building_id || 'OSM Footprint';
    const area = props.area_m2 ? `${props.area_m2} m²` : 'N/A';

    const html = `
        <div class="dossier-card">
            <div class="dossier-card-title">
                <span>🏢 Context OSM Building</span>
                <span class="source-badge badge-osm">OSM Footprint</span>
            </div>
            <div class="dossier-grid">
                <div class="dossier-field">
                    <span class="field-label">Building ID</span>
                    <span class="field-value">${bId}</span>
                </div>
                <div class="dossier-field">
                    <span class="field-label">Footprint Area</span>
                    <span class="field-value">${area}</span>
                </div>
            </div>
        </div>

        <div class="unsupported-notice-box">
            <strong>ℹ️ Model Status:</strong><br>
            Detailed vertical model not yet generated for this building.<br><br>
            <span style="font-size:11px; color:var(--text-secondary);">
                Full 3D floor volume strata and BhuNaksha cadastral parcel mappings are currently generated for Hero Buildings <strong>B0595</strong>, <strong>B0612</strong>, and <strong>B0162</strong>.
            </span>
        </div>
    `;

    container.innerHTML = html;
}

// --------------------------------------------------------------------------
// 5. UI Event Listeners
// --------------------------------------------------------------------------
function setupUIEventListeners() {
    // Hero Building Selector Buttons
    document.querySelectorAll('.btn-building').forEach(btn => {
        btn.addEventListener('click', () => {
            selectBuilding(btn.dataset.id);
        });
    });

    // Reset Camera Button
    document.getElementById('btn-reset-camera').addEventListener('click', () => {
        focusBuildingCamera();
    });

    // View All / Focus Building Button
    document.getElementById('btn-view-all').addEventListener('click', () => {
        focusBuildingCamera();
    });
}
