"""Unfactored statics for a vertically aligned shear-wall stack.

Story i = 1 is the bottom. Story forces are applied at the top of each story.
Results are strength-level effects; load-combination factors are applied by
the design checks. Equations A1, A6, A7 of docs/spec-io.md and example
§3.3.4-3.3.6 (Figure 3.5, Table 3.7).
"""

from __future__ import annotations

from dataclasses import dataclass

from design.inputs import DesignInputs
from design.trace import Step, Tracer, fmt


@dataclass(frozen=True)
class StoryForces:
    story: int
    h_ft: float
    V_lb: float  # cumulative story shear
    M_OT_ftlb: float  # overturning moment at the bottom of the story
    w_D_plf: float  # cumulative dead line load at the bottom of the story, incl. wall self-weight
    w_L_plf: float
    w_Lr_plf: float
    d_arm_ft: float  # chord lever arm
    chord_length_ft: float  # chord length carrying gravity load to the posts
    steps: tuple[Step, ...]


def example_layout(n: int, t_in: float, gap_in: float, outboard: int, b_ft: float) -> tuple[float, float, float, float]:
    """(X_t, X_c, chord length, d) for the example layout: posts of thickness t along the wall,
    ``outboard`` of them beyond the rod, the rest inboard after a ``gap`` (example Figs. 3.7-3.8).

    X_t: wall end to rod centre (in.); X_c: wall end to the post centroid (in.).
    """
    out = min(n, outboard)
    xs = [t_in * (k + 0.5) for k in range(out)]
    xs += [out * t_in + gap_in + t_in * (k + 0.5) for k in range(n - out)]
    x_t = out * t_in + gap_in / 2
    x_c = sum(xs) / n
    return x_t, x_c, (n * t_in + gap_in) / 12, b_ft - (x_t + x_c) / 12


def stack_forces(inp: DesignInputs) -> list[StoryForces]:
    n = len(inp.stories)
    b = inp.b_ft
    out: list[StoryForces] = []
    for i in range(1, n + 1):
        t = Tracer(f"S{i}.statics")
        above = inp.stories[i - 1:]
        V = sum(s.F_lb for s in above)
        t.step("V", "Story shear (strength level)", "V", r"V_i = \sum_{j \ge i} F_j",
               " + ".join(fmt(s.F_lb, 0) for s in above) + " lb", V, "lb", "statics", "statics")

        # Lever arm of each force about the bottom of story i: sum of story heights from i up to j.
        terms, M = [], 0.0
        for j in range(i, n + 1):
            arm = sum(inp.stories[k - 1].h_ft for k in range(i, j + 1))
            F = inp.stories[j - 1].F_lb
            M += F * arm
            terms.append(f"{fmt(F, 0)}({fmt(arm, 2)})")
        eq = r"M_{OT,i} = \sum_{j \ge i} F_j (H_j - H_{i-1})"
        subst = " + ".join(terms)
        if inp.load_type == "wind" and inp.roof_uplift_plf > 0:
            Mu = inp.roof_uplift_plf * b**2 / 2
            M += Mu
            eq += r" + w_{up} b^2 / 2"
            subst += f" + {fmt(inp.roof_uplift_plf, 0)}({fmt(b, 2)})²/2"
            t.step("M_up", "Roof uplift overturning", "M_up", r"w_{up} b^2 / 2",
                   f"{fmt(inp.roof_uplift_plf, 0)} plf ({fmt(b, 2)} ft)² / 2", Mu, "ft-lb",
                   "WoodWorks 5-story example §4.5.2", "memory")
        t.step("M_OT", "Overturning moment at story base (strength level)", "M_OT", eq,
               subst + " ft-lb", M, "ft-lb", "statics", "statics")

        wD = sum(s.w_D_plf + s.w_wall_plf for s in above)
        wL = sum(s.w_L_plf for s in above)
        wLr = sum(s.w_Lr_plf for s in above)
        t.step("w_D", "Cumulative dead line load", "w_D", r"w_{D,i} = \sum_{j \ge i}(w_{D,j} + w_{wall,j})",
               " + ".join(f"({fmt(s.w_D_plf, 0)} + {fmt(s.w_wall_plf, 0)})" for s in above) + " plf",
               wD, "plf", "statics", "statics")
        t.step("w_L", "Cumulative floor live line load", "w_L", r"\sum_{j \ge i} w_{L,j}", "", wL, "plf",
               "statics", "statics")
        t.step("w_Lr", "Cumulative roof live line load", "w_Lr", r"\sum_{j \ge i} w_{Lr,j}", "", wLr, "plf",
               "statics", "statics")

        s = inp.stories[i - 1]
        c = s.chord
        if c.layout == "example":
            cite_ex = "statics; WoodWorks 5-story example Figs. 3.7-3.8, Table 3.6 (post layout)"
            x_t, x_c, Lc, d_ex = example_layout(c.n_posts, c.post_thickness_in, c.rod_gap_in, c.outboard_posts, b)
            t.step("X_t", "Wall end to rod centre", "X_t", r"X_t = n_{out} t + g/2",
                   f"{min(c.n_posts, c.outboard_posts)}({c.post_thickness_in}) + {c.rod_gap_in}/2", x_t, "in",
                   cite_ex, "assumption",
                   note=f"{c.outboard_posts} posts outboard of the rod, the rest inboard after a {c.rod_gap_in} in. gap")
            t.step("X_c", "Wall end to post centroid", "X_c", r"X_c = \sum x_k / n", f"{c.n_posts} posts", x_c, "in",
                   cite_ex, "assumption")
            Lc = t.step("L_c", "Chord length", "L_c", r"L_c = (n t + g) / 12",
                        f"({c.n_posts}({c.post_thickness_in}) + {c.rod_gap_in}) / 12", Lc, "ft", cite_ex, "assumption")
            d = t.step("d", "Chord lever arm (layout rule)", "d", r"d = b - (X_t + X_c) / 12",
                       f"{fmt(b, 2)} − ({x_t:.3f} + {x_c:.3f}) / 12", d_ex, "ft", cite_ex, "assumption")
        elif c.d_arm_ft is not None:
            d = t.step("d", "Chord lever arm (given)", "d", "d = given", f"d = {fmt(s.chord.d_arm_ft, 2)} ft",
                       s.chord.d_arm_ft, "ft", "input; example Fig. 3.6", "assumption",
                       note="Rod centre to compression-post centroid, as used in example Table 3.6")
        else:
            d = t.step("d", "Chord lever arm, default (D2)", "d", r"d = b - d_{post}/12",
                       f"{fmt(b, 2)} − {fmt(inp.d_post_in, 2)}/12", b - inp.d_post_in / 12, "ft",
                       "spec-io D2", "assumption")
        if c.layout != "example":
            Lc = c.chord_length_ft
        out.append(StoryForces(i, s.h_ft, V, M, wD, wL, wLr, d, Lc, tuple(t.steps)))
    return out
