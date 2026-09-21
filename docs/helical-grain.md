# Experimental helical grain

In **Advanced**, enable advanced options and select **helical**. Use **Shifting OF**. Set center offset (distance from the motor axis to the port center), pitch (axial length per turn), and an explicitly assumed regression multiplier. Grain ID is the circle diameter measured in an axial cross-section. Offset zero gives a straight control using the same volume-conserving update.

This is a first-order, fixed-shape sensitivity model. It **does not predict swirl enhancement**. Multiplier 1 isolates the assumed geometric-area effect. A larger multiplier is a user hypothesis, not a measured correlation or guaranteed improvement. Standard cylindrical mode retains the original MATLAB algorithm.

## Geometry and assumptions

The void is a circular opening in each plane perpendicular to the motor axis. Its center rotates about that axis along the grain. It is **not** a circle swept perpendicular to a helical centerline, nor a rifled/grooved straight port.

For axial coordinate z, port radius r, center offset e, pitch p and grain length L (all meters), define k = 2π/p. The surface is:

$$
\boldsymbol{x}(\theta,z) = (e\cos(kz)+r\cos\theta,\ e\sin(kz)+r\sin\theta,\ z).
$$

Direct integration of this parameterized surface gives the following geometric identities (derived for this implementation, not an empirical helical correlation):

$$
V_p=\pi r^2L,\qquad A_b=2\pi rLH,\qquad
H=\frac{1}{2\pi}\int_0^{2\pi}\sqrt{1+(ek)^2\sin^2\theta}\,d\theta
=\frac{2}{\pi}E(-(ek)^2).
$$

Here Vp is port volume (m³), Ab is burning side area (m²), H is dimensionless, and E is the complete elliptic integral of the second kind in parameter convention. The outer surface and grain ends are assumed inhibited. The remaining fuel volume is the outer cylinder volume minus Vp, so equal initial ID, OD, length and density mean equal initial fuel masses regardless of pitch/offset.

The model uses HRAP's existing empirical regression law with **axial** flux G = oxidizer mass flow / (πr²) in kg/(m²·s), and axial length L in meters. It applies the configured multiplier M:

$$
u = 0.001\,aG^nL^m M,\qquad \dot m_f=\rho_f u A_b.
$$

u is an assumed surface-normal consumption rate (m/s); the 0.001 converts the numerical millimeter-based regression convention in `engine/grain.py`. The dimensions of coefficient a depend on exponents n and m and these chosen input units. Coefficients must be established for the actual fuel/flow conditions. Fuel density ρf is kg/m³. This model uses axial flux as a simplifying closure, not a resolved local flow field.

Offset and pitch stay fixed; growth is averaged into a larger circle in every axial plane. For a time step Δt (s), fuel consumption Δmf (kg) and updated radius are:

$$
\Delta m_f=\min\left(\dot m_f\Delta t,\ \rho_f\pi L[(R-e)^2-r^2]\right),\qquad
r_{new}=\sqrt{r^2+\frac{\Delta m_f}{\rho_f\pi L}}.
$$

R is the grain's outer radius. This makes fuel mass loss and gas-volume gain consistent. At a wall-crossing step the actual clipped Δmf/Δt feeds O/F and the chamber model. Time integration remains first-order; wall-contact time is resolved to the time step. The reported `rdot` is the effective normal consumption rate; the radius growth rate is approximately H times that value.

## Model boundary and interpretation

- Stops at the first outer-wall contact, r + e = R, with `Port Reached Outer Wall`. There may be substantial fuel and oxidizer remaining. This is a geometry limit, not complete burnout; simulation impulse at that event is a partial integral. Do not append an artificial tail and call it a complete motor prediction.
- Fixed offset/pitch cannot capture the port relaxing toward a cylinder, spatially varying normal regression, flame behavior, helical pressure losses, injector swirl interaction, or structural failure. More surface area need not mean a better motor.
- The existing motor schematic displays an equivalent straight port. It does not show the helical shape or provide manufacturing geometry.
- Combustion tables retain their existing interpolation/boundary handling. Check whether simulated O/F and pressure stay within the selected propellant table; out-of-range results require additional scrutiny.
- The final wall-crossing step clips fuel over a full time step while oxidizer still flows. Its O/F can spike and vary strongly with time step; that last sample is a numerical termination artifact, not a predicted physical transient. Check integrated outputs and event-time convergence, and compare pre-contact intervals.
- A fair study records initial fuel mass/port area, remaining fuel, termination reason, and a common time interval. Equal initial mass does not imply equal usable fuel before the helical geometry limit.

## Research context

The [2015 journal paper by Whitmore et al.](https://digitalcommons.usu.edu/mae_facpub/78/) describes ABS/GOX experiments with enhancement that diminishes during regression. The authors' [2014 conference paper](https://www.researchgate.net/publication/269208360_High_Regression_Rate_Hybrid_Rocket_Fuel_Grains_with_Helical_Port_Structures) also discusses nitrous/ABS. These studies motivate investigating helical ports; **this implementation does not use a calibrated helical ABS/N₂O correlation**, and its fixed-shape closure is not the authors' engineering model.

Validation here means geometric integration, fuel/volume conservation, wall-event checks, straight-limit behavior and timestep refinement. It does not replace experimental calibration.
