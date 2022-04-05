# Each database in here corresponds to one set up in docker-compose.yaml.

import os


mysql_db_storage_engine = os.environ.get('DATABASE_MYSQL_STORAGE_ENGINE',
                                         'INNODB')
mysql_init_command = 'SET default_storage_engine=%s' % mysql_db_storage_engine


TEST_DATABASES = {
    # MySQL
    'mysql56': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 8700,
        'NAME': 'test',
        'USER': 'root',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
        'OPTIONS': {
            'init_command': mysql_init_command,
        },
    },
    'mysql57': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 8701,
        'NAME': 'test',
        'USER': 'root',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
        'OPTIONS': {
            'init_command': mysql_init_command,
        },
    },
    'mysql8': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 8702,
        'NAME': 'test',
        'USER': 'root',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
        'OPTIONS': {
            'init_command': mysql_init_command,
        },
    },

    # MariaDB
    'mariadb': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 8720,
        'NAME': 'test',
        'USER': 'root',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
        'OPTIONS': {
            'init_command': mysql_init_command,
        },
    },

    # Postgres
    'postgres11.8': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': '127.0.0.1',
        'PORT': 8730,
        'NAME': 'test',
        'USER': 'postgres',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
    },
    'postgres12': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': '127.0.0.1',
        'PORT': 8731,
        'NAME': 'test',
        'USER': 'postgres',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
    },
    'postgres13': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': '127.0.0.1',
        'PORT': 8732,
        'NAME': 'test',
        'USER': 'postgres',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
    },
    'postgres14': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': '127.0.0.1',
        'PORT': 8733,
        'NAME': 'test',
        'USER': 'postgres',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
    },
    'postgres15': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': '127.0.0.1',
        'PORT': 8734,
        'NAME': 'test',
        'USER': 'postgres',
        'PASSWORD': '8jAHSDAIUyo278jkaSF871',
    },
}


# Optionally import any local test databases.
try:
    from local_test_db_settings import TEST_DATABASES as NEW_TEST_DATABASES

    TEST_DATABASES.update(NEW_TEST_DATABASES)
except ImportError:
    pass
