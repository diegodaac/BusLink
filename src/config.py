import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key')

class DevelopmentConfig(Config):
    DEBUG = True
    MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
    MYSQL_USER = os.getenv('MYSQL_USER')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
    MYSQL_DB = os.getenv('MYSQL_DB')

config = {
    'development': DevelopmentConfig
}
