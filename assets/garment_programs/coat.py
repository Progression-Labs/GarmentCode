"""Tailored coats: an upper garment open down the centre front, and a coat skirt below the waist
cut as a frock (straight, knee length all round), a morning coat (the front curving away from
the waist to knee-length tails) or a tailcoat (the front cut square at the waist, tails behind).

The front of each is left unsewn: the open centre front, the cutaway hem and the back vent are
free edges, which simulators treat as hems.
"""
from copy import deepcopy

import pygarment as pyg
from assets.garment_programs.base_classes import BaseBottoms
from assets.garment_programs.bodice import BodiceHalf


class FittedCoat(pyg.Component):
    """A fitted bodice with sleeves and a collar, its centre front left open.

    The name carries 'Fitted' so a lower garment under it is cut at the natural waist (full rise),
    as MetaGarment does for fitted tops.
    """

    def __init__(self, body, design) -> None:
        super().__init__(self.__class__.__name__)
        design = deepcopy(design)
        # Asymmetric halves are not supported for coats: both are the right half's design.
        self.right = BodiceHalf('right', body, design, fitted=True)
        self.left = BodiceHalf('left', body, design, fitted=True).mirror()

        # The back is sewn up its centre; the front is not (the coat opens there).
        self.stitching_rules.append(
            (self.right.interfaces['back_in'], self.left.interfaces['back_in']))

        self.interfaces = {
            'bottom': pyg.Interface.from_multiple(
                self.right.interfaces['f_bottom'].reverse(),
                self.left.interfaces['f_bottom'],
                self.left.interfaces['b_bottom'].reverse(),
                self.right.interfaces['b_bottom'],
            )
        }

    def length(self):
        return self.right.length()


class CoatSkirtPanel(pyg.Panel):
    """One quarter of a coat skirt: the right side of the front or the back, its waist on top.

    Built for the body's right side (centre at x = 0, side seam at x = -width), the left side
    is its mirror. The side widens by `hip_out` over the first `hip_depth` below the waist (to
    the hip line, where the skirt carries its share of the hips) and below that hangs straight,
    as a tailored skirt falls past the hips rather than spreading on to its hem. The centre edge
    is `centre_len` long and the side `side_len`; the hem joins their lower ends, bowed upwards by
    `hem_curve` (a fraction of its length) when the front is cut away. With `vent_from` set, the
    centre edge is split there: the part above is the 'centre' interface (sewn to the other back
    panel), the part below is left open. With `side_sewn` shorter than the side, only that much
    of the side below the waist is the 'side' interface, and below it the edge runs free, out to
    the hip line's width if it frees above that line, then to a hem `hem_width` wide (from the
    centre): a tail, narrowing to its point as a cutter shapes one, hanging below a front cut
    away above it.
    """

    def __init__(self, name, width, side_len, centre_len, hip_out=0., hip_depth=1., hem_curve=0.,
                 vent_from=None, side_sewn=None, hem_width=None):
        super().__init__(name)

        def side_at(depth):
            # The sewn line: out to the hip line, then straight down.
            if depth <= hip_depth:
                return [-width - hip_out * depth / hip_depth, -depth]
            return [-width - hip_out, -depth]

        side_top = [-width, 0]
        centre_top = [0, 0]
        centre_bottom = [0, -centre_len]
        free = side_sewn is not None and side_sewn < side_len - 0.5
        sewn_to = side_sewn if free else side_len
        # Top down: the waist, the hip line where the sewn part reaches it, the sewn part's end.
        sewn = [side_top]
        if hip_depth < sewn_to:
            sewn.append(side_at(hip_depth))
        sewn.append(side_at(sewn_to))
        if free:
            side_bottom = [-(width + hip_out) if hem_width is None else -hem_width, -side_len]
            # Free above the hip line (a tailcoat's tails, sewn only to the front's short drop),
            # the tail still widens to carry its share of the hips there before it narrows to
            # its point: run straight from the sewn end, it was drawn tight across the seat.
            hip = [side_at(hip_depth)] if sewn_to < hip_depth < side_len else []
            verts = [side_bottom] + hip + sewn[::-1]
            side = pyg.EdgeSeqFactory.from_verts(*verts)
            sewn_edges = side[1 + len(hip):]
        else:
            side_bottom = sewn[-1]
            side = pyg.EdgeSeqFactory.from_verts(*sewn[::-1])
            # A sequence of its own: the panel's grows into the outline below.
            sewn_edges = side[:]
        self.side = sewn_edges
        self.waist = pyg.Edge(side_top, centre_top)
        if vent_from is not None:
            vent = [0, -vent_from]
            centre = pyg.EdgeSeqFactory.from_verts(centre_top, vent, centre_bottom)
            self.centre_sewn = centre[0]
        else:
            centre = pyg.EdgeSequence(pyg.Edge(centre_top, centre_bottom))
            self.centre_sewn = centre[0]
        if hem_curve:
            hem = pyg.CircleEdgeFactory.from_three_points(
                centre_bottom, side_bottom, [0.5, hem_curve], relative=True)
        else:
            hem = pyg.Edge(centre_bottom, side_bottom)

        self.edges = side
        self.edges.append(self.waist)
        self.edges.append(centre)
        self.edges.append(hem)

        self.interfaces = {
            'side': pyg.Interface(self, self.side),
            'top': pyg.Interface(self, self.waist),
            'centre': pyg.Interface(self, self.centre_sewn),
            'hem': pyg.Interface(self, hem),
        }


class CoatSkirt(BaseBottoms):
    """The skirt of a coat, sewn to its waist seam: four panels, the fronts open at the centre,
    the backs sewn at the centre down to the vent."""

    def __init__(self, body, design, tag='', rise=None, **kwargs) -> None:
        super().__init__(body, design, tag, rise=1.)
        params = design['coat_skirt']
        cut = params['cut']['v']

        waist, hips_depth, back_waist = self.eval_rise(1.)
        tails = hips_depth + params['length']['v'] * body['_leg_length']
        front_w = (waist - back_waist) / 2
        back_w = back_waist / 2

        # The skirt clears the hips with ease: each panel widens down its side seam to the hip
        # line, where it carries its share of the hip girth, and hangs straight below it. One
        # widening for both sides of a side seam, so the two edges sewn together are one length.
        ease = params['ease']['v']
        hips = body['hips']
        hips_back = body['hip_back_width']
        front_share = (hips - hips_back) / 2
        back_share = hips_back / 2
        hip_out = max(0., front_share * ease - front_w, back_share * ease - back_w)

        if cut == 'frock':
            front_side, front_centre, curve = tails, tails, 0.
        elif cut == 'morning':
            front_side = tails
            front_centre = params['front_drop']['v'] * hips_depth
            curve = params['cutaway_curve']['v']
        elif cut == 'tail':
            # Square across at the waist: a narrow band to the side seam, the tails behind.
            front_side = front_centre = params['front_drop']['v'] * hips_depth
            curve = 0.
        else:
            raise ValueError(f'CoatSkirt: unknown cut {cut}')

        vent_from = params['vent']['v'] * tails if params['vent']['v'] else None
        # Where a back panel's side hangs free below the front, it narrows to this much of its
        # width at the hip line: a tail.
        tail_hem = params['tail_hem']['v'] * (back_w + hip_out)
        z_front, z_back = 25, -20
        y = body['_waist_level']

        def panel(name, width, side, centre, vent=None, hem_curve=0., side_sewn=None,
                  hem_width=None):
            return CoatSkirtPanel(
                name, width, side, centre, hip_out=hip_out, hip_depth=hips_depth,
                hem_curve=hem_curve, vent_from=vent, side_sewn=side_sewn, hem_width=hem_width)

        self.front_r = panel('coat_skirt_front_r', front_w, front_side, front_centre,
                             hem_curve=curve).translate_to([0, y, z_front])
        self.front_l = panel('coat_skirt_front_l', front_w, front_side, front_centre,
                             hem_curve=curve).mirror().translate_to([0, y, z_front])
        # The back's side is sewn as far down as the front reaches; below that the tail is free.
        self.back_r = panel('coat_skirt_back_r', back_w, tails, tails, vent=vent_from,
                            side_sewn=front_side, hem_width=tail_hem).translate_to([0, y, z_back])
        self.back_l = panel('coat_skirt_back_l', back_w, tails, tails, vent=vent_from,
                            side_sewn=front_side, hem_width=tail_hem).mirror().translate_to(
                                [0, y, z_back])

        self.stitching_rules = pyg.Stitches(
            (self.front_r.interfaces['side'], self.back_r.interfaces['side']),
            (self.front_l.interfaces['side'], self.back_l.interfaces['side']),
            (self.back_r.interfaces['centre'], self.back_l.interfaces['centre']),
        )

        self.interfaces = {
            # Each waist runs against its bodice's: flipped, the right front's side meets the
            # right front's side. Unflipped, every bodice dart's piece was sewn to the mirror
            # piece of its skirt (the side of a front to its centre), and sewing dragged the
            # fronts round to the back, crossed there in an X.
            'top': pyg.Interface.from_multiple(
                self.front_r.interfaces['top'].flip_edges(),
                self.front_l.interfaces['top'].flip_edges(),
                self.back_l.interfaces['top'].flip_edges(),
                self.back_r.interfaces['top'].flip_edges(),
            ),
        }

    def length(self):
        return self.back_r.length()
