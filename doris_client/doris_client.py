import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

from .selectdb.config import WriteOptions
from .selectdb.db_operator import SelectDBBase


class DorisClient:
    def __init__(self, fe_host, fe_query_port, fe_http_port, username, password, db):
        self.fe_host = fe_host
        self.fe_query_port = fe_query_port
        self.fe_http_port = fe_http_port
        self.username = username
        self.password = password
        self.db = db
        self._session = requests.sessions.Session()
        self.db_operator = SelectDBBase(
            self.fe_host,
            int(self.fe_query_port),
            self.db,
            self.username,
            self.password,
            4,
        )

    def query(self, sql):
        return self.db_operator.query(sql)

    def execute(self, sql):
        self.db_operator.execute(sql)

    def query_to_dataframe(self, sql, columns: list):
        return self.db_operator.read_to_df(sql, columns)

    def write_from_df(
        self,
        data_df: pd.DataFrame,
        table_name: str,
        table_model: str,
        table_module_key=None,
        distributed_hash_key=None,
        buckets=None,
        table_properties=None,
        field_mapping: list[tuple] = None,
        repeat_replacement: bool = None,
    ):
        replace_table = repeat_replacement
        if replace_table is None:
            replace_table = False
        elif replace_table:
            self.execute(f"DROP TABLE {table_name}")

        self.db_operator.create_table_from_df(
            replace_table,
            data_df,
            table_name,
            table_model,
            table_module_key,
            distributed_hash_key,
            buckets,
            table_properties,
            field_mapping,
        )
        csv = data_df.to_csv(header=False, index=False)
        self.write(table_name, csv)

    def list_tables(self, database):
        list_tuple = self.db_operator.get_tables(database)
        return [t[0] for t in list_tuple]

    def drop_table(self, db, table_name):
        return self.db_operator.drop_table(f"{db}.{table_name}")

    def create_database(self, database):
        return self.db_operator.create_database(database)

    def get_table_columns(self, db, table_name):
        return self.db_operator.get_table_columns(f"{db}.{table_name}")

    def _build_url(self, database, table):
        url = "http://{host}:{port}/api/{database}/{table}/_stream_load".format(
            host=self.fe_host, port=self.fe_http_port, database=database, table=table
        )
        return url

    def write(self, table_name, data, options: WriteOptions = None):
        write_config = options
        if write_config is None:
            write_config = WriteOptions()
        database = table_name.split(".")[0]
        table = table_name.split(".")[1]
        self._auth = HTTPBasicAuth(self.username, self.password)
        self._session.should_strip_auth = lambda old_url, new_url: False
        resp = self._session.request(
            "PUT",
            url=self._build_url(database, table),
            data=data,  # open('/path/to/your/data.csv', 'rb'),
            headers=write_config.get_options(),
            auth=self._auth,
        )
        import json

        print(resp.text)
        load_status = json.loads(resp.text)["Status"] == "Success"
        if resp.status_code == 200 and resp.reason == "OK" and load_status:
            return True
        else:
            return False
