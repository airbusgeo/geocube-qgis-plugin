import logging

from qgis._core import QgsApplication, QgsProject, QgsRasterLayer, QgsCoordinateReferenceSystem, QgsRectangle
from qgis._gui import QgsMapTool
from PyQt5.QtCore import Qt
from qgis.core import Qgis
from .utils import min_index_from_array, generate_graph, get_reproject_bounds


class TimeSeriesMapSelect(QgsMapTool):
    def __init__(self, parent, iface, canvas, scene, geocube_client, geocube_auth_config_id, geocube_server):
        self.data_table = []
        self.parent = parent
        self.iface = iface
        self.canvas = canvas
        self.geocube_client = geocube_client
        self.geocube_auth_config_id = geocube_auth_config_id
        self.geocube_server = geocube_server
        self.scene = scene
        self.x_list = []
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

            self.parent.xCoord.setPlainText(f'{posx}')
            self.parent.yCoord.setPlainText(f'{posy}')
            self.generate_graph()

            # access self.iface object
            self.iface.actionPan().trigger()
            # call show() on parent object (the plugin dialog)
            self.parent.show()

    def generate_graph(self):
        logging.info("generate graph from mapselect")
        figure, self.x_list, self.data_table = generate_graph(self.parent, self.scene, self.iface, self.geocube_client)
        figure.canvas.mpl_connect('button_press_event', self.onclick)

    def onclick(self, event):
        logging.debug('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
                      ('double' if event.dblclick else 'single', event.button,
                       event.x, event.y, event.xdata, event.ydata))
        x_coord = event.xdata
        min_index = min_index_from_array(self.x_list, x_coord)
        self.parent.graphicTableView.selectRow(min_index)
        record_id = self.data_table[min_index][0]
        record_name = self.data_table[min_index][1]

        instance_name = self.parent.instanceComboBox.currentText()
        variable_name = self.parent.variablesComboBox.currentText()
        instance_id = self.geocube_client.get_instance_id(variable_name=variable_name, instance_name=instance_name)
        logging.info(instance_id)

        layers = QgsProject.instance().mapLayersByName(layerName="graph_layer_view")
        if len(layers) > 0:
            for layer in layers:
                logging.debug("layer already exist")
                layer.setDataSource(
                    dataSource='authcfg=' + self.geocube_auth_config_id + '&type=xyz&url=https://' + self.geocube_server + '/v1/catalog/mosaic/' + instance_id + '/%7Bx%7D/%7By%7D/%7Bz%7D/png?records.ids=' +
                               record_id, baseName="graph_layer_view", provider="wms",
                    options=layer.dataProvider().ProviderOptions())
                logging.debug("layer updated")
                return
        xyz_Layer = QgsRasterLayer(
            'authcfg=' + self.geocube_auth_config_id + '&type=xyz&url=https://' + self.geocube_server + '/v1/catalog/mosaic/' + instance_id + '/%7Bx%7D/%7By%7D/%7Bz%7D/png?records.ids=' +
            record_id,
            "graph_layer_view", 'wms')
        xyz_Layer.setExtent(self.compute_record_rect(record_id=record_id,
                                                     record_name=record_name))
        srs = QgsCoordinateReferenceSystem()
        srs.createFromSrid(srid=3857)
        xyz_Layer.setCrs(srs=srs)
        if xyz_Layer.isValid():
            QgsProject.instance().addMapLayer(xyz_Layer)
            logging.info("layer added")
        else:
            logging.error("failed to add layer")

    def compute_record_rect(self, record_id: str, record_name: str) -> QgsRectangle:
        wkt = self.geocube_client.get_aoi_from_record(record_name=record_name, record_id=record_id)
        bounds = get_reproject_bounds(wkt)
        return QgsRectangle(bounds[0], bounds[1], bounds[2], bounds[3])
