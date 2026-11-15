"""Teeterkin: parametric CadQuery model of every molded / printed part.
Frame: x forward, y left, z up, millimetres, floor at z = 0, robot standing upright (balancing), head lowered.
Every part is built in assembly position; export.py re-orients copies for printing.
Change a number here and re-run `python cad/export.py`.

Molded parts (8 unique tools, 10 pieces, + dock):
  shell_front, shell_rear   two-piece body clamshell (split at x = 0), rear half carries the kickstand tail
  core                      one inner frame: motor saddles, battery cradle, spine for the main board, servo pocket, mast sleeve
  head                      head shell with the periscope mast and scotch-yoke bar moulded in one piece
  visor                     smoked clear face (PC), snaps onto the head
  hub (x2)                  wheel hub, same tool both sides
  tyre (x2)                 TPU tyre, same tool both sides
  dock                      charging pad the robot leans back onto
"""
import math
import cadquery as cq

# ---------------------------------------------------------------- key dimensions
WHEEL_R, WHEEL_W = 36.0, 14.0         # 72 mm wheel
AXLE_Z = WHEEL_R
TRACK = 118.0                         # wheel centre to wheel centre
WY = TRACK / 2
WALL = 2.2
# body hull: smooth loft through ellipses (z, half-depth in x, half-width in y)
HULL = [(10.0, 20.0, 24.0), (18.0, 29.0, 37.0), (34.0, 35.0, 46.0), (60.0, 36.5, 47.0), (95.0, 36.0, 46.5),
        (125.0, 33.0, 43.0), (146.0, 26.0, 35.0), (156.0, 17.0, 25.0)]
HULL_TOP = HULL[-1][0]
MOTOR_FACE_Y = 41.0                   # gearbox face (shaft side) of each N20
# periscope head
HEAD_X = (-29.0, 29.0)
HEAD_HY = 52.0                        # half width
HEAD_Z0 = HULL_TOP + 2.0              # head underside when lowered (2 mm gap to the body)
HEAD_H = 56.0
HEAD_FILLET = 17.0
VISOR_X = 13.0                        # visor / head split plane
MAST = dict(x0=-15.0, x1=-1.0, hy=11.0)   # mast tube cross-section (x range, half width in y)
SLEEVE_Z = (134.0, HULL_TOP)
SERVO_Z = 108.0                       # SG90 output shaft height (axis along x)
HORN_R = 19.0                         # scotch-yoke crank radius -> 38 mm lift
LIFT = 2 * HORN_R
YOKE_X = (-1.0, 2.0)
YOKE_Z = SERVO_Z - HORN_R             # pin height with the head lowered
MAST_BOTTOM = YOKE_Z - 5.0
# electronics positions
BATT_X = (-11.5, 8.5); BATT_Z = 62.0; BATT_R = 9.2; BATT_L = 65.0
PCB = dict(x=-28.5, hy=20.5, z0=38.0, z1=104.0)   # main board: rear face at x, 44 x 70 mm, parts on its front face
SPINE_X = (-24.0, -21.0)
DISP = dict(x=18.0, z=HEAD_Z0 + 33.0, w=58.0, h=35.0)       # 2.0" IPS module face plane / centre
CAM = dict(x=21.0, z=HEAD_Z0 + 10.5)
USB_Z = 41.0                          # USB-C (right-angle, on the main board's rear face)
TAIL_TIP = (-44.0, 0.0, 9.0)          # kickstand contact point; robot rests ~16 deg back on it
DOCK_SHOW = (-150.0, 0.0)             # viewer: dock drawn behind the robot


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), centered=False).translate((min(x0, x1), min(y0, y1), min(z0, z1)))


def cyl_y(x, z, r, y0, y1):
    return cq.Workplane('XZ').circle(r).extrude(-(y1 - y0)).translate((x, y0, z)) if y1 > y0 else cyl_y(x, z, r, y1, y0)


def cyl_x(y, z, r, x0, x1):
    return cq.Workplane('YZ').circle(r).extrude(x1 - x0).translate((x0, y, z))


def cyl_z(x, y, r, z0, z1):
    return cq.Workplane('XY').circle(r).extrude(z1 - z0).translate((x, y, z0))


def _loft(prof, d=0.0):
    w = cq.Workplane('XY').workplane(offset=prof[0][0] + d).ellipse(prof[0][1] - d, prof[0][2] - d)
    zp = prof[0][0] + d
    for i, (z, a, b) in enumerate(prof[1:]):
        zz = z - d if i == len(prof) - 2 else z
        w = w.workplane(offset=zz - zp).ellipse(a - d, b - d); zp = zz
    return w.loft(ruled=False, combine=True)


def hull_solid():
    return _loft(HULL)


def _hull_wall():
    outer = _loft(HULL)
    inner = _loft(HULL, WALL)
    s = outer.cut(inner)
    # top cap: mast opening
    s = s.cut(box(MAST['x0'] - 0.8, MAST['x1'] + 0.8, -MAST['hy'] - 0.8, MAST['hy'] + 0.8, HULL_TOP - 5, HULL_TOP + 1))
    # axle bosses / shaft holes on both sides
    for sy in (1, -1):
        s = s.cut(cyl_y(0, AXLE_Z, 4.0, -60, 60))
    return s


def _tail():
    """Kickstand tail: a tapered, upturned nub on the lower back. When Teeterkin parks it leans back onto it
    (motors off, zero power), and the two charge pads in its underside meet the dock."""
    path = cq.Workplane('XZ').moveTo(-22.0, 20.0).spline([(-34.0, 13.0), (TAIL_TIP[0], TAIL_TIP[2] + 4.0)], includeCurrent=True)
    prof = cq.Workplane('YZ', origin=(-22.0, 0, 20.0)).ellipse(13.0, 9.0)
    t = prof.sweep(path, transition='round')
    tip = cq.Workplane('XY').sphere(6.5).translate((TAIL_TIP[0], 0, TAIL_TIP[2] + 3.5))
    return t.union(tip)


def shell_front():
    s = _hull_wall().intersect(box(0, 60, -70, 70, 0, 200))
    # front sensor window (ToF), speaker grille, two cliff-sensor eyes
    s = s.cut(box(25, 45, -6.5, 6.5, 122.0, 130.0))
    for i in range(5):
        s = s.cut(box(25, 45, -12 + i * 6 - 1.2, -12 + i * 6 + 1.2, 66.0, 84.0))
    for sy in (1, -1):
        s = s.cut(cyl_x(sy * 17.0, 17.0, 2.6, 10, 40).rotate((10, sy * 17.0, 17.0), (0, 1, 0), 35))
    # snap bosses / screw pillars along the split line
    for (y, z) in ((28.0, 18.0), (-28.0, 18.0), (36.0, 128.0), (-36.0, 128.0)):
        s = s.union(cyl_x(y, z, 3.2, 0.0, 6.0).cut(cyl_x(y, z, 1.25, -1, 7)))
    return s


def shell_rear():
    s = _hull_wall().intersect(box(-60, 0, -70, 70, 0, 200))
    s = s.union(_tail().cut(_loft(HULL, WALL)))
    # USB-C port, power switch, charge pads in the tail underside
    s = s.cut(box(-45, -26, -4.8, 4.8, USB_Z - 1.9, USB_Z + 1.9))
    s = s.cut(box(-45, -26, 8.0, 16.0, USB_Z + 8.0, USB_Z + 11.0))
    for sy in (1, -1):
        s = s.cut(cyl_z(TAIL_TIP[0] + 4.0, sy * 3.6, 1.6, 0, 30))
    for (y, z) in ((28.0, 18.0), (-28.0, 18.0), (36.0, 128.0), (-36.0, 128.0)):
        s = s.union(cyl_x(y, z, 3.2, -6.0, 0.0).cut(cyl_x(y, z, 0.9, -7, 1)))
    return s


def core():
    """Single inner frame. Everything bolts or snaps to it; the shells only close around it."""
    c = box(-9.0, 9.0, -MOTOR_FACE_Y, MOTOR_FACE_Y, 27.0, 47.0)                      # motor saddle block
    c = c.cut(box(-6.2, 6.2, -MOTOR_FACE_Y - 1, -9.0, AXLE_Z - 5.2, AXLE_Z + 5.2))    # N20 pockets (left + right)
    c = c.cut(box(-6.2, 6.2, 9.0, MOTOR_FACE_Y + 1, AXLE_Z - 5.2, AXLE_Z + 5.2))
    c = c.cut(box(-6.8, 6.8, -MOTOR_FACE_Y + 22.5, MOTOR_FACE_Y - 22.5, AXLE_Z - 6.8, AXLE_Z + 6.8))  # encoder discs
    c = c.cut(box(-6.5, 6.5, -8.0, 8.0, 30.0, 50.0))                                 # wire pass
    c = c.union(box(-22.0, 20.0, -34.0, 34.0, 47.0, 50.0))                           # battery floor
    for bx in BATT_X:                                                                # cell saddles
        sad = box(bx - 8, bx + 8, -34.0, 34.0, 50.0, 55.0).cut(cyl_y(bx, BATT_Z, BATT_R + 0.3, -40, 40))
        c = c.union(sad)
    for sy in (1, -1):                                                               # cell end stops
        c = c.union(box(-22.0, 18.0, sy * 33.4, sy * 35.8, 47.0, 66.0))
    c = c.union(box(SPINE_X[0], SPINE_X[1], -36.0, 36.0, 27.0, 150.0))               # spine (main board on its back)
    for (y, z) in ((16.5, 42.0), (-16.5, 42.0), (16.5, 100.0), (-16.5, 100.0)):     # board standoffs
        c = c.union(cyl_x(y, z, 2.6, PCB['x'] + 1.6, SPINE_X[0]).cut(cyl_x(y, z, 0.9, PCB['x'], SPINE_X[0])))
    # mast sleeve, tied back to the spine
    sl = box(MAST['x0'] - 2.6, MAST['x1'] + 0.6, -MAST['hy'] - 2.6, MAST['hy'] + 2.6, SLEEVE_Z[0], SLEEVE_Z[1] - 3.0)
    sl = sl.cut(box(MAST['x0'] - 0.4, MAST['x1'] + 0.4, -MAST['hy'] - 0.4, MAST['hy'] + 0.4, SLEEVE_Z[0] - 1, SLEEVE_Z[1]))
    c = c.union(sl).union(box(SPINE_X[1], MAST['x0'] - 2.6, -6.0, 6.0, SLEEVE_Z[0], SLEEVE_Z[0] + 10.0))
    # servo cradle: two ears catch the SG90 flange, arm reaches back to the spine
    for zz in (SERVO_Z - 16.8 - 5.0, SERVO_Z + 6.0 + 0.0):
        c = c.union(box(8.0, 10.5, -9.0, 9.0, zz, zz + 5.0))
    c = c.union(box(SPINE_X[1], 10.5, 9.0, 12.0, SERVO_Z - 22.0, SERVO_Z + 11.0))
    c = c.union(box(SPINE_X[1], 10.5, -12.0, -9.0, SERVO_Z - 22.0, SERVO_Z + 11.0))
    c = c.cut(box(MAST['x0'] - 0.5, YOKE_X[1] + 0.8, -24.0, 24.0, MAST_BOTTOM - 1.0, SLEEVE_Z[0] - 0.01))   # yoke travel window
    return c.intersect(_loft(HULL, WALL + 0.4))                                       # trimmed to the inside of the shells


def head():
    """Head shell + mast + yoke bar in one moulding. The visor (front) is a separate clear part."""
    hz0, hz1 = HEAD_Z0, HEAD_Z0 + HEAD_H
    outer = box(HEAD_X[0], HEAD_X[1], -HEAD_HY, HEAD_HY, hz0, hz1).edges().fillet(HEAD_FILLET)
    inner = box(HEAD_X[0] + WALL, HEAD_X[1] - WALL, -HEAD_HY + WALL, HEAD_HY - WALL, hz0 + WALL, hz1 - WALL).edges().fillet(HEAD_FILLET - WALL)
    h = outer.cut(inner)
    # "ears": two soft touch domes on top (capacitive pads inside)
    for sy in (1, -1):
        e = cq.Workplane('XY').sphere(9.0).translate((-6.0, sy * 30.0, hz1 - 3.0)).intersect(box(-20, 10, sy * 30 - 10, sy * 30 + 10, hz1 - 2.0, hz1 + 10))
        h = h.union(e)
    h = h.cut(box(VISOR_X, 60, -60, 60, hz0 - 5, hz1 + 20))            # visor opening
    # visor lip (snap ledge)
    lip = box(VISOR_X - 2.5, VISOR_X, -HEAD_HY + 4, HEAD_HY - 4, hz0 + 4, hz1 - 4).cut(box(VISOR_X - 3, VISOR_X + 1, -HEAD_HY + 7, HEAD_HY - 7, hz0 + 7, hz1 - 7))
    h = h.union(lip.intersect(outer))
    # mast (hollow: the 10-wire flex runs inside) + yoke bar with its horizontal slot
    m = box(MAST['x0'], MAST['x1'], -MAST['hy'], MAST['hy'], MAST_BOTTOM, hz0 + WALL)
    m = m.cut(box(MAST['x0'] + 1.8, MAST['x1'] - 1.8, -MAST['hy'] + 1.8, MAST['hy'] - 1.8, MAST_BOTTOM - 1, hz0 + 3))
    y = box(YOKE_X[0] - 0.01, YOKE_X[1], -HORN_R - 4.5, HORN_R + 4.5, YOKE_Z - 5.0, YOKE_Z + 5.0)
    y = y.cut(box(YOKE_X[0] - 1, YOKE_X[1] + 1, -HORN_R - 1.8, HORN_R + 1.8, YOKE_Z - 1.7, YOKE_Z + 1.7))
    h = h.union(m).union(y)
    # display ribs (floor to roof) with four bosses for the 2.0" module
    for sy in (1, -1):
        h = h.union(box(9.0, 12.0, sy * 24.0, sy * 28.0, hz0 + 1.0, hz1 - 1.0).intersect(inner.union(outer)))
        for sz in (1, -1):
            h = h.union(cyl_x(sy * 26.0, DISP['z'] + sz * 14.5, 2.4, 9.0, DISP['x'] - 4.1).cut(cyl_x(sy * 26.0, DISP['z'] + sz * 14.5, 0.9, 8, DISP['x'])))
    return h


def visor():
    hz0, hz1 = HEAD_Z0, HEAD_Z0 + HEAD_H
    outer = box(HEAD_X[0], HEAD_X[1], -HEAD_HY, HEAD_HY, hz0, hz1).edges().fillet(HEAD_FILLET)
    inner = box(HEAD_X[0] + WALL, HEAD_X[1] - WALL, -HEAD_HY + WALL, HEAD_HY - WALL, hz0 + WALL, hz1 - WALL).edges().fillet(HEAD_FILLET - WALL)
    v = outer.cut(inner).intersect(box(VISOR_X, 60, -60, 60, hz0 - 5, hz1 + 5))
    return v


def hub(sy):
    """Built for the left wheel (outer face = +y), mirrored for the right. Spokes show on the outside."""
    w = cyl_y(0, AXLE_Z, WHEEL_R - 6.0, -WHEEL_W / 2 + 1.0, WHEEL_W / 2 - 1.0)
    w = w.cut(cyl_y(0, AXLE_Z, WHEEL_R - 9.0, -WHEEL_W / 2 + 3.0, WHEEL_W / 2))      # dish, open to the outside
    w = w.union(cyl_y(0, AXLE_Z, 6.0, -WHEEL_W / 2 - 5.0, WHEEL_W / 2 - 1.0))       # boss reaching toward the body
    for i in range(5):                                                              # 5 spokes
        a = i * 72.0 + 18.0
        sp = box(4.0, WHEEL_R - 8.0, -WHEEL_W / 2 + 3.0, WHEEL_W / 2 - 2.0, -2.2, 2.2).translate((0, 0, AXLE_Z)).rotate((0, 0, AXLE_Z), (0, 1, AXLE_Z), a)
        w = w.union(sp)
    w = w.cut(cyl_y(0, AXLE_Z, 1.55, -20, 20))                                      # 3 mm D-bore (flat moulded in)
    if sy < 0:
        w = w.mirror('XZ')
    return w.translate((0, sy * WY, 0))


def tyre(sy):
    o = cyl_y(0, AXLE_Z, WHEEL_R, -WHEEL_W / 2, WHEEL_W / 2).edges().fillet(3.0)
    t = o.cut(cyl_y(0, AXLE_Z, WHEEL_R - 6.0, -20, 20))
    # tread: shallow chevrons
    for i in range(24):
        a = i * 15.0
        g = box(WHEEL_R - 1.0, WHEEL_R + 1, -WHEEL_W / 2 + 2.5, WHEEL_W / 2 - 2.5, -1.0, 1.0).translate((0, 0, AXLE_Z)).rotate((0, 0, AXLE_Z), (0, 1, AXLE_Z), a)
        t = t.cut(g)
    return t.translate((0, sy * WY, 0))


def dock():
    """Charging pad: a low oval disc with a shallow cup where the tail lands, two spring pads, USB-C in."""
    x, y = DOCK_SHOW
    d = cq.Workplane('XY').ellipse(70.0, 55.0).extrude(9.0).edges('>Z').fillet(4.0)
    d = d.cut(cq.Workplane('XY').sphere(16.0).translate((0, 0, 20.5)))           # tail cup
    d = d.union(cq.Workplane('XY').ellipse(14.0, 30.0).extrude(16.0).translate((-52, 0, 0)).edges('>Z').fillet(5.0))   # backstop
    for sy in (1, -1):
        d = d.cut(cyl_z(0, sy * 3.6, 1.8, 3.0, 12.0))
    d = d.cut(box(-75, -60, -4.6, 4.6, 3.0, 6.6))
    return d.translate((x, y, 0))


PARTS = [
    dict(name='shell_front', fn=shell_front, link='base', material='ABS (proto: PETG)', color='#f2ede4', qty=1),
    dict(name='shell_rear', fn=shell_rear, link='base', material='ABS (proto: PETG)', color='#f2ede4', qty=1),
    dict(name='core', fn=core, link='base', material='PC/ABS 20% GF (proto: PETG)', color='#2a2e35', qty=1),
    dict(name='head', fn=head, link='head', material='ABS (proto: PETG)', color='#f2ede4', qty=1),
    dict(name='visor', fn=visor, link='head', material='smoked PC (proto: clear PETG, sanded)', color='#1b2430', qty=1),
    dict(name='hub_l', fn=lambda: hub(1), link='wheel_l', material='PA6 GF (proto: PETG)', color='#ff6b35', qty=2),
    dict(name='hub_r', fn=lambda: hub(-1), link='wheel_r', material='PA6 GF (proto: PETG)', color='#ff6b35', qty=0),
    dict(name='tyre_l', fn=lambda: tyre(1), link='wheel_l', material='TPU 85A', color='#22252b', qty=2),
    dict(name='tyre_r', fn=lambda: tyre(-1), link='wheel_r', material='TPU 85A', color='#22252b', qty=0),
    dict(name='dock', fn=dock, link='dock', material='ABS (proto: PETG)', color='#e6e0d6', qty=1),
]

# joints: name -> (parent, child, origin xyz, axis, limits)
JOINTS = {
    'wheel_l': ('base', 'wheel_l', (0.0, WY, AXLE_Z), (0, 1, 0), None),
    'wheel_r': ('base', 'wheel_r', (0.0, -WY, AXLE_Z), (0, 1, 0), None),
    'head_lift': ('base', 'head', (0.0, 0.0, HEAD_Z0), (0, 0, 1), (0.0, LIFT)),
    'servo_horn': ('base', 'horn', (YOKE_X[1] + 0.5, 0.0, SERVO_Z), (1, 0, 0), (0.0, 180.0)),
}
