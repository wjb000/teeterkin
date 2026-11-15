# Teeterkin: production notes

## Part list (molded)
| Part | Qty | Material (volume) | Prototype | Tool notes |
|---|---:|---|---|---|
| shell_front | 1 | ABS, gloss white | PETG, print on split face | straight pull; grille slots and ToF window in the core side |
| shell_rear (with tail) | 1 | ABS, gloss white | PETG, print on split face | one small slide for the USB-C / switch window |
| core | 1 | PC/ABS 20% GF, dark grey | PETG, upright, supports under the sleeve | ribbed frame; all bought parts mount here |
| head (with mast + yoke) | 1 | ABS, gloss white | PETG, print on its face opening | mast core pin from below; yoke slot by shut-off |
| visor | 1 | PC, smoked 40% | clear PETG, sanded + tinted film | polished A-side, gate on the hidden lip |
| hub | 2 | PA6 GF, orange | PETG | same tool left/right, D-bore moulded |
| tyre | 2 | TPU 85A, charcoal | TPU 85A | same tool left/right (or overmold on the hub later) |
| dock | 1 | ABS | PETG | |

8 tools, 10 molded pieces per robot (+ dock). Estimated tooling $38k-55k (P20 steel for shells/head/core, aluminium for hub/tyre/dock/visor at launch volume).

## Rules used in the CAD
- Nominal wall 2.2 mm everywhere on the shells and head; core ribs 2.5-3 mm.
- Every shell splits on a single flat plane (x = 0 for the body, x = 13 mm for the head/visor), so all pull directions are straight.
- Draft: 1 deg on all pull faces still to be added in the tooling pass (the parametric model has none yet).
- Screw bosses: 4 x M2 self-tapping across the body split, 4 x M2 for the main board, 4 x M2 for the display.
- Clearances checked by `cad/export.py`: zero static interference between any two parts, and zero interference over the full 38 mm head travel (`cad/reports/interference.json`).

## Assembly (target 12 minutes, no soldering at the line)
1. Core: press the two N20 motors into the saddles (encoders face inward), clip both 18650 cells (pre-welded 2S pack with leads) into the cradle.
2. Screw the main board to the back of the spine (4 x M2). Plug motors, battery, speaker, ToF, cliff sensors, servo, tail contacts.
3. Drop the SG90 into its cradle, fit the horn at the 0 deg mark with the M2 pin screw.
4. Head: screw the display to the four bosses, stick the XIAO head board behind the camera window, plug the ribbon, snap the visor on.
5. Slide the mast down the core sleeve so the horn pin enters the yoke slot. Route the ribbon's service loop.
6. Close front + rear shells around the core (4 x M2 + snaps). Press hubs onto the shafts, stretch tyres on.
7. End-of-line test (fixture + script): IMU bias calibration on a level plate, motor/encoder direction, 10 s balance self-test, head lift, camera frame, speaker chirp, mic level, charge current on a dock.

## Risks to retire with the first prototypes
- N20 torque margin for balancing a ~0.49 kg body (pick 100:1; fall back to 12 V N20 windings on the 2S pack if recovery is weak).
- Shaft engagement in the hub boss is short (about 5 mm on a 10 mm shaft): use the 12 mm extended-shaft motor option or add a set screw.
- Visor optics: tint level vs eye brightness; may need a black mask print on the inside.
- Wi-Fi range from inside the head with the display in front of the antenna.
