import logging

from osgeo import osr, ogr
from qgis._core import QgsProject
from qgis._gui import QgsMapTool
from PyQt5.QtCore import Qt
from qgis.core import Qgis
from shapely.geometry import Polygon
from PyQt5 import QtGui


class RecordMapSelect(QgsMapTool):
    def __init__(self, parent, iface, canvas, geocube_client, on_map_model):
        self.parent = parent
        self.iface = iface
        self.canvas = canvas
        self.geocube_client = geocube_client
        self.on_map_model = on_map_model
        QgsMapTool.__init__(self, self.canvas)

    def canvasReleaseEvent(self, event):
        click_point = event.mapPoint()
        posx = click_point.x()
        posy = click_point.y()
        if event.button() == Qt.RightButton:
            self.iface.messageBar().pushMessage(f'Please use right click in order to select Point on Map',
                                                Qgis.Info, 5)
        elif event.button() == Qt.LeftButton:
            self.iface.messageBar().pushMessage(f'Position: {posx}, {posy}',
                                                Qgis.Info, 5)

            current_crs = QgsProject.instance().crs().authid()
            crs = int(current_crs.split(":")[1])
            source = osr.SpatialReference()
            source.ImportFromEPSG(int(crs))

            target = osr.SpatialReference()
            target.ImportFromEPSG(4326)

            transform = osr.CoordinateTransformation(source, target)
            point = ogr.CreateGeometryFromWkt(f'POINT ({posx} {posy})')

            point.Transform(transform)

            self.parent.positionOnMap.setText(f'Position: {point.GetX()}, {point.GetY()}')
            self.parent.positionOnMap.adjustSize()

            if source.IsGeographic():
                posx = point.GetX()
                posy = point.GetY()
            else:
                posx = point.GetY()
                posy = point.GetX()

            buffer = 0.00001
            polygon = Polygon(
                [[posx - buffer, posy - buffer], [posx + buffer, posy - buffer], [posx + buffer, posy + buffer],
                 [posx - buffer, posy + buffer],
                 [posx - buffer, posy - buffer]])

            logging.info("list_records")
            records = self.geocube_client.list_records(aoi=polygon)

            self.on_map_model.clear()
            for record in records:
                item = QtGui.QStandardItem(record.format())
                self.on_map_model.appendRow(item)

            self.parent.onmapResult.setText('Records found: ' + str(len(records)))
            self.parent.onmapResult.adjustSize()

            # access self.iface object
            self.iface.actionPan().trigger()
            # call show() on parent object (the plugin dialog)
            self.parent.show()
