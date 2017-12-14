from rif import rcl
import numpy as np


class XformCheck:

    def __init__(self, *, sym=None, origin_segment=None,
                 is_exactly=None, z_axes_intersection=None, lever=100.0):
        if 1 is not ((None is not sym) +
                     (None is not is_exactly) +
                     (None is not z_axes_intersection)):
            raise ValueError(
                'required: exactly one of sym, is_exactly, or z_axes_intersection')
        if origin_segment is not None and sym is None:
            raise ValueError('origin_segment requires sym')
        self.sym = sym
        self.origin_segment = origin_segment
        self.is_exactly = is_exactly
        self.lever = lever

    def __call__(self, xform):

        # todo: this should probably do something...i

        # todo: this should probably do something...i

        # todo: this should probably do something...i

        # todo: this should probably do something...i

        # todo: this should probably do something...i

        return np.ones(xform.shape[:-2])


class GeomCheck:

    def __init__(self, *, from_segment=0, to_segment=-1, tol=1.0, **kwargs):
        self.from_segment = from_segment
        self.to_segment = to_segment
        self.check_xform = XformCheck(**kwargs)

    def __call__(self, positions):
        x_from = positions[self.from_segment]
        x_to = positions[self.to_segment]
        x = np.linarg.inv(x_from) @ x_to
        return self.check_xform(x)


class SpliceSite:

    def __init__(self, resids, polarity):
        self.resids = list(resids)
        self.polarity = polarity


class Spliceable:

    def __init__(self, body, *, sites, bodyid=None):
        self.body = body
        self.bodyid = bodyid
        if callable(sites):
            sites = sites(body)
        self.sites = list(sites)

    def splicable_positions(self):
        """selection of resids, and map 'global' index to selected index"""
        resid_subset = set()
        for site in self.sites:
            resid_subset |= set(site.resids)
        resid_subset = np.array(list(resid_subset))
        # really? must be an easier way to 'invert' a mapping in numpy?
        N = len(self.body) + 1
        val, idx = np.where(0 == (np.arange(N)[np.newaxis, :] -
                                  resid_subset[:, np.newaxis]))
        to_subset = np.array(N * [-1])
        to_subset[idx] = val
        assert (to_subset[resid_subset] == np.arange(len(resid_subset))).all()
        return resid_subset, to_subset


class Segment:

    def __init__(self, splicables, *, entry=None, exit=None):
        self.entrypol = entry
        self.exitpol = exit
        self.init(splicables, entry, exit)

    def init(self, splicables=None, entry=None, exit=None):
        if not (entry or exit):
            raise ValueError('at least one of entry/exit required')
        self.splicables = list(splicables) or self.splicables
        self.entrypol = entry or self.entrypol
        self.exitpol = exit or self.exitpol
        # each array has all in/out pairs
        self.x2exit, self.x2orig = list(), list()
        self.entryresid, self.exitresid, self.bodyid = list(), list(), list()
        # this whole loop is pretty inefficient, but that probably
        # doesn't matter much given the cost subsequent operations (?)
        for ibody, splicable in enumerate(self.splicables):
            resid_subset, to_subset = splicable.splicable_positions()
            bodyid = ibody if splicable.bodyid is None else splicable.bodyid
            # extract 'stubs' from body at selected positions
            # rif 'stubs' have 'extra' 'features'... the raw field is
            # just bog-standard homogeneous matrices
            bbstubs = rcl.bbstubs(splicable.body, resid_subset)['raw']
            if len(resid_subset) != bbstubs.shape[0]:
                raise ValueError("no funny residdues supported")
            bbstubs_inv = np.linalg.inv(bbstubs)
            entry_sites = (list(enumerate(splicable.sites)) if self.entrypol else
                           [(-1, SpliceSite(resids=[np.nan],
                                            polarity=self.entrypol))])
            exit_sites = (list(enumerate(splicable.sites)) if self.exitpol else
                          [(-1, SpliceSite(resids=[np.nan],
                                           polarity=self.exitpol))])
            for isite, entry_site in entry_sites:
                if entry_site.polarity == self.entrypol:
                    for jsite, exit_site in exit_sites:
                        if isite != jsite and exit_site.polarity == self.exitpol:
                            for ires in entry_site.resids:
                                istub_inv = (np.identity(4) if np.isnan(ires)
                                             else bbstubs_inv[to_subset[ires]])
                                for jres in exit_site.resids:
                                    jstub = (np.identity(4) if np.isnan(jres)
                                             else bbstubs[to_subset[jres]])
                                    self.x2exit.append(istub_inv @ jstub)
                                    self.x2orig.append(istub_inv)
                                    self.entryresid.append(ires)
                                    self.exitresid.append(jres)
                                    self.bodyid.append(bodyid)
        if len(self.x2exit) is 0:
            raise ValueError('no valid splices found')
        self.x2exit = np.stack(self.x2exit)
        self.x2orig = np.stack(self.x2orig)
        self.entryresid = np.array(self.entryresid)
        self.exitresid = np.array(self.exitresid)
        self.bodyid = np.array(self.bodyid)


class Worms:

    def __init__(self, segments, score, solutions):
        self.segments = segments
        self.score = score
        self.solutions = solutions


def all_chained_xforms(x2exit, x2orig):
    fullaxes = (np.newaxis,) * (len(x2exit) - 1)
    xexit = [x2exit[0][fullaxes], ]
    xorig = [x2orig[0][fullaxes], ]
    for iseg in range(1, len(x2exit)):
        fullaxes = (slice(None),) + (np.newaxis,) * iseg
        xexit.append(x2exit[iseg][fullaxes] @ xexit[iseg - 1])
        xorig.append(x2orig[iseg][fullaxes] @ xexit[iseg - 1]
                     # for last in chain, exit==orig
                     if iseg != len(x2exit) - 1 else xexit[-1])
    return xexit, xorig


def grow(segments, *, criteria, cache=None):
    if segments[0].entrypol is not None:
        raise ValueError('beginning of worm cant have entry')
    if segments[-1].exitpol is not None:
        raise ValueError('end of worm cant have exit')
    for a, b in zip(segments[:-1], segments[1:]):
        if not (a.exitpol and b.entrypol and a.exitpol != b.entrypol):
            raise ValueError('incompatible exit->entry polarity: '
                             + str(a.exitpol) + '->'
                             + str(b.entrypol) + ' on segment pair: '
                             + str((segments.index(a), segments.index(b))))
    import time
    t = time.clock()
    xexit, xorig = all_chained_xforms([s.x2exit for s in segments],
                                      [s.x2orig for s in segments])
    t = time.clock() - t

    for ep, bp in zip(xexit, xorig):
        assert len(ep.shape) == len(segments) + 2
        assert ep.shape == bp.shape
    assert np.all(xexit[-1] == xorig[-1])

    xdist = np.sqrt(np.sum(xorig[-1][..., :3, 3]**2, axis=-1))
    print("%7.3f %7.1f %10.6f %7.0f/s %9d %7d mb" %
          (np.min(xdist),
           np.max(xdist),
           t,
           xexit[-1].size / 16 / t,
           xexit[-1].size / 16,
           xexit[-1].size * xexit[-1].itemsize * 4 / 1_000_000.0))

    # raise NotImplementedError('display with pymol here.... check
    # ordering...')

    return None