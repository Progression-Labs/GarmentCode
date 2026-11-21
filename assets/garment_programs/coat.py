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
    is its mirror. The centre edge is `centre_len` long and the side edge `side_len`; the hem
    joins their lower ends, bowed upwards by `hem_curve` (a fraction of its length) when the
    front is cut away. With `vent_from` set, the centre edge is split there: the part above is
    the 'centre' interface (sewn to the other back panel), the part below is left open. With
    `side_sewn` shorter than the side, only that much of the side below the waist is the 'side'
    interface: a tail hangs free below a front cut away above it.
    """

    def __init__(self, name, width, side_len, centre_len, flare=0., hem_curve=0., vent_from=None,
                 side_sewn=None):
        super().__init__(name)

        side_bottom = [-width - flare, -side_len]
        side_top = [-width, 0]
        centre_top = [0, 0]
        centre_bottom = [0, -centre_len]

        if side_sewn is not None and side_sewn < side_len - 0.5:
            t = side_sewn / side_len
            split = [side_top[0] + (side_bottom[0] - side_top[0]) * t, -side_sewn]
            side = pyg.EdgeSeqFactory.from_verts(side_bottom, split, side_top)
            self.side = side[1]
        else:
            side = pyg.EdgeSequence(pyg.Edge(side_bottom, side_top))
            self.side = side[0]
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

        # The skirt clears the hips with ease: each panel widens down its side seam so that at the
        # hip line it carries its share of the hip girth.
        ease = params['ease']['v']

        def flare_for(top_w, share, length):
            # Widening to the hip line, then hanging nearly straight: a coat's skirt falls past
            # the hips rather than spreading on to the hem.
            want = share * ease
            return max(0., (want - top_w) * min(length / max(hips_depth, 1.), params['hang']['v']))

        hips = body['hips']
        hips_back = body['hip_back_width']
        front_share = (hips - hips_back) / 2
        back_share = hips_back / 2

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
        z_front, z_back = 25, -20
        y = body['_waist_level']

        # One flare for both sides of a side seam, so the two edges sewn together are one length.
        seam_flare = max(flare_for(front_w, front_share, tails), flare_for(back_w, back_share, tails))

        def panel(name, width, side, centre, share, vent=None, hem_curve=0., side_sewn=None):
            return CoatSkirtPanel(
                name, width, side, centre,
                flare=seam_flare * side / tails,
                hem_curve=hem_curve, vent_from=vent, side_sewn=side_sewn)

        self.front_r = panel('coat_skirt_front_r', front_w, front_side, front_centre,
                             front_share, hem_curve=curve).translate_to([0, y, z_front])
        self.front_l = panel('coat_skirt_front_l', front_w, front_side, front_centre,
                             front_share, hem_curve=curve).mirror().translate_to([0, y, z_front])
        # The back's side is sewn as far down as the front reaches; below that the tail is free.
        self.back_r = panel('coat_skirt_back_r', back_w, tails, tails, back_share,
                            vent=vent_from, side_sewn=front_side).translate_to([0, y, z_back])
        self.back_l = panel('coat_skirt_back_l', back_w, tails, tails, back_share,
                            vent=vent_from, side_sewn=front_side).mirror().translate_to([0, y, z_back])

        self.stitching_rules = pyg.Stitches(
            (self.front_r.interfaces['side'], self.back_r.interfaces['side']),
            (self.front_l.interfaces['side'], self.back_l.interfaces['side']),
            (self.back_r.interfaces['centre'], self.back_l.interfaces['centre']),
        )

        self.interfaces = {
            'top': pyg.Interface.from_multiple(
                self.front_r.interfaces['top'],
                self.front_l.interfaces['top'],
                self.back_l.interfaces['top'],
                self.back_r.interfaces['top'],
            ),
        }

    def length(self):
        return self.back_r.length()
