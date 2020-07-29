"""Database state tracking for in-progress evolutions."""

from __future__ import unicode_literals

from copy import deepcopy

from django.db import connections

from django_evolution.compat import six
from django_evolution.compat.db import convert_table_name
from django_evolution.db import EvolutionOperationsMulti
from django_evolution.errors import DatabaseStateError


class IndexState(object):
    """An index recorded in the database state."""

    def __init__(self, name, columns, unique=False):
        """Initialize the index state.

        Args:
            name (unicode):
                The name of the index.

            columns (list of unicode):
                A list of columns that the index is comprised of.

            unique (bool, optional):
                Whether this is a unique index.
        """
        assert name
        assert columns

        self.name = name
        self.columns = columns
        self.unique = unique

    def __eq__(self, other_state):
        """Return whether two index states are equal.

        Args:
            other_state (IndexState):
                The other index state to compare to.

        Returns:
            bool:
            ``True`` if the two index states are equal. ``False`` if they
            are not.
        """
        return (self.name == other_state.name and
                self.columns == other_state.columns and
                self.unique == other_state.unique)

    def __hash__(self):
        """Return a hash representation of the index.

        Returns:
            int:
            The hash representation.
        """
        return hash(repr(self))

    def __repr__(self):
        """Return a string representation of the index state.

        Returns:
            unicode:
            A string representation of the index.
        """
        return '<IndexState(name=%r, columns=%r, unique=%r)>' % (
            self.name, self.columns, self.unique)


class DatabaseState(object):
    """Tracks some useful state in the database.

    This primarily tracks indexes associated with tables, allowing them to be
    scanned from the database, explicitly added, removed, or cleared.
    """

    def __init__(self, db_name, scan=True):
        """Initialize the state.

        Args:
            db_name (unicode):
                The name of the database.

            scan (bool, optional):
                Whether to automatically scan state from the database during
                initialization. By default, information is scanned.
        """
        connection = connections[db_name]

        self.db_name = db_name
        self._tables = {}
        self._norm_table_name = \
            lambda name: convert_table_name(connection, name)

        if scan:
            self.rescan_tables()

    def clone(self):
        """Clone the database state.

        Returns:
            DatabaseState:
            The cloned copy of the state.
        """
        cloned_sig = DatabaseState(db_name=self.db_name, scan=False)
        cloned_sig._tables = deepcopy(self._tables)

        return cloned_sig

    def add_table(self, table_name):
        """Add a table to track.

        This will add an empty entry for the table to the state.

        Args:
            table_name (unicode):
                The name of the table.
        """
        self._tables[self._norm_table_name(table_name)] = {
            'indexes': {},
        }

    def has_table(self, table_name):
        """Return whether a table is being tracked.

        This does not necessarily mean that the table exists in the database.
        Rather, state for the table is being tracked.

        Args:
            table_name (unicode):
                The name of the table to look up.

        Returns:
            bool:
            ``True`` if the table is being tracked. ``False`` if it is not.
        """
        return self._norm_table_name(table_name) in self._tables

    def has_model(self, model):
        """Return whether a database model is installed in the database.

        Args:
            model (type):
                The model class.

        Returns:
            bool:
            ``True`` if the model has an accompanying table in the database.
            ``False`` if it does not.
        """
        meta = model._meta

        return (self.has_table(meta.db_table) or
                (meta.auto_created and
                 self.has_table(meta.auto_created._meta.db_table)))

    def add_index(self, table_name, index_name, columns, unique=False):
        """Add a table's index to the database state.

        This index can be used for later lookup during the evolution process.
        It won't otherwise be preserved, though the resulting indexes are
        expected to match the result in the database.

        This requires the table to be tracked first.

        Args:
            table_name (unicode):
                The name of the table.

            index_name (unicode):
                The name of the index.

            columns (list of unicode):
                A list of column names the index is comprised of.

            unique (bool, optional):
                Whether this is a unique index.

        Raises:
            django_evolution.errors.DatabaseStateError:
                There was an issue adding this index. Details are in the
                exception's message.
        """
        assert index_name

        table_name = self._norm_table_name(table_name)

        try:
            indexes = self._tables[table_name]['indexes']
        except KeyError:
            raise DatabaseStateError(
                'Unable to add index "%s" to table "%s". The table is not '
                'being tracked in the database state.'
                % (index_name, table_name))

        existing_index = self.get_index(table_name=table_name,
                                        index_name=index_name)

        if existing_index:
            raise DatabaseStateError(
                'Unable to add index "%s" to table "%s". This index already '
                'exists.'
                % (index_name, table_name))

        indexes[index_name] = IndexState(name=index_name,
                                         columns=columns,
                                         unique=unique)

    def remove_index(self, table_name, index_name, unique=False):
        """Remove an index from the database state.

        This index will no longer be found during lookups when generating
        evolution SQL, even if it exists in the database.

        This requires the table to be tracked first and for the index to
        both exist and match the ``unique`` flag.

        Args:
            table_name (unicode):
                The name of the table.

            index_name (unicode):
                The name of the index.

            unique (bool, optional):
                Whether this is a unique index.

        Raises:
            django_evolution.errors.DatabaseStateError:
                There was an issue removing this index. Details are in the
                exception's message.
        """
        table_name = self._norm_table_name(table_name)

        try:
            indexes = self._tables[table_name]['indexes']
        except KeyError:
            raise DatabaseStateError(
                'Unable to remove index "%s" from table "%s". The table is '
                'not being tracked in the database state.'
                % (index_name, table_name))

        try:
            existing_index = indexes[index_name]
        except KeyError:
            raise DatabaseStateError(
                'Unable to remove index "%s" from table "%s". The index '
                'could not be found.'
                % (index_name, table_name))

        if unique != existing_index.unique:
            raise DatabaseStateError(
                'Unable to remove index "%s" from table "%s". The specified '
                'index type (unique=%r) does not match the existing type '
                '(unique=%r).'
                % (index_name, table_name, unique, existing_index.unique))

        del indexes[index_name]

    def get_index(self, table_name, index_name):
        """Return the index state for a given name.

        Args:
            table_name (unicode):
                The name of the table.

            index_name (unicode):
                The name of the index.

        Returns:
            IndexState:
            The state for the index, if found. ``None`` if the index could not
            be found.
        """
        table_name = self._norm_table_name(table_name)

        try:
            return self._tables[table_name]['indexes'][index_name]
        except KeyError:
            return None

    def find_index(self, table_name, columns, unique=False):
        """Find and return an index matching the given columns and flags.

        Args:
            table_name (unicode):
                The name of the table.

            columns (list of unicode):
                The list of columns the index is comprised of.

            unique (bool, optional):
                Whether this is a unique index.

        Returns:
            IndexState:
            The state for the index, if found. ``None`` if an index matching
            the criteria could not be found.
        """
        table_name = self._norm_table_name(table_name)

        for index_state in self.iter_indexes(table_name):
            if (index_state.columns == columns and
                index_state.unique == unique):
                return index_state

        return None

    def clear_indexes(self, table_name):
        """Clear all recorded indexes for a table.

        Args:
            table_name (unicode):
                The name of the table.
        """
        table_name = self._norm_table_name(table_name)

        try:
            self._tables[table_name]['indexes'].clear()
        except KeyError:
            pass

    def iter_indexes(self, table_name):
        """Iterate through all indexes for a table.

        Args:
            table_name (unicode):
                The name of the table.

        Yields:
            IndexState:
            An index in the table.
        """
        table_name = self._norm_table_name(table_name)

        try:
            indexes = self._tables[table_name]['indexes']
        except KeyError:
            return

        for index_state in six.itervalues(indexes):
            yield index_state

    def rescan_tables(self):
        """Rescan the list of tables from the database.

        This will look up all tables found in the database, along with
        information (such as indexes) on those tables.

        Existing information on the tables will be flushed.
        """
        evolver = EvolutionOperationsMulti(self.db_name).get_evolver()
        connection = evolver.connection
        introspection = connection.introspection
        cursor = connection.cursor()

        for table_name in introspection.get_table_list(cursor):
            # NOTE: The table names are already normalized, so there's no
            #       need to normalize them again.
            if hasattr(table_name, 'name'):
                # In Django >= 1.7, we get back TableInfo namedtuples,
                # which have 'name' and 'type' keys. We don't care about
                # anything but 'name'.
                table_name = table_name.name

            if self.has_table(table_name):
                self.clear_indexes(table_name)
            else:
                self.add_table(table_name)

            indexes = evolver.get_indexes_for_table(table_name)

            for index_name, index_info in six.iteritems(indexes):
                self.add_index(table_name=table_name,
                               index_name=index_name,
                               columns=index_info['columns'],
                               unique=index_info['unique'])
