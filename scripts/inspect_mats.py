import numpy as np
import scipy.io
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "data" / "propellants" / "mat"
for p in sorted(root.glob("*.mat")):
    d = scipy.io.loadmat(p, squeeze_me=True, struct_as_record=False)
    s = d["s"]
    k = np.asarray(s.prop_k)
    of = np.atleast_1d(np.asarray(s.prop_OF, dtype=float)).ravel()
    pc = np.atleast_1d(np.asarray(s.prop_Pc, dtype=float)).ravel()
    opt = getattr(s, "opt_OF", None)
    print(
        f"{p.stem:22s} k={k.shape} OF={of.shape} Pc={pc.shape} "
        f"Reg={np.asarray(s.prop_Reg)} rho={s.prop_Rho} opt={opt}"
    )
