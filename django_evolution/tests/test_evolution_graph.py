"""Unit tests for django_evolution.utils.graph.EvolutionGraph."""

from __future__ import unicode_literals

from django.db import DEFAULT_DB_ALIAS, connections

from django_evolution.compat.apps import get_app
from django_evolution.models import Evolution, Version
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import (MigrationsTestsMixin,
                                                   TestCase)
from django_evolution.tests.decorators import requires_migrations
from django_evolution.tests.evolutions_app.models import EvolutionsAppTestModel
from django_evolution.tests.evolutions_app2.models import \
    EvolutionsApp2TestModel
from django_evolution.utils.graph import EvolutionGraph
from django_evolution.utils.migrations import (MigrationExecutor,
                                               MigrationList,
                                               MigrationLoader,
                                               record_applied_migrations)

try:
    # Django >= 1.7
    from django.db import migrations
    from django.db.migrations.graph import MigrationGraph
except ImportError:
    # Django < 1.7
    MigrationGraph = None
    migrations = None


class EvolutionGraphTests(MigrationsTestsMixin, TestCase):
    """Unit tests for django_evolution.utils.graph.EvolutionGraph."""

    def test_add_evolutions(self):
        """Testing EvolutionGraph.add_evolutions"""
        app = get_app('django_evolution')

        evolutions = [
            Evolution(app_label='django_evolution',
                      label='my_evolution1'),
            Evolution(app_label='django_evolution',
                      label='my_evolution2'),
        ]

        graph = EvolutionGraph()
        graph.add_evolutions(
            app=app,
            evolutions=evolutions,
            new_models=[
                Evolution,
                Version,
            ],
            extra_state={
                'foo': 'bar',
            })

        graph.finalize()

        nodes = graph.get_ordered()
        self.assertEqual(len(nodes), 6)

        self._check_node(
            nodes[0],
            insert_index=0,
            key='evolution:django_evolution:__first__',
            required_by={
                'create-model:django_evolution:evolution',
            },
            state={
                'anchor': True,
                'app': app,
            })

        self._check_node(
            nodes[1],
            insert_index=1,
            key='create-model:django_evolution:evolution',
            dependencies={
                'evolution:django_evolution:__first__'
            },
            required_by={
                'create-model:django_evolution:version',
            },
            state={
                'app': app,
                'foo': 'bar',
                'model': Evolution,
                'type': graph.NODE_TYPE_CREATE_MODEL,
            })

        self._check_node(
            nodes[2],
            insert_index=2,
            key='create-model:django_evolution:version',
            dependencies={
                'create-model:django_evolution:evolution'
            },
            required_by={
                'evolution:django_evolution:my_evolution1',
            },
            state={
                'app': app,
                'foo': 'bar',
                'model': Version,
                'type': graph.NODE_TYPE_CREATE_MODEL,
            })

        self._check_node(
            nodes[3],
            insert_index=3,
            key='evolution:django_evolution:my_evolution1',
            dependencies={
                'create-model:django_evolution:version'
            },
            required_by={
                'evolution:django_evolution:my_evolution2',
            },
            state={
                'app': app,
                'evolution': evolutions[0],
                'foo': 'bar',
                'type': graph.NODE_TYPE_EVOLUTION,
            })

        self._check_node(
            nodes[4],
            insert_index=4,
            key='evolution:django_evolution:my_evolution2',
            dependencies={
                'evolution:django_evolution:my_evolution1'
            },
            required_by={
                'evolution:django_evolution:__last__',
            },
            state={
                'app': app,
                'evolution': evolutions[1],
                'foo': 'bar',
                'type': graph.NODE_TYPE_EVOLUTION,
            })

        self._check_node(
            nodes[5],
            insert_index=5,
            key='evolution:django_evolution:__last__',
            dependencies={
                'evolution:django_evolution:my_evolution2'
            },
            state={
                'anchor': True,
                'app': app,
            })

    @requires_migrations
    def test_add_migration_plan(self):
        """Testing EvolutionGraph.add_migration_plan"""
        class TestsInitialMigration(migrations.Migration):
            pass

        class TestsAddFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0001_initial'),
            ]

        class OtherInitialMigration(migrations.Migration):
            dependencies = [('tests', '0002_add_field')]

        graph = EvolutionGraph()
        migration_plan = self._add_migrations(
            graph=graph,
            migrations_info=[
                ('tests', '0001_initial', TestsInitialMigration),
                ('tests', '0002_add_field', TestsAddFieldMigration),
                ('other', '0001_initial', OtherInitialMigration),
            ],
            leaf_migration_targets=[('other', '0001_initial')])
        self.assertEqual(len(migration_plan), 3)

        graph.finalize()

        nodes = graph.get_ordered()
        self.assertEqual(len(nodes), 3)

        self._check_node(
            nodes[0],
            insert_index=0,
            key='migration:tests:0001_initial',
            required_by={
                'migration:tests:0002_add_field',
            },
            state={
                'migration_plan_item': migration_plan[0],
                'migration_target': ('tests', '0001_initial'),
                'type': graph.NODE_TYPE_MIGRATION,
            })

        self._check_node(
            nodes[1],
            insert_index=1,
            key='migration:tests:0002_add_field',
            dependencies={
                'migration:tests:0001_initial',
            },
            required_by={
                'migration:other:0001_initial',
            },
            state={
                'migration_plan_item': migration_plan[1],
                'migration_target': ('tests', '0002_add_field'),
                'type': graph.NODE_TYPE_MIGRATION,
            })

        self._check_node(
            nodes[2],
            key='migration:other:0001_initial',
            dependencies={
                'migration:tests:0002_add_field',
            },
            state={
                'migration_plan_item': migration_plan[2],
                'migration_target': ('other', '0001_initial'),
                'type': graph.NODE_TYPE_MIGRATION,
            })

    def test_mark_evolutions_applied(self):
        """Testing EvolutionGraph.mark_evolutions_applied"""
        app_label = 'app_deps_app'
        app = get_app(app_label)

        evolutions = [
            Evolution(app_label=app_label,
                      label='test_evolution'),
        ]

        graph = EvolutionGraph()
        graph.process_migration_deps = False

        graph.add_evolutions(app=app,
                             evolutions=evolutions)
        graph.mark_evolutions_applied(app=get_app('evolutions_app'),
                                      evolution_labels=['first_evolution'])
        graph.mark_evolutions_applied(app=get_app('evolutions_app2'),
                                      evolution_labels=['second_evolution'])
        graph.finalize()

        nodes = graph.get_ordered()
        self.assertEqual(len(nodes), 3)

        self._check_node(
            nodes[0],
            insert_index=0,
            key='evolution:app_deps_app:__first__',
            required_by={
                'evolution:app_deps_app:test_evolution',
            },
            state={
                'anchor': True,
                'app': app,
            })

        self._check_node(
            nodes[1],
            insert_index=1,
            key='evolution:app_deps_app:test_evolution',
            dependencies={
                'evolution:app_deps_app:__first__',
            },
            required_by={
                'evolution:app_deps_app:__last__',
            },
            state={
                'app': app,
                'evolution': evolutions[0],
                'type': graph.NODE_TYPE_EVOLUTION,
            })

        self._check_node(
            nodes[2],
            insert_index=2,
            key='evolution:app_deps_app:__last__',
            dependencies={
                'evolution:app_deps_app:test_evolution',
            },
            state={
                'anchor': True,
                'app': app,
            })

    @requires_migrations
    def test_mark_migrations_applied(self):
        """Testing EvolutionGraph.mark_migrations_applied"""
        class TestsInitialMigration(migrations.Migration):
            pass

        class TestsAddFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0001_initial'),
            ]

        class OtherInitialMigration(migrations.Migration):
            dependencies = [('tests', '0002_add_field')]

        graph = EvolutionGraph()
        migration_plan = self._add_migrations(
            graph=graph,
            migrations_info=[
                ('tests', '0001_initial', TestsInitialMigration),
                ('tests', '0002_add_field', TestsAddFieldMigration),
                ('other', '0001_initial', OtherInitialMigration),
            ],
            leaf_migration_targets=[('other', '0001_initial')],
            mark_applied=[
                ('tests', '0001_initial'),
                ('tests', '0002_add_field'),
            ])
        self.assertEqual(len(migration_plan), 1)

        graph.finalize()

        nodes = graph.get_ordered()
        self.assertEqual(len(nodes), 1)

        self._check_node(
            nodes[0],
            insert_index=0,
            key='migration:other:0001_initial',
            state={
                'migration_plan_item': migration_plan[0],
                'migration_target': ('other', '0001_initial'),
                'type': graph.NODE_TYPE_MIGRATION,
            })

    def test_iter_batches(self):
        """Testing EvolutionGraph.iter_batches"""
        evolutions_app = get_app('evolutions_app')
        evolutions_app2 = get_app('evolutions_app2')
        evolution_deps_app = get_app('evolution_deps_app')

        # evolutions_app
        evolutions1 = [
            Evolution(app_label='evolutions_app',
                      label='first_evolution'),
            Evolution(app_label='evolutions_app',
                      label='second_evolution'),
        ]
        models1 = [EvolutionsAppTestModel]

        # evolutions_app2
        evolutions2 = [
            Evolution(app_label='evolutions_app2',
                      label='first_evolution'),
            Evolution(app_label='evolutions_app2',
                      label='second_evolution'),
        ]
        models2 = [EvolutionsApp2TestModel]

        # evolution_deps_app
        evolutions3 = [
            Evolution(app_label='evolution_deps_app',
                      label='test_evolution'),
        ]

        graph = EvolutionGraph()
        graph.process_migration_deps = supports_migrations

        if supports_migrations:
            connection = connections[DEFAULT_DB_ALIAS]
            migration_executor = MigrationExecutor(connection=connection)
            migration_loader = MigrationLoader(connection=connection)

            migration_plan = migration_executor.migration_plan([
                ('migrations_app', '0002_add_field'),
                ('migrations_app2', '0002_add_field'),
            ])
            migration_loader.build_graph()

            graph.add_migration_plan(migration_plan=migration_plan,
                                     migration_graph=migration_loader.graph)
        else:
            migration_plan = None

        graph.add_evolutions(app=evolutions_app,
                             evolutions=evolutions1,
                             new_models=models1)
        graph.add_evolutions(app=evolutions_app2,
                             evolutions=evolutions2,
                             new_models=models2)
        graph.add_evolutions(app=evolution_deps_app,
                             evolutions=evolutions3)
        graph.finalize()

        all_batches = list(graph.iter_batches())

        if supports_migrations:
            self.assertEqual(len(all_batches), 6)
            excluded_migration_deps = set()
        else:
            self.assertEqual(len(all_batches), 4)
            excluded_migration_deps = {
                'migration:migrations_app:0001_initial',
                'migration:migrations_app2:0002_add_field',
            }

        # Turn this back into a generator so we can more easily check these
        # batches with/without migrations, depending on the version of Django
        # the tests are being run on.
        batches = iter(all_batches)

        # Check the first migrations batch.
        if supports_migrations:
            node_type, nodes = next(batches)
            self.assertEqual(node_type, EvolutionGraph.NODE_TYPE_MIGRATION)
            self.assertEqual(len(nodes), 3)
            self._check_node(
                nodes[0],
                key='migration:migrations_app:0001_initial',
                required_by={
                    'evolution:evolution_deps_app:test_evolution',
                    'migration:migrations_app:0002_add_field',
                },
                state={
                    'migration_plan_item': migration_plan[0],
                    'migration_target': ('migrations_app', '0001_initial'),
                    'type': EvolutionGraph.NODE_TYPE_MIGRATION,
                })
            self._check_node(
                nodes[1],
                key='migration:migrations_app:0002_add_field',
                dependencies={
                    'migration:migrations_app:0001_initial',
                },
                required_by={
                    'migration:migrations_app2:0001_initial',
                },
                state={
                    'migration_plan_item': migration_plan[1],
                    'migration_target': ('migrations_app', '0002_add_field'),
                    'type': EvolutionGraph.NODE_TYPE_MIGRATION,
                })
            self._check_node(
                nodes[2],
                key='migration:migrations_app2:0001_initial',
                dependencies={
                    'migration:migrations_app:0002_add_field',
                },
                required_by={
                    'migration:migrations_app2:0002_add_field',
                },
                state={
                    'migration_plan_item': migration_plan[2],
                    'migration_target': ('migrations_app2', '0001_initial'),
                    'type': EvolutionGraph.NODE_TYPE_MIGRATION,
                })

        # Check the first create-model batch.
        node_type, nodes = next(batches)
        self.assertEqual(node_type, EvolutionGraph.NODE_TYPE_CREATE_MODEL)
        self.assertEqual(len(nodes), 1)
        self._check_node(
            nodes[0],
            key='create-model:evolutions_app:evolutionsapptestmodel',
            dependencies={
                'evolution:evolutions_app:__first__',
            },
            required_by={
                'evolution:evolutions_app:first_evolution',
            },
            state={
                'app': evolutions_app,
                'model': EvolutionsAppTestModel,
                'type': EvolutionGraph.NODE_TYPE_CREATE_MODEL,
            })

        # Check the first evolution batch.
        node_type, nodes = next(batches)
        self.assertEqual(node_type, EvolutionGraph.NODE_TYPE_EVOLUTION)
        self.assertEqual(len(nodes), 3)
        self._check_node(
            nodes[0],
            key='evolution:evolutions_app:first_evolution',
            dependencies={
                'create-model:evolutions_app:evolutionsapptestmodel',
            },
            required_by={
                'evolution:evolution_deps_app:test_evolution',
                'evolution:evolutions_app:second_evolution',
            },
            state={
                'app': evolutions_app,
                'evolution': evolutions1[0],
                'type': EvolutionGraph.NODE_TYPE_EVOLUTION,
            })
        self._check_node(
            nodes[1],
            key='evolution:evolutions_app:second_evolution',
            dependencies={
                'evolution:evolutions_app:first_evolution',
            },
            required_by={
                'evolution:evolutions_app:__last__',
            },
            state={
                'app': evolutions_app,
                'evolution': evolutions1[1],
                'type': EvolutionGraph.NODE_TYPE_EVOLUTION,
            })
        self._check_node(
            nodes[2],
            key='evolution:evolution_deps_app:test_evolution',
            dependencies={
                'evolution:evolution_deps_app:__first__',
                'evolution:evolutions_app:first_evolution',
                'evolution:evolutions_app:__last__',
                'migration:migrations_app:0001_initial',
            } - excluded_migration_deps,
            required_by={
                'evolution:evolution_deps_app:__last__',
                'evolution:evolutions_app2:__first__',
                'evolution:evolutions_app2:second_evolution',
                'migration:migrations_app2:0002_add_field',
            } - excluded_migration_deps,
            state={
                'app': evolution_deps_app,
                'evolution': evolutions3[0],
                'type': EvolutionGraph.NODE_TYPE_EVOLUTION,
            })

        if supports_migrations:
            # Check the second migration batch.
            node_type, nodes = next(batches)
            self.assertEqual(node_type, EvolutionGraph.NODE_TYPE_MIGRATION)
            self.assertEqual(len(nodes), 1)
            self._check_node(
                nodes[0],
                key='migration:migrations_app2:0002_add_field',
                dependencies={
                    'evolution:evolution_deps_app:test_evolution',
                    'migration:migrations_app2:0001_initial',
                },
                state={
                    'migration_plan_item': migration_plan[3],
                    'migration_target': ('migrations_app2', '0002_add_field'),
                    'type': EvolutionGraph.NODE_TYPE_MIGRATION,
                })

        # Check the second create-model batch.
        node_type, nodes = next(batches)
        self.assertEqual(node_type, EvolutionGraph.NODE_TYPE_CREATE_MODEL)
        self.assertEqual(len(nodes), 1)
        self._check_node(
            nodes[0],
            key='create-model:evolutions_app2:evolutionsapp2testmodel',
            dependencies={
                'evolution:evolutions_app2:__first__',
            },
            required_by={
                'evolution:evolutions_app2:first_evolution',
            },
            state={
                'app': evolutions_app2,
                'model': EvolutionsApp2TestModel,
                'type': EvolutionGraph.NODE_TYPE_CREATE_MODEL,
            })

        # Check the second evolution batch.
        node_type, nodes = next(batches)
        self.assertEqual(node_type, EvolutionGraph.NODE_TYPE_EVOLUTION)
        self.assertEqual(len(nodes), 2)
        self._check_node(
            nodes[0],
            key='evolution:evolutions_app2:first_evolution',
            dependencies={
                'create-model:evolutions_app2:evolutionsapp2testmodel',
            },
            required_by={
                'evolution:evolutions_app2:second_evolution',
            },
            state={
                'app': evolutions_app2,
                'evolution': evolutions2[0],
                'type': EvolutionGraph.NODE_TYPE_EVOLUTION,
            })
        self._check_node(
            nodes[1],
            key='evolution:evolutions_app2:second_evolution',
            dependencies={
                'evolution:evolution_deps_app:test_evolution',
                'evolution:evolutions_app2:first_evolution',
            },
            required_by={
                'evolution:evolutions_app2:__last__',
            },
            state={
                'app': evolutions_app2,
                'evolution': evolutions2[1],
                'type': EvolutionGraph.NODE_TYPE_EVOLUTION,
            })

    def _add_migrations(self, graph, migrations_info, leaf_migration_targets,
                        mark_applied=[]):
        """Add migrations to a graph.

        This is a utility for simplifying the additions of a list of
        migrations to a graph, handling the creation of the Django migration
        objects, the formulation of a migration plan, and the recording of
        applied migrations.

        Args:
            graph (django_evolution.utils.graph.EvolutionGraph):
                The graph to add migrations to.

            migrations_info (list of tuple):
                The list of info on migrations to add. Each tuple contains:

                1. The app label
                2. The migration name
                3. The migration class

            leaf_migration_targets (list of tuple):
                The list of final migration targets to migrate to.

            mark_applied (list of tuple, optional):
                The list of migration targets to mark as applied.

        Returns:
            list of tuple:
            The migration plan generated from the migrations.
        """
        migration_list = MigrationList()

        for app_label, name, migration_cls in migrations_info:
            migration_list.add_migration_info(
                app_label=app_label,
                name=name,
                migration=migration_cls(name, app_label))

        connection = connections[DEFAULT_DB_ALIAS]

        if mark_applied:
            mark_applied_list = MigrationList()
            mark_applied_list.add_migration_targets(mark_applied)

            record_applied_migrations(connection, mark_applied_list)
        else:
            mark_applied_list = None

        migration_executor = MigrationExecutor(
            connection=connection,
            custom_migrations=migration_list)
        migration_loader = MigrationLoader(
            connection=connection,
            custom_migrations=migration_list)

        migration_plan = \
            migration_executor.migration_plan(leaf_migration_targets)
        migration_loader.build_graph()

        graph.add_migration_plan(migration_plan=migration_plan,
                                 migration_graph=migration_loader.graph)

        if mark_applied_list:
            graph.mark_migrations_applied(mark_applied_list)

        return migration_plan

    def _check_node(self, node, key, insert_index=None, dependencies=set(),
                    required_by=set(), state={}):
        """Check a graph node for validity.

        This will assert if any of the provided arguments don't match the
        node.

        Args:
            node (django_evolution.utils.graph.Node):
                The graph node to check.

            key (unicode):
                The expected node key.

            insert_index (int, optional):
                The expected insert index. If not provided, this won't be
                checked.

            dependencies (set, optional):
                The node keys expected as dependencies.

            required_by (set, optional):
                The node keys expected to require this node.

            state (dict, optional):
                The expected state of the node.

        Raises:
            AssertionError:
                The node did not match the expected arguments.
        """
        self.assertEqual(node.key, key)
        self.assertEqual(node.state, state)
        self.assertEqual({_node.key for _node in node.dependencies},
                         dependencies)
        self.assertEqual({_node.key for _node in node.required_by},
                         required_by)

        if insert_index is not None:
            self.assertEqual(node.insert_index, insert_index)
