'''
    File: framefield.py
    License: MIT
    Author: Aidan Kurtz
    Created: 06/08/2016
    Python Version: 3.5
    ========================
    This module contains all things 3D frame field.
'''

from visual import *
from utils import tet_centroid, chiral_symmetries

import math
import numpy as np
from scipy import spatial

class Frame(object):
    def __init__(self, u, v, w, location):
        self.u, self.v, self.w = u, v, w
        self.location = location

def init_framefield(tet_mesh, surf_mesh):
    boundary_frames = []
    # The frame field is initialized at the boundary,
    # based on the curvature cross-field and normals.
    for fi, surf_face in enumerate(surf_mesh.faces):
        # Retrieve the tet this face belongs to.
        ti = tet_mesh.adjacent_elements[surf_mesh.face_map.inv[fi]][0]
        tet = tet_mesh.elements[ti]
        # Ignore faces which have 0 curvature.
        if math.isclose(surf_mesh.k1[surf_face[0]], 0) and math.isclose(surf_mesh.k2[surf_face[0]], 0):
            continue
        # @TODO(aidan) Find actual face values, not vertex.
        boundary_frames.append(Frame( surf_mesh.pdir1[surf_face[0]],
                                      surf_mesh.pdir2[surf_face[0]],
                                      surf_mesh.vertex_normals[surf_face[0]],
                                      tet_centroid(tet_mesh, ti) ))

    # Prepare a KDTree of boundary frame coords for quick spatial queries.
    tree = spatial.KDTree(np.vstack([frame.location for frame in boundary_frames]))

    frames = []
    # Now propagate the boundary frames throughout the tet mesh.
    # Each tet frame takes the value of its nearest boundary tet.
    for ti, tet in enumerate(tet_mesh.elements):
        location = tet_centroid(tet_mesh, ti)
        nearest_ti = tree.query(location)[1] # Find closest boundary frame
        # Create new frame
        frames.append(Frame( boundary_frames[nearest_ti].u,
                             boundary_frames[nearest_ti].v,
                             boundary_frames[nearest_ti].w,
                             location ))
    
    return frames

def compute_onerings(tet_mesh, surf_mesh):
    # Compute the one ring of tets surrounding each internal edge.
    one_rings = {}
    for ei, edge in enumerate(tet_mesh.edges):
        # Make sure this is an internal edge, skip if it isn't.
        if (edge[0] in surf_mesh.vertex_map and edge[1] in surf_mesh.vertex_map):
            continue
        # If it is, construct its one ring.
        one_ring = []
        finished = False
        one_ring.append(tet_mesh.edge_adjacent_elements[ei])
        # Walk around the edge until we've closed the one ring.
        while not finished:
            finished = True
            for neigh_ti in tet_mesh.neighbors[one_ring[-1]]:
                neighbor = tet_mesh.elements[neigh_ti]
                # Make sure this neighbor is a viable pick.
                if (neigh_ti == -1 or neigh_ti in one_ring):
                    continue
                # Make sure this neighbor shares the edge.
                if (edge[0] in neighbor and edge[1] in neighbor ):
                    # Add it to the ring.
                    one_ring.append(neigh_ti)
                    finished = False
                    break
        # Store it in our ring dictionary (don't tell golem).
        one_rings[ei] = one_ring
    
    return one_rings

def singular_graph(tet_mesh, one_rings, frames):
    # Compute the matchings for all pairs of face-adjacent tets.
    matchings = {}
    for pair in tet_mesh.adjacent_elements:
        args = []
        # If boundary face, skip.
        if -1 in pair:
            continue
        # Find the best permutation to characterize closeness.
        for permutation in chiral_symmetries:
            arg = frames[pair[0]].u - np.dot(frames[pair[1]].u, permutation.T) + \
                  frames[pair[0]].v - np.dot(frames[pair[1]].v, permutation.T) + \
                  frames[pair[0]].w - np.dot(frames[pair[1]].w, permutation.T)
            args.append(np.linalg.norm(arg))
        # Store the matching
        matchings[tuple(pair)] = chiral_symmetries[np.argmin(args)]

    # Classify the internal edges by type, and find the singular graph.
    # The edge type is determined via concatenation of the matchings around the edge's one-ring.
    lines = []
    for ei, edge in enumerate(tet_mesh.edges):
        try:
            one_ring = one_rings[ei]
        except KeyError:
            continue
        # Concatenate the matchings around the edge to find its type.
        type = np.identity(3)
        for i in range(len(one_ring)):
            matching = []
            pair = (one_ring[(i + 1) % len(one_ring)], one_ring[i])
            # If pair order is reversed, invert permutation matrix
            if pair not in matchings:
                pair = pair[::-1] # reverse
                matching = np.linalg.inv(matchings[pair])
            else:
                matching = matchings[pair]
            # Concatenate transforms     
            type = np.dot(type, matchings[pair])

        # Singular edge.
        if not np.array_equal(type, np.identity(3)):
            lines.append(edge)

    # Plot singular edges.    
    plot_lines(lines, tet_mesh.points)


def optimize_framefield(tet_mesh, frames):
    pass