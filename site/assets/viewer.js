import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {toCreasedNormals} from 'three/addons/utils/BufferGeometryUtils.js';

const BUILD = 'v1';
const $ = id => document.getElementById(id);
const el = $('viewer'), Q = new URLSearchParams(location.search);
const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(28, el.clientWidth / el.clientHeight, 5, 8000);
const r = new THREE.WebGLRenderer({antialias: true, alpha: true, preserveDrawingBuffer: true});
r.setPixelRatio(Math.min(devicePixelRatio, 2)); r.setSize(el.clientWidth, el.clientHeight);
r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.05; r.outputColorSpace = THREE.SRGBColorSpace;
el.prepend(r.domElement);
const pm = new THREE.PMREMGenerator(r); scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.6;
const ctl = new OrbitControls(cam, r.domElement); ctl.enableDamping = true; ctl.minDistance = 150; ctl.maxDistance = 2500;

// robot frame: x forward, y left, z up (mm)  ->  three: (x, z, -y)
const TGT = new THREE.Vector3(-20, 120, 0);
const VIEWS = {front: [900, 150, 0], '34': [600, 360, -600], side: [0, 170, -900], back: [-900, 180, 0], top: [1, 980, 0]};
function setView(n) {
  const v = VIEWS[n] || VIEWS['34']; cam.position.set(...v); ctl.target.copy(n === 'top' ? new THREE.Vector3(-40, 0, 0) : TGT); ctl.update();
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('on', b.dataset.view === n));
}

scene.add(new THREE.HemisphereLight(0xfff6ea, 0x9a8f80, 0.9));
const key = new THREE.DirectionalLight(0xffffff, 2.1); key.position.set(420, 780, -460); key.castShadow = true;
key.shadow.mapSize.set(2048, 2048); Object.assign(key.shadow.camera, {left: -340, right: 340, top: 340, bottom: -340, near: 100, far: 2400});
key.shadow.bias = -0.0004; key.shadow.normalBias = 1.0; scene.add(key);
const rim = new THREE.DirectionalLight(0xffe0bf, 1.1); rim.position.set(-600, 380, 300); scene.add(rim);
const floor = new THREE.Mesh(new THREE.CircleGeometry(1400, 96), new THREE.ShadowMaterial({opacity: 0.16}));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
const root = new THREE.Group(); root.rotation.x = -Math.PI / 2; scene.add(root);
const roll = new THREE.Group(); root.add(roll);           // fore/aft travel
const tilt = new THREE.Group(); roll.add(tilt);            // body pitch about the axle
const body = new THREE.Group(); tilt.add(body);

const GROUPS = {
  shell: {name: 'Shell, head & visor', color: '#e9e3d8'}, structure: {name: 'Core frame', color: '#2a2e35'},
  drivetrain: {name: 'Wheels & motors', color: '#ff6b35'}, power: {name: 'Power & charging', color: '#3b6fb6'},
  electronics: {name: 'Brain & boards', color: '#1f6f3f'}, sensors: {name: 'Sensors', color: '#6b2f9a'},
  motion: {name: 'Periscope lift', color: '#2b5fa8'}, expression: {name: 'Face & voice', color: '#ffb000'}, dock: {name: 'Charging dock', color: '#8b8f96'}
};
const items = {}, links = {}, labels = [];
const shellMats = [];
let RI, P, xray = Q.get('xray') === '1', showLabels = Q.get('labels') !== '0', explodeT = +(Q.get('explode') || 0), demo = Q.get('demo') === '1', peek = +(Q.get('peek') || 0), peekTarget = peek, sel = null;
const visible = Object.fromEntries(Object.keys(GROUPS).map(g => [g, true]));
(Q.get('hide') || '').split(',').filter(Boolean).forEach(g => visible[g] = false);

let blink = 0;
function drawFace(g, t) {
  const W = 320, H = 240; g.fillStyle = '#04060a'; g.fillRect(0, 0, W, H);
  const open = Math.max(0.08, 1 - Math.max(0, Math.sin(t * 1.0) > 0.985 ? 1 : 0));
  for (const cx of [100, 220]) {
    const look = demo ? Math.sin(t * 0.8) * 10 : 0;
    const grd = g.createRadialGradient(cx + look, 112, 4, cx + look, 112, 52);
    grd.addColorStop(0, '#fffbe8'); grd.addColorStop(0.45, '#ffd27a'); grd.addColorStop(1, '#ff6b35');
    g.fillStyle = grd; g.beginPath(); g.ellipse(cx + look, 112, 40, 46 * open, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = 'rgba(255,255,255,.85)'; g.beginPath(); g.ellipse(cx + look - 14, 94, 9, 7 * open, -0.4, 0, Math.PI * 2); g.fill();
  }
  g.strokeStyle = '#ffb46b'; g.lineWidth = 5; g.lineCap = 'round'; g.beginPath(); g.arc(160, 168, 18, 0.25 * Math.PI, 0.75 * Math.PI); g.stroke();
}
const faceCanvas = document.createElement('canvas'); faceCanvas.width = 320; faceCanvas.height = 240;
const faceTex = new THREE.CanvasTexture(faceCanvas); faceTex.colorSpace = THREE.SRGBColorSpace;

function makeMat(key, it) {
  const k = key.split(':')[1];
  const c = new THREE.Color(it.color);
  if (key.startsWith('part:')) {
    if (k === 'visor') { const m = new THREE.MeshPhysicalMaterial({color: 0x1b2430, roughness: 0.08, metalness: 0.0, clearcoat: 1, transmission: 0.35, thickness: 1.5, transparent: true, opacity: 0.38}); m.userData.glass = true; shellMats.push(m); return m; }
    if (k.startsWith('tyre')) return new THREE.MeshStandardMaterial({color: c, roughness: 0.85});
    if (k.startsWith('hub')) return new THREE.MeshPhysicalMaterial({color: c, roughness: 0.35, clearcoat: 0.5});
    if (k === 'core') return new THREE.MeshStandardMaterial({color: c, roughness: 0.7});
    if (k === 'dock') return new THREE.MeshPhysicalMaterial({color: c, roughness: 0.45, clearcoat: 0.3});
    const m = new THREE.MeshPhysicalMaterial({color: c, roughness: 0.3, clearcoat: 0.7, clearcoatRoughness: 0.2}); shellMats.push(m); return m;
  }
  if (k.startsWith('pogo') || k === 'touch') return new THREE.MeshStandardMaterial({color: c, metalness: 0.9, roughness: 0.3});
  if (k.startsWith('motor') || k === 'usbc') return new THREE.MeshStandardMaterial({color: c, metalness: 0.75, roughness: 0.35});
  return new THREE.MeshStandardMaterial({color: c, roughness: 0.5, metalness: 0.05});
}

Promise.all([
  fetch('assets/robot_info.json?v=' + BUILD).then(x => x.json()),
  new Promise((ok, bad) => new GLTFLoader().load('assets/teeterkin.gltf?v=' + BUILD, ok, undefined, bad))
]).then(([ri, gltf]) => {
  RI = ri; P = ri.params; const g = gltf.scene;
  tilt.position.set(0, 0, P.axle_z); body.position.set(0, 0, -P.axle_z); body.add(g);
  const fix = s => s.replace(/^(link|part|elec)(?!:)/, '$1:');
  const meshes = [];
  g.traverse(o => { const n = fix(o.name); if (n.startsWith('link:') && !o.isMesh) links[n.slice(5)] = o; if (o.isMesh) meshes.push(o); });
  for (const o of meshes) {
    let n = fix(o.name); if (!ri.items[n]) n = fix(o.parent.name);
    const it = ri.items[n]; if (!it) continue;
    o.geometry = toCreasedNormals(o.geometry.index ? o.geometry.toNonIndexed() : o.geometry, THREE.MathUtils.degToRad(35));
    o.material = makeMat(n, it); o.castShadow = !o.material.userData.glass; o.receiveShadow = true;
    const node = ri.items[fix(o.name)] ? o : o.parent;
    if (!items[n]) items[n] = Object.assign({key: n, nodes: [], p0: []}, it);
    if (!items[n].nodes.includes(node)) { items[n].nodes.push(node); items[n].p0.push(node.position.clone()); }
    o.userData.key = n;
  }
  if (links.dock) root.attach(links.dock);                 // the dock does not wobble with the robot
  for (const l of Object.values(links)) { l.userData.p0 = l.position.clone(); l.userData.q0 = l.quaternion.clone(); }
  // the face: animated eyes on the 2" panel, seen through the smoked visor
  if (links.head && items['elec:lcd']) {
    const d = P.disp;
    const face = new THREE.Mesh(new THREE.PlaneGeometry(42.6, 32), new THREE.MeshBasicMaterial({map: faceTex, toneMapped: false}));
    face.rotation.set(Math.PI / 2, Math.PI / 2, 0); face.position.set(d.x + 0.15, 0, d.z - P.head_z0);
    items['elec:lcd'].nodes[0].add(face); face.position.sub(items['elec:lcd'].nodes[0].position); face.userData.key = 'elec:lcd';
  }
  buildUI(); applyAll(); setView(Q.get('view') || '34');
  document.body.classList.add('loaded');
}).catch(e => { $('loading').textContent = 'Could not load the model: ' + e; console.error(e); });

const money = v => '$' + v.toFixed(2);
function buildUI() {
  const counts = {};
  for (const it of Object.values(items)) counts[it.group] = (counts[it.group] || 0) + 1;
  $('layers').innerHTML = Object.entries(GROUPS).map(([g, G]) =>
    `<label class="layer"><input type="checkbox" data-g="${g}" ${visible[g] ? 'checked' : ''}><span class="sw" style="background:${G.color}"></span>${G.name}<span class="n">${counts[g] || 0}</span></label>`).join('');
  $('layers').querySelectorAll('input').forEach(i => i.onchange = () => { visible[i.dataset.g] = i.checked; applyAll(); });
  const rows = {};
  for (const it of Object.values(items)) { const k = it.group + '|' + it.title; (rows[k] = rows[k] || {it, keys: [], n: 0}).keys.push(it.key); rows[k].n++; }
  let html = '', ncomp = 0;
  for (const g of Object.keys(GROUPS)) {
    const rs = Object.values(rows).filter(r => r.it.group === g); if (!rs.length) continue;
    html += `<div class="grp"><span class="sw" style="background:${GROUPS[g].color}"></span>${GROUPS[g].name}</div>`;
    for (const rw of rs) {
      ncomp++;
      const short = (rw.it.desc || '').split(/(?<=\.)\s/)[0];
      html += `<div class="c" data-keys="${rw.keys.join(',')}" data-g="${g}"><b>${rw.it.title}${rw.n > 1 ? ` &times;${rw.n}` : ''}</b><span>${short}</span></div>`;
    }
  }
  $('clist').innerHTML = html; $('ncomp').textContent = '(' + ncomp + ')';
  $('clist').querySelectorAll('.c').forEach(d => {
    d.onclick = () => select(d.dataset.keys.split(','));
    d.onmouseenter = () => highlight(d.dataset.keys.split(','), true); d.onmouseleave = () => highlight(d.dataset.keys.split(','), false);
  });
  const L = $('labels');
  for (const lb of RI.labels) {
    const it = items[lb.key]; if (!it) continue;
    const a = new THREE.Object3D(); a.position.fromArray(lb.local); (links[lb.node.slice(5)] || root).add(a);
    const d = document.createElement('div'); d.className = 'lbl'; d.innerHTML = `<i></i><span>${it.title}</span>`;
    d.onclick = () => select([lb.key]); L.appendChild(d);
    const ext = ['shell', 'dock', 'drivetrain'].includes(it.group) && !lb.key.startsWith('elec:motor') || ['elec:tof', 'elec:camera', 'elec:pogo_l'].includes(lb.key);
    labels.push({a, d, it, ext, key: lb.key});
  }
  const s = RI.summary, B = RI.bom;
  $('stats').innerHTML = `<div><b>${s.height_mm}&ndash;${s.height_up_mm} mm</b>tall (head down/up)</div><div><b>${(s.total_mass_g / 1000).toFixed(2)} kg</b>est. mass</div>` +
    `<div><b>${s.molded_tools} tools</b>${s.molded_pieces} molded pieces</div><div><b>${s.pendulum_tau_ms} ms</b>pendulum time const.</div>` +
    `<div><b>${money(B.volume_total)}</b>volume BOM</div><div><b>${money(B.proto_total)}</b>prototype BOM</div>`;
  document.querySelectorAll('.vtot').forEach(e => e.textContent = '$' + Math.round(B.volume_total));
  let bh = `<div class="tot"><div><b>${money(B.volume_total)}</b><span>volume BOM / robot (10k/yr estimate)</span></div><div><b>${money(B.proto_total)}</b><span>prototype BOM (retail, checked ${B.checked})</span></div></div>`;
  bh += `<h3>Volume (estimate)</h3><table class="bomt">${B.volume.map(v => `<tr><td>${v.item}</td><td>${money(v.unit)}</td></tr>`).join('')}</table>`;
  bh += `<p class="mute">${B.tooling}</p><h3>Prototype</h3><table class="bomt">${B.proto.map(v => `<tr><td>${v.link ? `<a href="${v.link}" target="_blank" rel="noopener">${v.item}</a>` : v.item}${v.qty > 1 ? ' &times;' + v.qty : ''}</td><td>${money(v.qty * v.unit)}</td></tr>`).join('')}</table>`;
  bh += `<p class="mute">Full table with sources: <a href="https://github.com/wjb000/teeterkin/blob/main/BOM.md">BOM.md</a></p>`;
  $('bom').innerHTML = bh;
  document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => {
    document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x === b));
    document.querySelectorAll('[data-pane]').forEach(p => p.hidden = p.dataset.pane !== b.dataset.tab);
  });
  if (Q.get('tab')) document.querySelector(`#tabs [data-tab="${Q.get('tab')}"]`)?.click();
}

function highlight(keys, on) {
  for (const k of keys) { const it = items[k]; if (!it) continue;
    for (const n of it.nodes) n.traverse(o => { if (o.isMesh && o.material.emissive && !o.material.userData.glass) { o.material.emissive.set(on ? 0xff5a1a : 0x000000); o.material.emissiveIntensity = on ? 0.45 : 1; } }); }
}
function select(keys) {
  if (sel) highlight(sel, false);
  sel = keys; highlight(keys, true);
  const it = items[keys[0]];
  $('info').classList.remove('hidden'); $('info-t').textContent = it.title + (keys.length > 1 ? ` (x${keys.length})` : '');
  $('info-k').textContent = (GROUPS[it.group] || {}).name + (it.kind === 'vendor' ? ' · maker CAD' : it.kind === 'molded' ? ' · molded part' : ' · modelled from datasheet') + (it.mass_g ? ` · ${it.mass_g} g` : '');
  $('info-d').textContent = it.desc + (it.material ? ' Material: ' + it.material + '.' : '');
  document.querySelectorAll('#clist .c').forEach(c => c.classList.toggle('sel', c.dataset.keys.split(',').includes(keys[0])));
  labels.forEach(l => l.d.classList.toggle('sel', keys.includes(l.key)));
}

function applyAll() {
  for (const it of Object.values(items)) {
    const vis = visible[it.group];
    it.nodes.forEach((n, i) => { n.visible = vis; n.position.copy(it.p0[i]).add(new THREE.Vector3(...it.explode).multiplyScalar(explodeT)); });
  }
  for (const m of shellMats) {
    const g = m.userData.glass; m.transparent = xray || g; m.opacity = xray ? (g ? 0.12 : 0.13) : (g ? 0.38 : 1); m.depthWrite = !xray && !g; m.needsUpdate = true;
  }
  $('xray').classList.toggle('on', xray); $('lbls').classList.toggle('on', showLabels); $('demo').classList.toggle('on', demo); $('peek').classList.toggle('on', peekTarget > 0.5);
  $('explode').value = explodeT;
  document.querySelectorAll('#clist .c').forEach(c => c.classList.toggle('off', !visible[c.dataset.g]));
}

document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => setView(b.dataset.view));
$('xray').onclick = () => { xray = !xray; applyAll(); };
$('lbls').onclick = () => { showLabels = !showLabels; applyAll(); };
$('demo').onclick = () => { demo = !demo; applyAll(); };
$('peek').onclick = () => { peekTarget = peekTarget > 0.5 ? 0 : 1; applyAll(); };
$('explode').oninput = e => { explodeT = +e.target.value; applyAll(); };

const ray = new THREE.Raycaster(), mp = new THREE.Vector2(); let down = null;
r.domElement.addEventListener('pointerdown', e => down = [e.clientX, e.clientY]);
r.domElement.addEventListener('pointerup', e => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
  const b = r.domElement.getBoundingClientRect(); mp.set((e.clientX - b.left) / b.width * 2 - 1, -(e.clientY - b.top) / b.height * 2 + 1);
  ray.setFromCamera(mp, cam);
  const hits = ray.intersectObject(root, true).filter(h => h.object.userData.key && isShown(h.object) && !((xray || h.object.material.userData.glass) && shellMats.includes(h.object.material)));
  if (hits.length) select([hits[0].object.userData.key]); else { if (sel) highlight(sel, false); sel = null; $('info').classList.add('hidden'); }
});
function isShown(o) { while (o) { if (!o.visible) return false; o = o.parent; } return true; }

// motion: periscope (servo crank -> yoke -> head lift) and the balancing wobble
const qx = new THREE.Quaternion(), qy = new THREE.Quaternion(), AXX = new THREE.Vector3(1, 0, 0), AXY = new THREE.Vector3(0, 1, 0);
let last = 0, wheelA = 0;
function animate(t) {
  const dt = Math.min(0.05, t - last); last = t;
  if (demo) peekTarget = (Math.sin(t * 0.9) > 0.2) ? 1 : 0;
  peek += (peekTarget - peek) * Math.min(1, dt * 6);
  const th = peek * Math.PI;                       // horn angle 0..180 deg
  if (links.horn) { qx.setFromAxisAngle(AXX, th); links.horn.quaternion.copy(links.horn.userData.q0).multiply(qx); }
  if (links.head) { links.head.position.copy(links.head.userData.p0); links.head.position.z += P.horn_r * (1 - Math.cos(th)); }
  let pitch = 0, x = 0;
  if (demo) { pitch = 0.07 * Math.sin(t * 2.1) + 0.03 * Math.sin(t * 5.3); x = 18 * Math.sin(t * 2.1 - 0.6); }
  tilt.rotation.y = pitch; roll.position.x = x;
  wheelA = x / P.wheel_r - pitch;
  for (const w of ['wheel_l', 'wheel_r']) if (links[w]) { qy.setFromAxisAngle(AXY, wheelA); links[w].quaternion.copy(links[w].userData.q0).multiply(qy); }
  drawFace(faceCanvas.getContext('2d'), t); faceTex.needsUpdate = true;
}
const v = new THREE.Vector3();
function placeLabels() {
  const w = el.clientWidth, h = el.clientHeight;
  for (const L of labels) {
    const vis = showLabels && visible[L.it.group] && (L.ext || xray || !visible.shell || explodeT > 0.35);
    if (!vis) { L.d.style.display = 'none'; continue; }
    L.a.getWorldPosition(v); v.project(cam);
    if (v.z > 1) { L.d.style.display = 'none'; continue; }
    L.d.style.display = ''; L.d.style.transform = `translate(${(v.x * .5 + .5) * w}px,${(-v.y * .5 + .5) * h}px)`;
  }
}
new ResizeObserver(() => { cam.aspect = el.clientWidth / el.clientHeight; cam.updateProjectionMatrix(); r.setSize(el.clientWidth, el.clientHeight); }).observe(el);
(function loop(t) { requestAnimationFrame(loop); if (RI) animate((t || 0) / 1000); ctl.update(); placeLabels(); r.render(scene, cam); })();
