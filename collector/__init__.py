from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy import engine_from_config, Column, Integer, String, DateTime, \
    ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm.collections import column_mapped_collection

from datetime import datetime
import logging

log = logging.getLogger(__name__)

Session = scoped_session(sessionmaker())
Base = declarative_base()

class StatDataType(object):
    BOOLEAN = 'b'
    FLOAT = 'f'
    STRING = 's'
    INTEGER = 'i'

class StatData(Base):
    __tablename__ = 'stat_data'

    TYPE_MAP = {
        bool:  StatDataType.BOOLEAN,
        float: StatDataType.FLOAT,
        str: StatDataType.STRING,
        unicode: StatDataType.STRING,
        int: StatDataType.INTEGER
    }
    
    CASTERS = {
        StatDataType.BOOLEAN: lambda x: bool(int(x)),
        StatDataType.FLOAT: float,
        StatDataType.STRING: str,
        StatDataType.INTEGER: int
    }

    @property
    def casted_value(self):
        return self.CASTERS[self.type](self.value)
    
    @classmethod
    def build(cls, key, value):
        return cls(key=key,
                   value=value,
                   type=cls.TYPE_MAP[type(value)])

    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True)
    key = Column(String, primary_key=True)
    type = Column(String(1), nullable=False)
    value = Column(String, nullable=False)

class Stat(Base):
    __tablename__ = 'stats'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    application = Column(String, nullable=False)
    device_id = Column(String, nullable=False)

    data_map = relationship(
        StatData,
        collection_class=column_mapped_collection(StatData.key), 
        cascade='all, delete-orphan'
    )
    data = association_proxy('data_map', 'casted_value', creator=StatData.build)

@view_config(route_name='collector', renderer='json')
def collector(request):
    data = request.json_body
    
    application = data.get('application')
    device_id = data.get('device_id')

    if not device_id or not  application:
        return {'status': 'error', 'message': 'bad object'}

    del data['device_id']
    del data['application']

    stat = Stat(device_id=device_id, application=application)

    for k in data:
        stat.data[k] = data[k]

    Session.add(stat)
    Session.commit()
    
    return {'status': 'ok'}

def main(global_config, **settings):

    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)

    config = Configurator(settings=settings)
    config.add_route('collector', '/collector')
    config.scan()

    return config.make_wsgi_app()

if __name__ == '__main__':
    serve(main(), host='0.0.0.0')
