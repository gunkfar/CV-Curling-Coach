"""Curling sheet geometry in the ice (world) coordinate frame.

World frame: origin at the tee (house center) on the ice surface, +X along the
center line toward the back line, Z up, units in meters. +Y follows the
right-hand rule (90 degrees counter-clockwise from +X when viewed from above).
"""

from dataclasses import dataclass, field

# Ring keys used in keypoint names, outermost first.
RING_KEYS = ("12", "8", "4", "btn")

# Physical correspondences beyond the 17 ring / line crossings that have a known ice position (v2 addition, used by the
# observation editor): where the CENTRE line meets the hog line's house-side (inner) / far (outer) edge. They are not part of
# keypoint_names() (the established 17-point set), so every existing caller behaves as before. Their positions rest on the same
# hog-line assumption (21 ft, 4 in wide) as the hog-line position constraint, so they are NOT independent of it.
EXTRA_KEYPOINT_NAMES = ("cl_hogline_inner", "cl_hogline_outer")


@dataclass(frozen=True)
class SheetSpec:
    """Painted-geometry dimensions in meters (WCF defaults, measured to outer edges)."""

    ring_radii_m: dict = field(default_factory=lambda: {
        "12": 1.829,   # 12-foot circle
        "8": 1.219,    # 8-foot circle
        "4": 0.610,    # 4-foot circle
        "btn": 0.1524, # button; WCF only specifies a minimum, so venues may differ
    })
    back_line_x_m: float = 1.829
    stone_radius_m: float = 0.1455   # max circumference 0.9144 m
    # Hog line (calibration_w_hogline addition). World Curling rule R1: 4 in (101.6 mm) wide, placed so that its INSIDE
    # (house-side) edge is 21 ft = 6.401 m from the centre of the tee line. It lies on the side away from the back line,
    # i.e. at negative X in this frame (+X points toward the back line). The far edge is 101.6 mm further out.
    hog_line_inner_x_m: float = -6.401
    hog_line_width_m: float = 0.1016

    def ring_radius(self, ring: str) -> float:
        try:
            return self.ring_radii_m[ring]
        except KeyError:
            raise KeyError(f"Unknown ring {ring!r}; expected one of {list(self.ring_radii_m)}") from None

    def hog_line_edge_x(self, edge: str = "inner") -> float:
        """Ice X (m) of a hog-line edge: 'inner' = house-side edge (the WCF reference), 'outer' = far edge, 'centre'."""
        offsets = {"inner": 0.0, "centre": -0.5 * self.hog_line_width_m, "outer": -self.hog_line_width_m}
        if edge not in offsets:
            raise KeyError(f"Unknown hog-line edge {edge!r}; expected one of {list(offsets)}")
        return self.hog_line_inner_x_m + offsets[edge]

    def keypoint_world(self, name: str) -> tuple[float, float]:
        """Ice coordinates of a named keypoint.

        Names: "tee", "cl_back_<ring>", "cl_hog_<ring>", "tl_pos_<ring>", "tl_neg_<ring>",
        where <ring> is one of RING_KEYS. Each is where a painted line's center
        crosses that ring's outer edge. Also "cl_hogline_inner" / "cl_hogline_outer" (EXTRA_KEYPOINT_NAMES).
        """
        if name == "tee":
            return (0.0, 0.0)
        if name in EXTRA_KEYPOINT_NAMES:
            return (self.hog_line_edge_x("inner" if name.endswith("inner") else "outer"), 0.0)
        prefix, _, ring = name.rpartition("_")
        offsets = {"cl_back": (1, 0), "cl_hog": (-1, 0), "tl_pos": (0, 1), "tl_neg": (0, -1)}
        if prefix not in offsets or ring not in self.ring_radii_m:
            raise KeyError(f"Unknown keypoint name {name!r}")
        r = self.ring_radii_m[ring]
        dx, dy = offsets[prefix]
        return (dx * r, dy * r)

    def keypoint_names(self) -> list[str]:
        names = ["tee"]
        for prefix in ("cl_back", "cl_hog", "tl_pos", "tl_neg"):
            names += [f"{prefix}_{ring}" for ring in RING_KEYS]
        return names

    def extra_keypoint_names(self) -> list[str]:
        """Supported keypoints beyond the established 17 (see EXTRA_KEYPOINT_NAMES)."""
        return list(EXTRA_KEYPOINT_NAMES)

    def all_keypoint_names(self) -> list[str]:
        return self.keypoint_names() + self.extra_keypoint_names()

    def to_dict(self) -> dict:
        return {"ring_radii_m": dict(self.ring_radii_m), "back_line_x_m": self.back_line_x_m,
                "stone_radius_m": self.stone_radius_m, "hog_line_inner_x_m": self.hog_line_inner_x_m,
                "hog_line_width_m": self.hog_line_width_m}

    @classmethod
    def from_dict(cls, d: dict) -> "SheetSpec":
        # hog fields are optional, so calibration files written by the original package still load
        return cls(ring_radii_m=dict(d["ring_radii_m"]), back_line_x_m=d["back_line_x_m"],
                   stone_radius_m=d["stone_radius_m"], hog_line_inner_x_m=d.get("hog_line_inner_x_m", -6.401),
                   hog_line_width_m=d.get("hog_line_width_m", 0.1016))
