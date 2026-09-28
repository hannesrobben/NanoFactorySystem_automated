"""Visualization of the Toolpath-IR (docs/05).

    layer_artists   IR -> render primitives (backend-free, shared)
    static          PNG flipbook: plot_layer / plot_job_layers
    interactive     (planned) matplotlib slider view, see docs/05

Deliberately NOT imported by the slicer package ``__init__`` eagerly —
matplotlib stays an optional dependency of the debug path, not of slicing.
"""
from .layer_artists import LayerArtistData, layer_artist_data, job_bounds
from .static import draw_layer, plot_layer, plot_job_layers

__all__ = [
    "LayerArtistData", "layer_artist_data", "job_bounds",
    "draw_layer", "plot_layer", "plot_job_layers",
]
