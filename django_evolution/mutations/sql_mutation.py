"""Mutation for executing SQL statements.

Version Added:
    2.2
"""

from __future__ import unicode_literals

import inspect

from django_evolution.errors import CannotSimulate
from django_evolution.mutations.base import BaseMutation
from django_evolution.signature import ProjectSignature


class SQLMutation(BaseMutation):
    """A mutation that executes SQL on the database.

    Unlike most mutations, this one is largely database-dependent. It allows
    arbitrary SQL to be executed. It's recommended that the execution does
    not modify the schema of a table (unless it's highly database-specific with
    no counterpart in Django Evolution), but rather is limited to things like
    populating data.

    SQL statements cannot be optimized. Any scheduled database operations
    prior to the SQL statement will be executed without any further
    optimization. This can lead to longer database evolution times.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.sql_mutation`
        module.
    """

    def __init__(self, tag, sql, update_func=None):
        """Initialize the mutation.

        Args:
            tag (unicode):
                A unique tag identifying this SQL operation.

            sql (unicode):
                The SQL to execute.

            update_func (callable, optional):
                A function to call to simulate updating the database signature.
                This is required for :py:meth:`simulate` to work.
        """
        super(SQLMutation, self).__init__()

        self.tag = tag
        self.sql = sql
        self.update_func = update_func

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [self.tag]

    def simulate(self, simulation):
        """Simulate a mutation for an application.

        This will run the :py:attr:`update_func` provided when instantiating
        the mutation, passing it ``app_label`` and ``project_sig``. It should
        then modify the signature to match what the SQL statement would do.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.CannotSimulate:
                :py:attr:`update_func` was not provided or was not a function.

            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message. This would be run by :py:attr:`update_func`.
        """
        if callable(self.update_func):
            if hasattr(inspect, 'getfullargspec'):
                # Python 3
                argspec = inspect.getfullargspec(self.update_func)
            else:
                # Python 2
                argspec = inspect.getargspec(self.update_func)

            if len(argspec.args) == 1 and argspec.args[0] == 'simulation':
                # New-style simulation function.
                self.update_func(simulation)
                return
            elif len(argspec.args) == 2:
                # Legacy simulation function.
                project_sig = simulation.project_sig

                serialized_sig = project_sig.serialize(sig_version=1)
                self.update_func(simulation.app_label, serialized_sig)
                new_project_sig = ProjectSignature.deserialize(serialized_sig)

                # We have to reconstruct the existing project signature's state
                # based on this.
                app_sig_ids = [
                    app_sig.app_id
                    for app_sig in new_project_sig.app_sigs
                ]

                for app_sig_id in app_sig_ids:
                    project_sig.remove_app_sig(app_sig_id)

                for app_sig in new_project_sig.app_sigs:
                    project_sig.add_app_sig(app_sig)

                return

        raise CannotSimulate(
            'SQLMutations must provide an update_func(simulation) or '
            'legacy update_func(app_label, project_sig) parameter '
            'in order to be simulated.')

    def mutate(self, mutator):
        """Schedule a database mutation on the mutator.

        This will instruct the mutator to execute the SQL for an app.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.

        Raises:
            django_evolution.errors.EvolutionNotImplementedError:
                The configured mutation is not supported on this type of
                database.
        """
        mutator.add_sql(self, self.sql)

    def is_mutable(self, *args, **kwargs):
        """Return whether the mutation can be applied to the database.

        Args:
            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (tuple, unused):
                Unused positional arguments.

        Returns:
            bool:
            ``True``, always.
        """
        return True
