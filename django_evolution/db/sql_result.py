class SQLResult(object):
    """Represents one or more SQL statements.

    This is returned by functions generating SQL statements. It can store
    the main SQL statements to execute, or SQL statements to be executed before
    or after the main statements.

    SQLResults can easily be added together or converted into a flat list of
    SQL statements to execute.
    """
    def __init__(self, sql=None, pre_sql=None, post_sql=None):
        self.sql = sql or []
        self.pre_sql = pre_sql or []
        self.post_sql = post_sql or []

    def add(self, sql_or_result):
        """Adds a list of SQL statements or an SQLResult.

        If an SQLResult is passed, its ``pre_sql``, ``sql``, and ``post_sql``
        lists will be added to this one.

        If a list of SQL statements is passed, it will be added to this
        SQLResult's sql list.
        """
        if isinstance(sql_or_result, SQLResult):
            self.pre_sql += sql_or_result.pre_sql
            self.sql += sql_or_result.sql
            self.post_sql += sql_or_result.post_sql
        else:
            self.sql += sql_or_result

    def add_pre_sql(self, sql_or_result):
        """Adds a list of SQL statements or an SQLResult to ``pre_sql`.

        If an SQLResult is passed, it will be converted into a list of SQL
        statements.
        """
        self.pre_sql += self.normalize_sql(sql_or_result)

    def add_sql(self, sql_or_result):
        """Adds a list of SQL statements or an SQLResult to ``sql``.

        If an SQLResult is passed, it will be converted into a list of SQL
        statements.
        """
        self.sql += self.normalize_sql(sql_or_result)

    def add_post_sql(self, sql_or_result):
        """Adds a list of SQL statements or an SQLResult to ``post_sql``.

        If an SQLResult is passed, it will be converted into a list of SQL
        statements.
        """
        self.post_sql += self.normalize_sql(sql_or_result)

    def normalize_sql(self, sql_or_result):
        """Normalizes a list of SQL statements or an SQLResult into a list.

        If a list of SQL statements is provided, it will be returned. If
        an SQLResult is provided, it will be converted into a list of SQL
        statements and returned.
        """
        if isinstance(sql_or_result, SQLResult):
            return sql_or_result.to_sql()
        else:
            return sql_or_result or []

    def to_sql(self):
        """Flattens the SQLResult into a list of SQL statements."""
        return self.pre_sql + self.sql + self.post_sql

    def __repr__(self):
        return ('<SQLResult: pre_sql=%r, sql=%r, post_sql=%r>'
                % (self.pre_sql, self.sql, self.post_sql))


class AlterTableSQLResult(SQLResult):
    """Represents one or more SQL statements or Alter Table rules.

    This is returned by functions generating SQL statements. It can store
    the main SQL statements to execute, or SQL statements to be executed before
    or after the main statements.

    SQLResults can easily be added together or converted into a flat list of
    SQL statements to execute.
    """
    def __init__(self, evolver, model, alter_table=None, *args, **kwargs):
        super(AlterTableSQLResult, self).__init__(*args, **kwargs)
        self.evolver = evolver
        self.model = model
        self.alter_table = alter_table or []

    def add(self, sql_result):
        """Adds a list of SQL statements or an SQLResult.

        If an SQLResult is passed, its ``pre_sql``, ``sql``, and ``post_sql``
        lists will be added to this one.

        If an AlterTableSQLResult is passed, its ``alter_table`` lists will
        also be added to this one.

        If a list of SQL statements is passed, it will be added to this
        SQLResult's sql list.
        """
        super(AlterTableSQLResult, self).add(sql_result)

        if isinstance(sql_result, AlterTableSQLResult):
            self.alter_table += sql_result.alter_table

    def add_alter_table(self, alter_table):
        """Adds a list of Alter Table rules to ``alter_table``."""
        self.alter_table += alter_table

    def to_sql(self):
        """Flattens the AlterTableSQLResult into a list of SQL statements.

        Any ``alter_table`` entries will be collapsed together into
        ALTER TABLE statements.
        """
        sql = []
        sql += self.pre_sql
        sql += self.sql

        if self.alter_table:
            qn = self.evolver.connection.ops.quote_name
            quoted_table_name = qn(self.model._meta.db_table)

            for item in self.alter_table:
                alter_table_attrs = []
                op = item.get('op', 'sql')

                if op == 'sql':
                    alter_table_attrs.append(item['sql'])
                else:
                    alter_table_attrs.append(op)

                    if 'column' in item:
                        alter_table_attrs.append(qn(item['column']))

                    if op == 'MODIFY COLUMN' and 'db_type' in item:
                        alter_table_attrs.append(item['db_type'])

                    if 'params' in item:
                        alter_table_attrs.extend(item['params'])

                sql.append('ALTER TABLE %s %s;'
                           % (quoted_table_name,
                              ' '.join(alter_table_attrs)))

        sql += self.post_sql

        return sql

    def __repr__(self):
        return ('<AlterTableSQLResult: pre_sql=%r, sql=%r, post_sql=%r,'
                ' alter_table=%r>'
                % (self.pre_sql, self.sql, self.post_sql, self.alter_table))
