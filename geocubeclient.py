import logging

import geocube
from PyQt5.QtCore import QCoreApplication
from geocube import entities
from shapely import geometry
from shapely.geometry import MultiPolygon
from typing import List, Dict, Union
import datetime


class Record:
    id: str
    name: str
    datetime: datetime
    tags: Dict[str, str]
    aoi_id: str
    aoi: geometry.MultiPolygon

    def __init__(self, name: str, id: str, date: datetime, t: Dict[str, str], aoi_id: str, aoi: geometry.MultiPolygon):
        self.name = name
        self.id = id
        self.datetime = date
        self.tags = t
        self.aoi_id = aoi_id
        self.aoi = aoi

    def format(self) -> str:
        return '{id} - {name} - {date} - {tags}'.format(name=self.name, id=self.id, date=self.datetime, tags=self.tags)


class GeocubeClient:

    def __init__(self, geocube_server: str, geocube_client_apikey: str):
        self.client = geocube.Client(uri=geocube_server, secure=True,
                                     api_key=geocube_client_apikey)
        self.records_aoi = {}

    def list_variables(self) -> List[str]:
        variables = self.client.list_variables()
        variable_names = []
        for variable in variables:
            variable_names.append(variable.name)
        return variable_names

    def list_records(self, name: str = "", tags: Dict[str, str] = None,
                     from_time: datetime = None, to_time: datetime = None,
                     aoi: geometry.MultiPolygon = None, limit: int = 5000, page: int = 0) -> List[Record]:
        records = self.client.list_records(name=name, tags=tags, from_time=from_time, to_time=to_time, aoi=aoi,
                                           limit=limit, page=page, with_aoi=True)
        returned_record = []
        for record in records:
            new_record = Record(name=record.name, id=record.id, date=record.datetime, t=record.tags,
                                aoi_id=record.aoi_id, aoi=record.aoi)
            self.records_aoi[record.id] = new_record
            returned_record.append(new_record)
        return returned_record

    def list_instance_from_variable(self, variable_name: str = "") -> List[str]:
        variables = self.client.list_variables(name=variable_name)
        instances = []
        for variable in variables:
            ins = variable.instances
            for i in ins:
                instances.append(i)
        return instances

    def get_instance_id(self, variable_name: str, instance_name: str) -> str:
        variable = self.client.variable(name=variable_name)
        instance = variable.instance(name=instance_name)
        return instance.instance_id

    def get_aoi_from_record(self, record_id: str, record_name: str) -> Union[MultiPolygon, None]:
        if record_id in self.records_aoi:
            logging.debug("aoi already loaded")
            record = self.records_aoi[record_id]
            return record.aoi
        records = self.client.list_records(page=0, name=record_name, with_aoi=True)
        for record in records:
            if record.id == record_id:
                return record.aoi
        logging.debug("return None")
        return None

    def get_cube_from_tags(self, variable_name: str, variable_instance: str, tags: Dict[str, str] = None,
                           from_time: datetime = None, to_time: datetime = None, crs: str = None,
                           transform: List[float] = None) -> Dict[Record, float]:
        instance = self.client.variable(variable_name).instance(variable_instance)
        params = entities.CubeParams.from_tags(
            crs=crs,
            transform=entities.geo_transform(transform[0], transform[1], transform[2]),
            shape=(1, 1),
            instance=instance,
            tags=tags,
            from_time=from_time,
            to_time=to_time,
        )
        images, records = self.client.get_cube(params=params, verbose=False)
        data = {}
        for i in range(len(images)):
            image = images[i]
            r = records[i]
            current_record = r[0]
            data[Record(name=current_record.name, id=current_record.id, date=current_record.datetime,
                        t=current_record.tags,
                        aoi_id=current_record.aoi_id, aoi=None)] = image[0][0][0]
        return data
