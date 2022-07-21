import logging
import math
from datetime import datetime
from typing import List

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib import pyplot as plt
from osgeo import osr, ogr
from qgis._core import QgsProject, Qgis
from shapely.geometry import MultiPolygon

from .tablemodel import TableModel


def compute_resolution_from_mapscale(map_canvas):
    scale = map_canvas.scale()
    map_extent = map_canvas.extent()
    logging.debug(map_extent)
    map_size = map_canvas.size()
    logging.debug(map_size)

    dx = abs(map_extent.xMaximum() - map_extent.xMinimum())
    dy = abs(map_extent.yMaximum() - map_extent.yMinimum())

    resx = dx / map_size.width()
    resy = dy / map_size.height()

    return min(resx, resy)


def min_index_from_array(array, value):
    min_index = 0
    min_value = math.inf
    for i in range(len(array)):
        diff_value = abs(array[i] - value)
        if diff_value < min_value:
            min_value = diff_value
            min_index = i
    return min_index


def generate_graph(dialog, scene, iface, geocube_client):
    logging.debug("generate graph")
    dialog.progressBar.setValue(0)
    instance_name = dialog.instanceComboBox.currentText()
    variable_name = dialog.variablesComboBox.currentText()

    crs = QgsProject.instance().crs().authid()

    resolution = compute_resolution_from_mapscale(iface.mapCanvas())
    logging.debug(resolution)
    x_coord = float(dialog.xCoord.toPlainText())
    y_coord = float(dialog.yCoord.toPlainText())
    transform = [x_coord, y_coord, resolution]
    logging.debug(transform)
    from_date = dialog.timeSeriesStartDate.dateTime()
    logging.debug(from_date)
    to_date = dialog.timeSeriesEndDate.dateTime()
    dialog.progressBar.setValue(20)
    tags_str = str(dialog.timeSeriesTextEdit.toPlainText())
    tags = {}
    if tags_str != "":
        tags_value = tags_str.split(",")
        for value in tags_value:
            s = value.split(":")
            tags[s[0]] = s[1]
        logging.debug(tags)
    if from_date > to_date:
        iface.messageBar().pushMessage("Error", "Wrong date input: Start Date must be before End Date",
                                       level=Qgis.Critical)
        pass
    dialog.progressBar.setValue(40)
    to_time = datetime.strptime(to_date.toString('yyyy-MM-dd HH:mm:ss'), "%Y-%m-%d %H:%M:%S")
    from_time = datetime.strptime(from_date.toString('yyyy-MM-dd HH:mm:ss'), "%Y-%m-%d %H:%M:%S")

    data = geocube_client.get_cube_from_tags(variable_instance=instance_name, variable_name=variable_name,
                                             crs=crs, transform=transform, tags=tags, from_time=from_time,
                                             to_time=to_time)
    dialog.progressBar.setValue(60)
    x_list = []
    y_list = []
    data_table = []
    for key in data:
        x_list.append(datetime.timestamp(key.datetime))
        y_list.append(data[key])
        data_table.append([key.id, key.name, key.datetime.strftime("%Y-%m-%d %H:%M:%S"), str(data[key])])

    if len(x_list) == 0:
        scene.clear()
        dialog.progressBar.setValue(100)
        iface.messageBar().pushMessage("Info", "No Record available",
                                       level=Qgis.Info)
        return

    step = (x_list[-1] - x_list[0]) / 30
    x_label = []
    last_x = x_list[0] - step
    for i, key in enumerate(data):
        if x_list[i] - last_x >= step:
            x_label.append(key.datetime.strftime("%Y-%m-%d"))
            last_x = x_list[i]
        else:
            x_label.append(" ")

    x = tuple(x_list)
    y = tuple(y_list)

    dialog.progressBar.setValue(80)

    fig, axs = plt.subplots()
    fig.set_figwidth(8)
    fig.set_figheight(4)
    axs.set_title("Time Series Pixel Value")
    axs.plot(x, y, "bo")
    axs.plot(x, y, "k")
    axs.set_xticks(x)
    axs.set_xticklabels(x_label, ha="right", rotation=30, fontsize=7)

    axs.set_ylabel('Pixel Value')
    axs.set_xlabel('Time')

    dialog.progressBar.setValue(90)
    canvas = FigureCanvas(fig)
    scene.addWidget(canvas)

    data_frame = pd.DataFrame(data_table, columns=['ID', 'Record Name', 'Date', 'Pixel Value'])
    table_model = TableModel(data_frame)
    dialog.graphicTableView.setModel(table_model)
    dialog.graphicTableView.resizeColumnsToContents()
    dialog.progressBar.setValue(100)
    return fig, x_list, data_table


def get_reproject_bounds(geometry: MultiPolygon) -> List[float]:
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)

    target = osr.SpatialReference()
    target.ImportFromEPSG(3857)

    transform = osr.CoordinateTransformation(source, target)

    pt_min = ogr.Geometry(ogr.wkbPoint)
    pt_min.FlattenTo2D()
    pt_max = ogr.Geometry(ogr.wkbPoint)
    pt_max.FlattenTo2D()

    pt_min.AddPoint(geometry.bounds[1], geometry.bounds[0])
    pt_max.AddPoint(geometry.bounds[3], geometry.bounds[2])

    pt_min.Transform(transform)
    pt_max.Transform(transform)

    return [pt_min.GetX(), pt_min.GetY(), pt_max.GetX(), pt_max.GetY()]
