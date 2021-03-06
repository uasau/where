"""Create a map showing all sites in analysis and some simple statistics

Description:
------------

asdf

"""

# Standard library imports

# External library imports
from branca import colormap
import folium
import numpy as np

# Midgard imports
from midgard.dev import plugins

# Where imports
from where.lib import config
from where.lib import log
from where.lib.unit import Unit


@plugins.register
def web_map_writer(dset):
    file_path = config.files.path("output_web_map", file_vars=dset.vars)
    log.info(f"Storing a web map at '{file_path}'. Open in a browser to look at it")

    sites = read_site_latlons(dset)
    map = draw_map(dset, sites)
    map.save(str(file_path))


def read_site_latlons(dset):
    sites = dict()
    for station in dset.unique("station"):
        for _ in dset.for_each_suffix("station"):
            llh = dset.first("site_pos.llh", station=station)
            if llh is not None:
                sites[station] = (llh[0] * Unit.rad2degree, llh[1] * Unit.rad2degree)

    return sites


def draw_map(dset, latlons):
    stations = dset.unique("station")
    rms = dset.rms("residual") * Unit.m2mm

    # Map layers
    map = folium.Map((20, 0), zoom_start=2)  # Default is OpenStreetMap
    folium.TileLayer("Stamen Toner").add_to(map)
    folium.TileLayer("CartoDB Positron").add_to(map)

    # Colors
    colors = colormap.LinearColormap(("green", "yellow", "red"), vmin=rms / 2, vmax=rms * 2)
    colors.caption = "RMS [mm]"
    map.add_child(colors)

    # Stations
    stations_layer = folium.FeatureGroup(name="Stations")
    for sta in stations:
        idx = dset.filter(station=sta)
        rms = dset.rms("residual", idx=idx) * Unit.m2mm
        other_idx = [dset.filter(idx=idx, station=other) for other in stations]
        others = [
            f"{dset.rms('residual', idx=i) * Unit.m2mm:.3f} mm to {other} ({sum(i)})"
            for i, other in zip(other_idx, stations)
            if other != sta and any(i)
        ]
        popup = f"<b>{sta}</b> ({sum(idx)}): {rms:.3f} mm<br />{'<br />'.join(others)}"
        stations_layer.add_child(
            folium.CircleMarker(
                latlons[sta],
                popup=popup,
                fill=True,
                color=colors(rms),
                radius=max(5, 10 * np.sqrt(np.mean(idx) * len(stations))),
            )
        )
    map.add_child(stations_layer)

    # Baselines
    for sta_1 in stations:
        baseline_layer = folium.FeatureGroup(name="{sta_1} baselines")
        for sta_2 in stations:
            idx = dset.filter(station=sta_1) & dset.filter(station=sta_2)
            if sta_1 == sta_2 or not any(idx):
                continue
            rms = dset.rms("residual", idx=idx) * Unit.m2mm
            locations = [latlons[s] for s in (sta_1, sta_2)]
            popup = "<b>{sta_1} - {sta_2}</b> ({sum(idx)}): {rms:.3f} mm"
            baseline_layer.add_child(
                folium.PolyLine(
                    locations, popup=popup, color=colors(rms), weight=max(1, 2 * np.mean(idx) * len(stations) ** 2)
                )
            )
        if baseline_layer._children:
            map.add_child(baseline_layer)

    folium.LayerControl().add_to(map)
    return map
