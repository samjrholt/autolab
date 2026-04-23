"""Run inside the WSL pixi env: sanity-check the APIs the sensor.html demo uses."""

import json

# 1. Material lookup.
import mammos_entity as me
import mammos_units as u
import mammos_spindynamics
import mammos_analysis
u.set_enabled_equivalencies(u.magnetic_flux_field())

results = mammos_spindynamics.db.get_spontaneous_magnetization("Ni80Fe20")
kuz = mammos_analysis.kuzmin_properties(T=results.T, Ms=results.Ms)

T = me.T(300, unit="K")
A = kuz.A(T)
Ms = kuz.Ms(T)
print("material: Ni80Fe20 at 300 K")
print("  Ms:", Ms.q.to("A/m"))
print("  A:",  A.q.to("J/m"))

# 2. Superellipse indicator (diamond / n=1 by default in the demo; we'll make n a knob).
import discretisedfield as df
import micromagneticmodel as mm
import oommfc as mc
import numpy as np

L_m = 100e-9
t_m = 5e-9
region = df.Region(p1=(-L_m/2, -L_m/2, -t_m/2), p2=(L_m/2, L_m/2, t_m/2))
mesh = df.Mesh(region=region, n=(40, 40, 1))

sx_m, sy_m, n_exp = 40e-9, 30e-9, 2.0  # superellipse n=2 → ellipse
Ms_Apm = Ms.q.to("A/m").value

def norm_fn(p):
    x, y, _ = p
    inside = (abs(x)/sx_m)**n_exp + (abs(y)/sy_m)**n_exp <= 1.0
    return Ms_Apm if inside else 0.0

system = mm.System(name="sensor_probe")
system.energy = mm.Exchange(A=A.value) + mm.Demag() + mm.Zeeman(H=(0, 0, 0))
system.m = df.Field(mesh, nvdim=3, value=(1, 0, 0), norm=norm_fn, valid="norm")

# 3. Hysteresis via HysteresisDriver (matches the demo page). Small sweep to finish quickly.
Hmin = (0, 0, 0)
Hmax = ((0.1, 100, 0) * u.mT).to(u.A / u.m)
n_steps = 21

hd = mc.HysteresisDriver()
hd.drive(system, Hsteps=[[Hmin, tuple(Hmax.value), n_steps]], verbose=0)

H_y = me.H(
    system.table.data["By_hysteresis"].values *
    u.Unit(system.table.units["By_hysteresis"]).to(u.A / u.m)
)
M_y = me.Entity("Magnetization", system.table.data["my"].values * Ms.q.to("A/m"))

# 4. Linear-segment FOM.
res = mammos_analysis.hysteresis.find_linear_segment(
    H_y, M_y, margin=0.05 * Ms.q.to("A/m"), min_points=2,
)
print("linear-segment analysis:")
print("  Hmax (linear region width, A/m):", res.Hmax.value)
print("  gradient:", res.gradient)
print("  Mr:", res.Mr)
print()
print(json.dumps({"ok": True, "Hmax_A_per_m": float(res.Hmax.value)}))
