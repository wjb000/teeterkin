"""Single source for both BOMs. Writes BOM.md (repo root) and returns a dict for the viewer side panel.
Prototype prices: retail, one robot's worth, checked 2026-11-14 on the linked pages (pack prices split per robot where noted).
Volume prices: engineering estimates for 10k units/yr (LCSC / Shenzhen module pricing and molding quotes from comparable
consumer products). They are not supplier quotes yet."""
import os

CHECKED = '2026-11-14'

PROTO = [
    # (item, qty, unit USD, source link, note)
    ('Seeed XIAO ESP32-S3 Sense (brain, camera, mic)', 1, 13.90, 'https://www.digikey.com/en/products/detail/seeed-technology-co-ltd/113991115/18724504', 'DigiKey, 1 pc ($19.99 at seeedstudio.com)'),
    ('N20 6 V metal gearmotor with hall encoder', 2, 14.95, 'https://abra-electronics.com/electromechanical/motors/gear-motors/mini-metal-gearmotors/ga12-n20-6v300-zh-jga12-n20-moteur-cc-a-engrenages-metalliques-a-detecteur-hall-6v-300-tr-min-avec-connecteur-jst-zh-a-6-broches.html', 'Abra, 300 rpm (50:1) listing; order the 100:1 option for the final ratio'),
    ('Waveshare 2.0" IPS LCD 240x320 ST7789', 1, 11.99, 'https://www.waveshare.com/product/2inch-lcd-module.htm', 'Waveshare direct'),
    ('SG90 micro servo', 1, 1.75, 'https://www.amazon.com/dp/B0DFL7QZRJ', '4-pack $6.99'),
    ('Adafruit MAX98357A I2S amp', 1, 5.95, 'https://www.adafruit.com/product/3006', 'Adafruit'),
    ('Pololu DRV8833 dual motor driver carrier', 1, 10.95, 'https://www.pololu.com/product/2130', 'Pololu'),
    ('MPU-6050 (GY-521) IMU board', 1, 4.33, 'https://www.amazon.com/EPLZON-MPU-6050-Accelerometer-Gyroscope-Converter/dp/B09TW19SS5', '3-pack $12.99'),
    ('VL53L0X ToF board (front + both cliff sensors on the proto)', 3, 3.00, 'https://www.amazon.com/SHUATI-VL53L0X-Distance-Breakout-Ranging/dp/B0CQ28Q3KC', '3-pack $8.99'),
    ('18650 cell 2600 mAh (Sony/Murata VTC5)', 2, 5.99, 'https://www.18650batterystore.com/collections/lithium-ion-batteries', '18650 Battery Store'),
    ('2S USB-C charge + protection board', 1, 7.99, 'https://www.amazon.com/Adeept-18650-Charge-Charging-Board/dp/B0BJTW4QBR', 'Adeept, Amazon'),
    ('5 V 2 A buck regulator (Pololu D24V22F5 class)', 1, 9.95, 'https://www.pololu.com/category/131/step-down-voltage-regulators', 'Pololu step-down family; price not re-checked'),
    ('Speaker 28 mm 8 ohm', 1, 1.95, 'https://www.adafruit.com/product/1890', 'Adafruit; price not re-checked'),
    ('Perfboard, JST leads, 10-wire ribbon, slide switch', 1, 6.00, '', 'shop stock, estimate'),
    ('Charge contacts (2 brass pads) + dock USB-C breakout + 2 pogo springs', 1, 4.00, '', 'estimate'),
    ('M2 screws, heat-set inserts', 1, 2.00, '', 'estimate'),
    ('PETG filament (~320 g incl. dock) + TPU (~40 g)', 1, 7.60, '', '$20/kg PETG, $30/kg TPU'),
]

VOLUME = [
    # (item, USD per robot at 10k/yr, basis)
    ('ESP32-S3 module (N8R8) on the head board', 3.20, 'LCSC ESP32-S3-WROOM-1 tier pricing'),
    ('OV3660 / OV2640 camera, 66 deg FPC', 2.40, 'Shenzhen module pricing'),
    ('PDM MEMS microphone', 0.35, 'LCSC'),
    ('2.0" IPS 240x320 bare panel (FPC)', 2.60, 'panel distributor pricing'),
    ('2x N20 100:1 + hall encoder', 4.80, '1688 / factory direct, $2.40 each'),
    ('Micro servo (SG90 class, custom lead length)', 0.90, 'factory direct'),
    ('2x 18650 2600 mAh (grade-A, tabbed pack)', 3.20, 'pack assembler pricing incl. welding'),
    ('Main board: 2-layer 44x70, DRV8833, ICM-42670-P, IP2326, buck, MAX98357A, USB-C, switch', 6.90, 'JLC/LCSC PCBA estimate'),
    ('Head board: ESP32-S3 + display/camera FFC connectors', 2.40, 'JLC/LCSC PCBA estimate (module above excluded)'),
    ('VL53L0X ToF + 2 IR cliff sensors', 1.40, 'LCSC'),
    ('Speaker 28 mm', 0.45, 'factory direct'),
    ('Injection-molded parts (shells, core, head, visor, 2 hubs) ', 4.60, 'material + cycle cost, tools amortised separately'),
    ('2x TPU tyres', 0.50, 'overmold / separate shot'),
    ('Wiring: 10-wire ribbon, motor leads, contacts, fasteners', 1.30, 'estimate'),
    ('Dock: molded puck, 2 spring contacts, USB-C board', 2.30, 'estimate'),
    ('Packaging + USB-C cable + quick-start card', 2.60, 'estimate'),
    ('Assembly + end-of-line test (12 min at $9/h)', 1.80, 'Shenzhen EMS labour rate'),
    ('Contingency: yield loss, scrap, price drift (8%)', 3.35, 'allowance'),
]
TOOLING = 'One-time: about $38k-55k for 8 steel/aluminium tools (shell front/rear, core, head, visor, hub, tyre, dock), FCC/CE/UN38.3 testing about $20k-30k.'


def totals():
    p = sum(q * u for _, q, u, _, _ in PROTO)
    v = sum(u for _, u, _ in VOLUME)
    return round(p, 2), round(v, 2)


def write(root):
    p, v = totals()
    L = ['# Teeterkin bill of materials', '',
         f'Two bills for the same design. **Prototype: ${p:.2f}** per robot (hobby retail, one robot, parts you can order today). '
         f'**Volume: ${v:.2f}** per robot (estimate at 10k units/yr).', '',
         f'Prototype prices were read on the linked pages on {CHECKED}; pack prices are split per robot (a 4-pack of servos counts as 1/4). '
         'Two lines are marked as not re-checked. Volume prices are engineering estimates, not supplier quotes.', '',
         '## Prototype (3D-printed, modules on perfboard)', '', '| Item | Qty | Unit | Line | Source |', '|---|---:|---:|---:|---|']
    for it, q, u, link, note in PROTO:
        src = f'[{note}]({link})' if link else note
        L.append(f'| {it} | {q} | ${u:.2f} | ${q * u:.2f} | {src} |')
    L += [f'| **Total** | | | **${p:.2f}** | |', '', '## Volume (injection molded, custom boards, 10k/yr)', '', '| Item | $/robot | Basis |', '|---|---:|---|']
    for it, u, basis in VOLUME:
        L.append(f'| {it} | ${u:.2f} | {basis} |')
    L += [f'| **Total landed BOM** | **${v:.2f}** | |', '', TOOLING, '',
          'Retail target $149-199: at $179 retail with 40% retailer margin the brand nets ~$107, leaving ~$50 per unit over the volume BOM for freight, returns, warranty, the app and margin.', '']
    open(os.path.join(root, 'BOM.md'), 'w').write('\n'.join(L))
    return dict(proto_total=p, volume_total=v, checked=CHECKED,
                proto=[dict(item=i, qty=q, unit=u, link=l) for i, q, u, l, _ in PROTO],
                volume=[dict(item=i, unit=u) for i, u, _ in VOLUME], tooling=TOOLING)
