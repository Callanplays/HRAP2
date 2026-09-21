# Experimental star grain

Enable Advanced, select **star**, and select **Shifting OF**. Set tip count and the valley-radius / tip-radius ratio. **Grain ID is the initial tip-to-tip diameter**, not an equal-area circle diameter. Tip count is 3–16 and the ratio must be between zero and cos(π/tip count), so the polygon has actual inward valleys.

This replaces the old perimeter-only shortcut, which retained circular mass and chamber-volume bookkeeping. Both advanced shape models now require Shifting OF; Constant OF fixes fuel flow externally and cannot provide the intended grain comparison. Standard cylindrical mode retains its MATLAB algorithm.

## Geometric model

The initial star polygon alternates tip and valley radii about the motor axis. It is extruded straight along the grain length. Its initial open area is:

$$
A_0 = N r_t r_v \sin(\pi/N).
$$

N is the number of tips, rt and rv are tip and valley radii (m), and A0 is area (m²). This follows directly by summing the triangles between adjacent vertices. Grain ends and the outer surface are inhibited.

Regression offsets the original polygon outward by cumulative normal burn distance. This rounds convex tips and fills the inward valleys rather than scaling the star. [Shapely's round buffer](https://shapely.readthedocs.io/en/stable/reference/shapely.buffer.html) approximates the circle used for the offset with line segments. The implementation uses 64 segments per quadrant and a lookup table of 513 distances through first outer-wall contact; linear area interpolation makes simulation steps inexpensive. Arc resolution and lookup spacing have separate numerical checks.

With current open area A, axial grain length L, fuel density ρf and outer radius R, fuel mass and equal-area diameter are:

$$
m_f=\rho_f(\pi R^2-A)L,\qquad D_{eq}=2\sqrt{A/\pi}.
$$

The empirical normal regression law is the same axial-flux Shifting OF law used in HRAP: numerical rate 0.001 a G^n L^m in m/s, with G = oxidizer mass flow / A in kg/(m²·s) and L in meters. The coefficient a carries the dimensions appropriate to that convention and the configured exponents. The uniform regression rate is a modeling assumption; it does not model differing local heat transfer at tips/valleys or establish ABS coefficients for a printed grain.

The step's consumed fuel is **ρf L times the actual area increase**. That same consumption sets fuel mass flow and O/F, while Deq makes the chamber's gas-volume change agree. No second perimeter multiplier is applied. Initial fuel and gas masses use the actual star area.

The simulation stops when normal offset reaches R − rt, at first outer-wall contact, with `Port Reached Outer Wall`. Residual fuel can remain. The final clipped step can produce an O/F spike, just as in the helical closure; that numerical endpoint is not a modeled physical transient. End time and integrated outputs need timestep checks.

## What is displayed

Port-ID traces and the motor schematic show **equal-area diameter**, including before the run and at recorded time zero. They do not show the star boundary. The schematic uses recorded initial mass as its fuel-percentage denominator while viewing results. Configuration JSON retains the input tip-to-tip diameter.

Comparisons should match initial area/fuel mass and report residual fuel and the termination condition. A higher initial burning perimeter need not yield better total performance. Hardware dimensions, material properties and regression behavior still need team confirmation and test calibration.
