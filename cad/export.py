#!/usr/bin/env python3
"""Build everything from cad/teeterkin.py + cad/components.py:
  cad/step/<part>.step, cad/step/teeterkin_assembly.step   molded parts + full assembly
  cad/stl/<part>.stl        prototype print files, already in print orientation (ASCII)
  cad/reports/*.json        interference check, mass / balance, part list
  site/assets/teeterkin.gltf + robot_info.json              viewer model and metadata
  BOM.md
Run: python cad/export.py      (cadquery 2.x, trimesh, manifold3d, fast_simplification)"""
import os, sys, json, math, time
import numpy as np, trimesh, cadquery as cq
import manifold3d as mf
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import teeterkin as T, components, bom
from textmesh import write_ascii_stl, glb_to_embedded_gltf

DENS = {'ABS': 1.05e-3, 'PC': 1.20e-3, 'PA6': 1.35e-3, 'TPU': 1.21e-3, 'PC/ABS': 1.25e-3}
STL_FACES = 5000
GLB_FACES = {'shell_front': 5200, 'shell_rear': 5200, 'head': 5000, 'core': 3800, 'visor': 1600, 'hub_l': 1100, 'hub_r': 1100,
             'tyre_l': 1500, 'tyre_r': 1500, 'dock': 1500}


def d(*p):
    q = os.path.join(ROOT, *p); os.makedirs(q, exist_ok=True); return q


def tess(shape, tol):
    v, f = shape.tessellate(tol, 0.3)
    m = trimesh.Trimesh(np.array([[p.x, p.y, p.z] for p in v]), np.array(f), process=True)
    m.merge_vertices(); trimesh.repair.fix_normals(m); return m


def wp_mesh(wp, tol=0.15):
    vs = wp.vals()
    return trimesh.util.concatenate([tess(s, tol) for s in vs]) if len(vs) > 1 else tess(vs[0], tol)


def decimate(m, n):
    if len(m.faces) <= n:
        return m
    try:
        return m.simplify_quadric_decimation(face_count=n)
    except Exception:
        return m


def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


def inter_vol(a, b):
    try:
        return (to_mf(a) ^ to_mf(b)).volume()
    except Exception:
        return float('nan')


def dens(mat):
    for k in ('PC/ABS', 'PA6', 'TPU', 'PC', 'ABS'):
        if mat.startswith(k) or mat.startswith('smoked ' + k):
            return DENS[k]
    return DENS['ABS']


def main():
    t0 = time.time()
    parts = []
    for P in T.PARTS:
        P = dict(P); P['solid'] = P['fn'](); P['mesh'] = wp_mesh(P['solid'], 0.12)
        P['vol'] = P['solid'].val().Volume(); parts.append(P)
        print(f"{P['name']}: {len(P['mesh'].faces)} faces, {P['vol'] / 1000:.1f} cm3")
    E = components.build()
    for e in E:
        e['mesh'] = wp_mesh(e['solid'], 0.25)
    print('built in', round(time.time() - t0), 's')

    # ---------------- STEP
    sd = d('cad', 'step')
    asm = cq.Assembly(name='teeterkin')
    for P in parts:
        cq.exporters.export(P['solid'], os.path.join(sd, P['name'] + '.step'))
        asm.add(P['solid'], name=P['name'], color=cq.Color(P['color']))
    for e in E:
        if e['kind'] != 'vendor':
            asm.add(e['solid'], name=e['key'], color=cq.Color(e['color']))
    asm.save(os.path.join(sd, 'teeterkin_assembly.step'))

    # ---------------- printable STL (print orientation, ASCII)
    ORIENT = {'shell_front': ((0, 1, 0), -90), 'shell_rear': ((0, 1, 0), 90), 'head': ((0, 1, 0), 90), 'visor': ((0, 1, 0), -90),
              'core': None, 'hub_l': ((1, 0, 0), -90), 'hub_r': ((1, 0, 0), 90), 'tyre_l': ((1, 0, 0), 90), 'tyre_r': ((1, 0, 0), 90), 'dock': None}
    stl = d('cad', 'stl'); prep = {}
    for P in parts:
        if P['name'] in ('hub_r', 'tyre_r'):
            continue                     # same tool / print as the left one
        m = decimate(P['mesh'].copy(), STL_FACES)
        o = ORIENT[P['name']]
        if o:
            m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(o[1]), o[0]))
        c = m.bounds.mean(0); m.apply_translation((-c[0], -c[1], -m.bounds[0][2]))
        nm = P['name'].replace('_l', '')
        write_ascii_stl(m, os.path.join(stl, nm + '.stl'), nm)
        prep[nm] = dict(qty=P['qty'], material=P['material'], bbox_mm=[round(float(x), 1) for x in m.extents], facets=len(m.faces))

    # ---------------- checks
    rep = d('cad', 'reports')
    clash = []
    every = [('part:' + P['name'], P['mesh'], P['solid']) for P in parts if P['name'] != 'dock'] + [('elec:' + e['key'], e['mesh'], e['solid']) for e in E]
    allowed = {('part:head', 'elec:flex'), ('elec:servo', 'elec:horn')}
    for i in range(len(every)):
        for j in range(i + 1, len(every)):
            a, b = every[i], every[j]
            if (a[0], b[0]) in allowed or (b[0], a[0]) in allowed:
                continue
            if not (np.all(a[1].bounds[0] < b[1].bounds[1]) and np.all(b[1].bounds[0] < a[1].bounds[1])):
                continue
            v = inter_vol(a[1], b[1])
            if v == v and v > 1.0:              # mesh says maybe: confirm on the exact B-rep
                try:
                    v = sum(x.Volume() for x in a[2].intersect(b[2]).vals())
                except Exception:
                    pass
                if v > 1.0:
                    clash.append(dict(a=a[0], b=b[0], mm3=round(v, 1)))
    head_m = next(P['mesh'] for P in parts if P['name'] == 'head')
    travel = []
    for frac in (0.25, 0.5, 0.75, 1.0):
        hm = head_m.copy(); hm.apply_translation((0, 0, T.LIFT * frac))
        for P in parts:
            if P['name'] in ('core', 'shell_front', 'shell_rear'):
                v = inter_vol(hm, P['mesh'])
                if v == v and v > 1.0:
                    travel.append(dict(lift_mm=round(T.LIFT * frac, 1), part=P['name'], mm3=round(v, 1)))
    json.dump(dict(static=clash, head_travel=travel), open(os.path.join(rep, 'interference.json'), 'w'), indent=1)
    print('interference:', clash, travel)

    mass, mom = 0.0, np.zeros(3)
    for P in parts:
        if P['name'] == 'dock':
            continue
        m = P['vol'] * dens(P['material']); c = P['mesh'].centroid
        P['mass'] = m; mass += m; mom += m * c
    for e in E:
        mass += e['mass']; mom += e['mass'] * e['mesh'].bounds.mean(0)
    com = mom / mass
    height = max(P['mesh'].bounds[1][2] for P in parts)
    summary = dict(height_mm=round(height), height_up_mm=round(height + T.LIFT), width_mm=round(T.TRACK + T.WHEEL_W),
                   depth_mm=round(2 * max(h[1] for h in T.HULL)), total_mass_g=round(mass), com_above_axle_mm=round(com[2] - T.AXLE_Z, 1),
                   com_x_mm=round(com[0], 1), molded_tools=8, molded_pieces=10, wheel_d_mm=2 * T.WHEEL_R, lift_mm=T.LIFT)
    summary['pendulum_tau_ms'] = round(1000 * math.sqrt((com[2] - T.AXLE_Z) / 1000 / 9.81))
    json.dump(dict(summary=summary, parts={P['name']: round(P.get('mass', 0), 1) for P in parts},
                   bought={e['key']: e['mass'] for e in E}, print=prep), open(os.path.join(rep, 'mass_properties.json'), 'w'), indent=1)
    print(summary)

    B = bom.write(ROOT)

    origin = {'base': np.zeros(3), 'dock': np.array([T.DOCK_SHOW[0], T.DOCK_SHOW[1], 0.0])}
    for jn, (p, c, o, a, lim) in T.JOINTS.items():
        origin[c] = np.array(o, float)
    sc = trimesh.Scene()
    sc.graph.update(frame_from=sc.graph.base_frame, frame_to='link:base', matrix=np.eye(4))
    Td = np.eye(4); Td[:3, 3] = origin['dock']
    sc.graph.update(frame_from=sc.graph.base_frame, frame_to='link:dock', matrix=Td)
    for jn, (p, c, o, a, lim) in T.JOINTS.items():
        M = np.eye(4); M[:3, 3] = origin[c] - origin[p]
        sc.graph.update(frame_from='link:' + p, frame_to='link:' + c, matrix=M)

    def put(name, mesh, link, faces):
        m = decimate(mesh.copy(), faces)
        m.apply_translation(-origin[link])
        m.vertices = np.round(m.vertices, 2)
        sc.add_geometry(m, node_name=name, geom_name=name, parent_node_name='link:' + link)

    TXT = {
        'shell_front': ('Body shell, front', 'Front half of the bean-shaped body: chest speaker grille, brow window for the range sensor, two cliff-sensor eyes. Splits from the rear half on one flat plane, so it is a simple straight-pull tool.'),
        'shell_rear': ('Body shell, rear + kickstand tail', 'Rear half with the upturned tail moulded in. To park, Teeterkin leans back onto the tail: motors off, zero power, and the charge pads in the tail land on the dock.'),
        'core': ('Core frame', 'The one structural part: motor saddles, battery cradle, spine for the main board, servo cradle and the mast sleeve. Every bought part mounts to it before the shells close.'),
        'head': ('Head + periscope mast', 'Head shell, hollow mast and scotch-yoke bar in a single moulding. The servo crank runs in the yoke slot and lifts the whole head 38 mm.'),
        'visor': ('Smoked visor (face)', 'Clear smoked polycarbonate. The display reads through it as glowing eyes; switched off it is a glossy black face.'),
        'hub_l': ('Wheel hub', 'Five-spoke hub in the accent colour, press-fit on the 3 mm D-shaft. Same tool both sides.'),
        'hub_r': ('Wheel hub', 'Five-spoke hub in the accent colour, press-fit on the 3 mm D-shaft. Same tool both sides.'),
        'tyre_l': ('Tyre', 'TPU 85A tyre with a fine chevron tread: grip on wood and tile, quiet on the floor.'),
        'tyre_r': ('Tyre', 'TPU 85A tyre with a fine chevron tread: grip on wood and tile, quiet on the floor.'),
        'dock': ('Charging dock', 'Low oval puck with a cup the tail drops into and two spring contacts. Teeterkin backs up, leans back, charges. USB-C in.'),
    }
    GRP = {'shell_front': 'shell', 'shell_rear': 'shell', 'head': 'shell', 'visor': 'shell', 'core': 'structure', 'hub_l': 'drivetrain', 'hub_r': 'drivetrain',
           'tyre_l': 'drivetrain', 'tyre_r': 'drivetrain', 'dock': 'dock'}
    EXP = {'shell_front': (75, 0, 0), 'shell_rear': (-75, 0, 0), 'core': (0, 0, 0), 'head': (0, 0, 95), 'visor': (55, 0, 95), 'hub_l': (0, 70, 0), 'hub_r': (0, -70, 0),
           'tyre_l': (0, 95, 0), 'tyre_r': (0, -95, 0), 'dock': (-40, 0, 0)}
    EEXP = {'motor_l': (0, 30, 0), 'motor_r': (0, -30, 0), 'cell_1': (-10, 0, 25), 'cell_2': (10, 0, 25), 'servo': (40, 0, 30), 'horn': (25, 0, 30), 'speaker': (45, 0, 0),
            'tof': (50, 0, 20), 'cliff_l': (35, 15, -10), 'cliff_r': (35, -15, -10), 'pcb': (-40, 0, 0), 'drv8833': (-40, 0, 0), 'imu': (-40, 0, 0), 'charger': (-40, 0, 0),
            'buck': (-40, 0, 0), 'amp': (-40, 0, 0), 'usbc': (-40, 0, 0), 'switch': (-40, 0, 0), 'pogo_l': (-50, 0, -10),
            'xiao': (25, 0, 95), 'camera': (45, 0, 95), 'mic': (25, 0, 95), 'lcd': (35, 0, 100), 'touch': (0, 0, 115), 'flex': (0, 0, 60)}
    LBL = {'shell_front': (33, -30, 100), 'shell_rear': (-34, 26, 95), 'core': (-22, -30, 140), 'head': (-20, 40, 205), 'visor': (28, -40, 190),
           'hub_l': (0, 67, 50), 'tyre_l': (25, 66, 12), 'dock': (-150, -45, 14)}
    items, labels = {}, []
    for P in parts:
        k = 'part:' + P['name']
        put(k, P['mesh'], P['link'], GLB_FACES[P['name']])
        t, s = TXT[P['name']]
        items[k] = dict(title=t, desc=s, group=GRP[P['name']], color=P['color'], explode=EXP[P['name']], kind='molded', material=P['material'],
                        mass_g=round(P.get('mass', 0), 1))
        if P['name'] in LBL:
            labels.append(dict(key=k, node='link:' + P['link'], local=(np.array(LBL[P['name']], float) - origin[P['link']]).tolist()))
    seen = set()
    for e in E:
        k = 'elec:' + e['key']
        put(k, e['mesh'], e['link'], 1400 if e['key'] == 'xiao' else 500)
        items[k] = dict(title=e['name'], desc=e['spec'], group=e['group'], color=e['color'], explode=EEXP.get(e['key'], (0, 0, 0)), kind=e['kind'], mass_g=e['mass'])
        if e['label'] and e['name'] not in seen:
            seen.add(e['name'])
            labels.append(dict(key=k, node='link:' + e['link'], local=(e['mesh'].bounds.mean(0) - origin[e['link']]).tolist()))
    out = d('site', 'assets')
    glb = os.path.join(out, 'teeterkin.glb'); sc.export(glb)
    glb_to_embedded_gltf(glb, os.path.join(out, 'teeterkin.gltf')); os.remove(glb)
    info = dict(summary=summary, bom=B,
                joints={jn: dict(node='link:' + c, origin=list(o), axis=list(a), limits=list(lim) if lim else None) for jn, (p, c, o, a, lim) in T.JOINTS.items()},
                params=dict(axle_z=T.AXLE_Z, wheel_r=T.WHEEL_R, horn_r=T.HORN_R, lift=T.LIFT, disp=T.DISP, head_z0=T.HEAD_Z0),
                items=items, labels=labels)
    json.dump(info, open(os.path.join(out, 'robot_info.json'), 'w'), indent=1)
    print('gltf', os.path.getsize(os.path.join(out, 'teeterkin.gltf')) // 1024, 'kB; total', round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
