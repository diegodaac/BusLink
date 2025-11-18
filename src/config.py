# src/config.py
class Config:
    SECRET_KEY = 'PRUEBA'

class DevelopmentConfig(Config):
    DEBUG = True
    MYSQL_HOST = '127.0.0.1'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = '28040396'
    MYSQL_DB = 'central_autobuses'

config = {
    'development': DevelopmentConfig
}
