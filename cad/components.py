"""Bought parts placed in the assembly, as CadQuery solids, so the same geometry feeds the assembly STEP,
the interference check, the mass estimate and the website viewer.
kind = 'vendor' (maker CAD, fetched by fetch_vendor.py) or 'modelled' (from datasheet dimensions)."""
import os
import cadquery as cq
from teeterkin import *

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, 'vendor')


def n20(sy):
    """N20 micro gearmotor + 7-PPR magnetic hall encoder, 12 x 10 mm, shaft out toward the wheel."""
    g = box(-6, 6, 0, 9.0, -5, 5)
    m = box(-6, 6, 9.0, 24.0, -5, 5).edges('|Y').fillet(2.0)
    e = box(-6.5, 6.5, 24.0, 25.2, -6.5, 6.5).union(cyl_y(0, 0, 4.0, 25.2, 28.0))
    sh = cyl_y(0, 0, 1.5, -11.0, 0)
    s = g.union(m).union(e).union(sh)
    s = s.translate((0, -MOTOR_FACE_Y, AXLE_Z)) if sy < 0 else s.mirror('XZ').translate((0, MOTOR_FACE_Y, AXLE_Z))
    return s


def sg90():
    """SG90 micro servo lying on its back: output shaft points -x at (x=2.5..6, z=SERVO_Z)."""
    b = box(6.0, 28.7, -6.1, 6.1, SERVO_Z - 16.8, SERVO_Z + 6.0)
    f = box(10.5, 13.0, -6.1, 6.1, SERVO_Z - 21.4, SERVO_Z + 10.6)
    top = cyl_x(0, SERVO_Z, 5.9, 3.5, 6.0).union(cyl_x(0, SERVO_Z - 5.5, 2.8, 3.5, 6.0))
    sh = cyl_x(0, SERVO_Z, 2.4, 2.4, 3.6)
    return b.union(f).union(top).union(sh)


def horn():
    """Single-arm horn (ships with the servo) with an M2 pin: the crank of the scotch yoke. Built pointing down (head lowered)."""
    x0 = YOKE_X[1] + 0.5
    hubc = cyl_x(0, SERVO_Z, 3.6, x0, x0 + 3.2)
    arm = box(x0, x0 + 1.6, -2.6, 2.6, SERVO_Z - HORN_R, SERVO_Z)
    tipc = cyl_x(0, SERVO_Z - HORN_R, 2.6, x0, x0 + 1.6)
    pin = cyl_x(0, SERVO_Z - HORN_R, 1.5, YOKE_X[0] + 0.3, x0)
    return hubc.union(arm).union(tipc).union(pin)


def xiao():
    p = os.path.join(VENDOR, 'xiao_esp32s3.step')
    if os.path.exists(p):
        s = cq.importers.importStep(p)
        s = s.rotate((0, 0, 0), (0, 0, 1), -90)          # board normal -> +x, USB-C -> -y
        bb = s.val().BoundingBox()
        return s.translate((8.0 - bb.xmin, -bb.center.y, CAM['z'] + 3.0 - bb.center.z)), 'vendor'
    return box(8.0, 9.6, -10.5, 10.5, CAM['z'] - 7.4, CAM['z'] + 10.4), 'modelled'


def build():
    E = []

    def add(key, name, solid, mass, link, kind, spec, bom, label=True, color='#555b66', group=None):
        E.append(dict(key=key, name=name, solid=solid, mass=mass, link=link, kind=kind, spec=spec, bom=bom, label=label, color=color, group=group))

    # ---------------- drivetrain
    for sy, s in ((1, 'l'), (-1, 'r')):
        add(f'motor_{s}', 'N20 gearmotor 100:1 + hall encoder', n20(sy), 10.5, 'base', 'modelled',
            'Metal-gear N20, 100:1, 3 mm D-shaft, 7-PPR magnetic encoder (700 counts per wheel turn). Run from the 2S pack with a PWM ceiling: about 0.7 m/s top speed on 72 mm wheels.',
            'motor', label=(sy > 0), color='#b9bec6', group='drivetrain')
    # ---------------- power
    for i, bx in enumerate(BATT_X):
        add(f'cell_{i + 1}', '18650 Li-ion cell 2600 mAh', cyl_y(bx, BATT_Z, BATT_R, -BATT_L / 2, BATT_L / 2), 46.0, 'base', 'modelled',
            'Two cells in series (2S, 7.4 V, 19 Wh). Lying across the body just above the axle: their weight sets the pendulum that the balance loop rides on. About 3 h of active play, 20 h idle (estimate).',
            'cell', label=(i == 0), color='#3b6fb6', group='power')
    # ---------------- main board (all chips on one 44 x 70 mm 2-layer board; prototype: modules on perfboard)
    px = PCB['x']
    add('pcb', 'Main board', box(px, px + 1.6, -PCB['hy'], PCB['hy'], PCB['z0'], PCB['z1']), 9.0, 'base', 'modelled',
        'One 44 x 70 mm board on the back of the spine: motor driver, IMU, 2S charger + protection, 5 V buck, audio amp, USB-C. The brain lives in the head.',
        'pcb', color='#1f6f3f', group='electronics')
    fx = px + 1.6
    chips = [('drv8833', 'DRV8833 dual H-bridge', (-10, 52, 5.0, 6.4, 1.2), 'Drives both N20s at 25 kHz PWM, 1.2 A per channel; balance loop runs at 500 Hz.', 'drv'),
             ('imu', 'ICM-42670-P 6-axis IMU', (0, 62, 3.0, 3.0, 1.0), 'Gyro + accelerometer for the balance loop. Board sits on the body centreline, 26 mm above the axle.', 'imu'),
             ('charger', '2S USB-C charger + protection', (10, 52, 5.0, 5.0, 1.0), 'IP2326-class boost charger (5 V USB-C in, 8.4 V out) plus 2S protection with balancing.', 'charger'),
             ('buck', '5 V 2 A buck regulator', (10, 80, 6.0, 6.0, 2.6), 'Pack to 5 V for the servo, the amp and the head. 3.3 V is made on the XIAO.', 'buck'),
             ('amp', 'MAX98357A I2S amplifier', (-10, 80, 3.0, 3.0, 1.0), 'Class-D mono, 3 W, drives the chest speaker for chirps, purrs and speech.', 'amp')]
    for key, nm, (y, z, w, h, t), spec, bom in chips:
        add(key, nm, box(fx, fx + t, y - w / 2, y + w / 2, z - h / 2, z + h / 2), 0.3, 'base', 'modelled', spec, bom, color='#15181c', group='electronics')
    add('usbc', 'USB-C port', box(px - 3.3, px, -4.5, 4.5, USB_Z - 1.6, USB_Z + 1.6), 1.0, 'base', 'modelled',
        'Right-angle receptacle on the back of the board. Charging (when not on the dock) and firmware.', 'usbc', color='#c9ccd1', group='power')
    add('switch', 'Power switch', box(px - 3.0, px, 9.0, 15.0, USB_Z + 8.2, USB_Z + 10.8), 0.5, 'base', 'modelled', 'Slide switch: hard power cut for shipping and storage.', 'switch', color='#30343a', group='power')
    add('pogo_l', 'Charge contacts in the tail', cyl_z(TAIL_TIP[0] + 4.0, 3.6, 1.5, 6.6, 13.0).union(cyl_z(TAIL_TIP[0] + 4.0, -3.6, 1.5, 6.6, 13.0)), 0.6, 'base', 'modelled',
        'Two gold-plated pads flush in the underside of the tail. Parking on the dock = leaning back onto them: no alignment mechanism needed.', 'pogo', color='#d4a24a', group='power')
    # ---------------- sensors
    add('tof', 'VL53L0X time-of-flight sensor', box(26.0, 27.6, -6.6, 6.6, 120.8, 131.2).union(box(27.6, 28.8, -3.0, 3.0, 124.0, 128.0)), 0.5, 'base', 'modelled',
        'Forward laser ranging to 2 m behind the brow window: obstacles, "someone is in front of me", following distance.', 'tof', color='#23262c', group='sensors')
    for sy, s in ((1, 'l'), (-1, 'r')):
        cl = box(16.5, 19.0, sy * 17.0 - 3.0, sy * 17.0 + 3.0, 15.0, 21.0).rotate((17.0, sy * 17.0, 18.0), (0, 1, 0), 35)
        add(f'cliff_{s}', 'Cliff sensor', cl, 0.3, 'base', 'modelled',
            'IR reflective sensor (ITR8307 class) looking down and ahead of each wheel: stops at stairs and table edges.', 'cliff', label=(sy > 0), color='#6b2f9a', group='sensors')
    # ---------------- motion + expression (body)
    add('servo', 'SG90 micro servo (periscope lift)', sg90(), 9.0, 'base', 'modelled',
        'The only actuator besides the wheels. Through the scotch yoke it pops the head up 38 mm in 0.25 s: peek, duck, nod, bounce.', 'servo', color='#2b5fa8', group='motion')
    add('horn', 'Servo horn + yoke pin', horn(), 0.8, 'horn', 'modelled', 'Ships with the servo; an M2 shoulder screw is the crank pin running in the head yoke slot.', 'servo', label=False, color='#f2f2f2', group='motion')
    add('speaker', 'Speaker 28 mm', cyl_x(0, 75.0, 14.0, 27.5, 31.5).union(cyl_x(0, 75.0, 6.0, 25.0, 27.5)), 5.0, 'base', 'modelled',
        '8 ohm 1 W, firing through the chest grille.', 'speaker', color='#3a3d44', group='expression')
    # ---------------- head
    xs, kind = xiao()
    add('xiao', 'XIAO ESP32-S3 Sense (brain)', xs, 5.0, 'head', kind,
        'Dual-core ESP32-S3, 8 MB PSRAM, Wi-Fi + BLE. Runs the balance loop, behaviours, face animation, wake word and the camera stream; heavier AI is offloaded to the phone app.',
        'xiao', color='#2c2c2c', group='electronics')
    cam = box(19.0, 21.5, -4.25, 4.25, CAM['z'] - 4.25, CAM['z'] + 4.25).union(cyl_x(0, CAM['z'], 3.4, 21.5, 23.4))
    add('camera', 'Camera (OV3660 on the XIAO Sense)', cam, 1.0, 'head', 'modelled',
        '3 MP camera looking out through the smoked visor below the face. With the head raised it sees over sofa arms and table tops.', 'xiao', color='#101114', group='sensors')
    add('mic', 'PDM microphone (on the XIAO Sense)', box(12.2, 13.2, 6.0, 9.0, CAM['z'] + 6.0, CAM['z'] + 8.0), 0.1, 'head', 'modelled',
        'Wake word ("hey kin") and sound events like a doorbell, a dog bark or glass breaking.', 'xiao', label=False, color='#9a9a9a', group='sensors')
    dz, dxp = DISP['z'], DISP['x']
    lcd = box(dxp - 4.1, dxp - 2.5, -29.0, 29.0, dz - 17.5, dz + 17.5).union(box(dxp - 2.5, dxp, -22.0, 22.0, dz - 16.0, dz + 16.0))
    add('lcd', '2.0" IPS display 320 x 240 (the face)', lcd, 12.0, 'head', 'modelled',
        'ST7789 SPI panel behind the smoked visor: two big animated eyes and a mouth line. Off = the visor looks black and glossy.', 'lcd', color='#0b0d10', group='expression')
    add('touch', 'Touch pads (ears)', cyl_z(-6.0, 28.0, 5.0, HEAD_Z0 + HEAD_H - 3.2, HEAD_Z0 + HEAD_H - 2.8).union(cyl_z(-6.0, -28.0, 5.0, HEAD_Z0 + HEAD_H - 3.2, HEAD_Z0 + HEAD_H - 2.8)), 0.4, 'head', 'modelled',
        'Copper pads under the two ear domes, read by the ESP32-S3 touch pins: pat its head, it purrs.', 'touch', color='#d4a24a', group='sensors')
    add('flex', 'Head cable (10-wire)', box(-9.0, -8.2, -4.0, 4.0, MAST_BOTTOM + 2.0, HEAD_Z0 + 2.0), 1.0, 'head', 'modelled',
        '10-way ribbon down the hollow mast: 5 V, ground, I2C (IMU), I2S (amp), motor PWM, encoder, servo. Service loop below the mast.', 'flex', label=False, color='#c9a227', group='electronics')
    return E
