"""Dependency graphs for tracking and ordering evolutions and migrations.

Version Added:
    2.1
"""

from __future__ import unicode_literals

from django_evolution.compat import six
from django_evolution.compat.models import get_model_name
from django_evolution.models import Evolution
from django_evolution.support import supports_migrations
from django_evolution.utils.apps import get_app_label
from django_evolution.utils.evolutions import (get_evolution_app_dependencies,
                                               get_evolution_dependencies)
from django_evolution.utils.migrations import Migration


class NodeNotFoundError(Exception):
    """A requested node could not be found.

    Version Added:
        2.1
    """

    def __init__(self, key):
        """Initialize the error.

        Args:
            key (unicode):
                The key corresponding to the missing node.
        """
        super(NodeNotFoundError, self).__init__(
            'A graph node with key "%s" was not found.'
            % key)


class Node(object):
    """A node in a graph.

    Each node is associated with a key, and tracks caller-provided state,
    dependency relations (in both directions), and an insertion order (for
    loose sorting).

    Version Added:
        2.1

    Attributes:
        dependencies (set of Node):
            Any other nodes that this node depends on.

        insert_index (int):
            An index defining when this was added to the graph, relative to
            other nodes.

        key (unicode):
            The key identifying this node.

        required_by (set of Node):
            Any other nodes that have this node as a dependency.

        state (dict):
            Tracked state provided by the caller.
    """

    def __init__(self, key, insert_index, state):
        """Initialize the node.

        Args:
            key (unicode):
                The key identifying this node.

            insert_index (int):
                An index defining when this was added to the graph, relative to
                other nodes.

            state (dict):
                Tracked state provided by the caller.
        """
        self.key = key
        self.insert_index = insert_index
        self.dependencies = set()
        self.required_by = set()
        self.state = state

    def __hash__(self):
        """Return a hash of this node.

        The hash will be based on the key.

        Returns:
            int:
            The hash for this node.
        """
        return hash(self.key)

    def __repr__(self):
        """Return a string representation of this node.

        Returns:
            unicode:
            The string representation.
        """
        return '<Node: %s>' % self.key


class DependencyGraph(object):
    """A graph tracking dependencies between nodes.

    This is used to model relations between objects, indicating which nodes
    require which, or are required by others, and then providing a sorted
    order based on those relations.

    Dependencies can be added at any time, and are only applied once the graph
    is finalized. This allows nodes to be added after a dependency referring
    to them is added.

    Version Added:
        2.1
    """

    def __init__(self):
        """Initialize the graph."""
        self._finalized = False
        self._nodes = {}
        self._pending_deps = set()

    def add_node(self, key, state={}):
        """Add a node to the graph.

        A node can only be added if the graph has not been finalized and if
        the key has not already been recorded.

        Args:
            key (unicode):
                The key uniquely identifying this node.

            state (dict, optional):
                State to add to the node.

        Returns:
            Node:
            The resulting node.
        """
        assert not self._finalized
        assert key not in self._nodes, \
            '"%s" is already a registered node' % key

        node = Node(key=key,
                    state=state,
                    insert_index=len(self._nodes))
        self._nodes[key] = node

        return node

    def add_dependency(self, node_key, dep_node_key):
        """Add a dependency between two nodes.

        This will be recorded as a pending dependency and later applied to
        the nodes when calling :py:meth:`finalize`.

        Args:
            node_key (unicode):
                The key of the node that depends on another node.

            dep_node_key (unicode):
                The key of the node that ``node_key`` depends on.
        """
        assert not self._finalized
        assert isinstance(node_key, six.text_type)
        assert isinstance(dep_node_key, six.text_type)

        self._pending_deps.add((node_key, dep_node_key))

    def remove_dependencies(self, node_keys):
        """Remove any pending dependencies referencing one or more keys.

        Args:
            node_keys (set):
                A set of node keys that should be removed from pending
                dependencies.
        """
        assert not self._finalized

        if not isinstance(node_keys, set):
            node_keys = set(node_keys)

        self._pending_deps -= set(
            dep
            for dep in self._pending_deps
            if dep[0] in node_keys or dep[1] in node_keys
        )

    def finalize(self):
        """Finalize the graph.

        This will apply any dependencies and then mark the graph as finalized.
        At this point, orders can be computed, but no new nodes or dependencies
        can be added.
        """
        assert not self._finalized

        for node_key, dep_node_key in self._pending_deps:
            assert node_key in self._nodes, (
                '"%s" was not found (requires dependency "%s")'
                % (node_key, dep_node_key))
            assert dep_node_key in self._nodes, (
                '"%s" was not found (required by "%s")'
                % (dep_node_key, node_key))

            node = self._nodes[node_key]
            dep_node = self._nodes[dep_node_key]

            node.dependencies.add(dep_node)
            dep_node.required_by.add(node)

        self._pending_deps = []
        self._finalized = True

    def get_node(self, key):
        """Return a node with a corresponding key.

        Args:
            key (unicode):
                The key associated with the node.

        Returns:
            Node:
            The resulting node.

        Raises:
            NodeNotFoundError:
                The node could not be found.
        """
        try:
            return self._nodes[key]
        except KeyError:
            raise NodeNotFoundError(key)

    def get_leaf_nodes(self):
        """Return all leaf nodes on the graph.

        Leaf nodes are nodes that nothing depends on. These are generally the
        last evolutions/migrations in any branch of the tree to apply.

        Returns:
            list of Node:
            The list of leaf nodes, sorted by their insertion index.
        """
        assert self._finalized

        return sorted(
            [
                node
                for node in six.itervalues(self._nodes)
                if not node.required_by
            ],
            key=lambda node: node.insert_index)

    def get_ordered(self):
        """Return all nodes in dependency order.

        This will perform a topological sort on the graph, returning nodes in
        the order they should be processed in.

        The graph must be finalized before this is called.

        Returns:
            list of Node:
            The list of ndoes, in dependency order.
        """
        assert self._finalized

        result = []
        result_set = set()

        # Loop through each leaf node, walking up the tree to find any
        # dependencies to add to the stack.
        #
        # As the dependency tree can be quite large, we're tracking this in
        # a stack instead of recursing.
        #
        # We process each leaf node individually, with its own stack. The
        # results from each round of processing are combined into a single
        # list.
        #
        # We're using the same general algorithm/approach as Django's
        # MigrationGraph, for compatibility.
        for leaf_node in self.get_leaf_nodes():
            stack = [leaf_node]
            visited = set()
            processed = set()

            while stack:
                node = stack.pop()

                if node not in visited:
                    # We haven't fully completed this branch of the tree yet.
                    # Figure out what we need to do with this node.
                    if node in processed:
                        # We've already popped this node in the stack before
                        # and went through its dependencies. We're now ready to
                        # add it to the result, if it's not already there.
                        visited.add(node)

                        if node not in result_set:
                            result.append(node)
                            result_set.add(node)
                    else:
                        # Add this node back to the stack, and then its
                        # dependencies. We'll be processing the dependencies
                        # next and then working our way back to this node.
                        #
                        # We'll mark that we've processed this, so we don't
                        # re-scan the dependencies again.
                        stack.append(node)
                        stack += sorted(node.dependencies,
                                        key=lambda dep: dep.insert_index,
                                        reverse=True)

                        processed.add(node)

        return result


class EvolutionGraph(DependencyGraph):
    """A graph tracking dependencies between migrations and evolutions.

    This is used to model the relationships between all configured migrations
    and evolutions, and to generate batches of consecutive migrations or
    evolutions that can be applied at once.

    Dependencies can be added at any time, and are only applied once the graph
    is finalized. This allows nodes to be added after a dependency referring
    to them is added.

    Version Added:
        2.1
    """

    #: An anchor node.
    #:
    #: These are internal, and are used for clustered dependency management.
    NODE_TYPE_ANCHOR = 'anchor'

    #: A node that results in model creation.
    NODE_TYPE_CREATE_MODEL = 'create-model'

    #: A node that results in applying a single evolution.
    NODE_TYPE_EVOLUTION = 'evolution'

    #: A node that results in applying a single migration.
    NODE_TYPE_MIGRATION = 'migration'

    def __init__(self, *args, **kwargs):
        """Initialize the graph.

        Args:
            *args (tuple):
                Positional arguments for the parent.

            **kwargs (dict):
                Keyword arguments for the parent.
        """
        super(EvolutionGraph, self).__init__(*args, **kwargs)

        self.process_evolution_deps = True
        self.process_migration_deps = supports_migrations

        self._app_evolution_nodes = {}

    def add_evolutions(self, app, evolutions=[], new_models=[],
                       extra_state={}):
        """Add a list of evolutions for a given app.

        Each evolution will gets its own node, and pending dependencies will
        be recorded to ensure the evolutions are applied in the correct order.

        A special ``__first__`` anchor node will be added before the sequence
        of evolutions, and a ``__last__`` node will be added after. This allows
        evolutions to easily reference another app's list of evolutions
        relative to the start or end of a list. It's used only internally.

        Args:
            app (module):
                The app module the evolutions apply to.

            evolutions (list of django_evolution.models.Evolution, optional):
                The list of evolutions to add to the graph. This may be an
                empty list if there are no evolutions but there are new
                models to create.

            new_models (list of type, optional):
                The list of database model classes to create for the app.

            extra_state (dict, optional):
                Extra state to set in each evolution node.
        """
        app_label = get_app_label(app)
        app_deps = get_evolution_app_dependencies(app)

        nodes = []

        # Add the leading anchor node.
        node = self.add_node(
            key='evolution:%s:__first__' % app_label,
            state={
                'anchor': True,
                'app': app,
            })
        prev_node = node

        if app_deps:
            self._add_evolution_node_after_deps(node, app_deps)

        # If we're creating models, add nodes for that.
        for model in new_models:
            node = self._add_create_model(app=app,
                                          model=model,
                                          extra_state=extra_state)
            self.add_dependency(node_key=node.key,
                                dep_node_key=prev_node.key)

            nodes.append(node)
            prev_node = node

        # Add a node for each evolution.
        for evolution in evolutions:
            node = self._add_evolution(app=app,
                                       evolution=evolution,
                                       extra_state=extra_state)
            self.add_dependency(node_key=node.key,
                                dep_node_key=prev_node.key)

            nodes.append(node)
            prev_node = node

        # Add the trailing anchor node.
        node = self.add_node(
            key='evolution:%s:__last__' % app_label,
            state={
                'anchor': True,
                'app': app,
            })
        self.add_dependency(node_key=node.key,
                            dep_node_key=prev_node.key)

        if app_deps:
            self._add_evolution_node_before_deps(node, app_deps)

        self._app_evolution_nodes.setdefault(app, []).extend(nodes)

    def add_migration_plan(self, migration_plan, migration_graph):
        """Add a migration plan to the graph.

        Each migration in the plan will gets its own node, and pending
        dependencies will be recorded to ensure the migrations are applied in
        the order already computed for the plan.

        Args:
            migration_plan (list of tuple):
                The computed migration plan to add to the graph.

            migration_graph (django.db.migrations.graph.MigrationGraph):
                The computed migration graph, used to reference computed
                dependencies.
        """
        assert supports_migrations

        has_node_map = hasattr(migration_graph, 'node_map')

        for plan_item in migration_plan:
            node = self._add_migration_plan_item(plan_item)
            migration_target = node.state['migration_target']

            if has_node_map:
                # Django >= 1.8
                parents = migration_graph.node_map[migration_target].parents
                deps = (
                    migration_graph.nodes[dep_node.key]
                    for dep_node in parents
                )
            else:
                # Django == 1.7
                deps = migration_graph.dependencies.get(migration_target, [])

            for dep in deps:
                self.add_dependency(node_key=node.key,
                                    dep_node_key=self._make_migration_key(dep))

    def mark_evolutions_applied(self, app, evolution_labels):
        """Mark one or more evolutions as applied.

        This will remove any pending dependencies referencing these evolutions
        from the graph.

        Args:
            app (module):
                The app module the evolutions apply to.

            evolution_labels (list of unicode):
                The list of evolutions labels to mark as applied.
        """
        app_label = get_app_label(app)

        if app not in self._app_evolution_nodes:
            # There aren't any evolution nodes for this app, so let's also
            # get rid of any dependencies to the anchors.
            evolution_labels += ['__first__', '__last__']

        self.remove_dependencies({
            self._make_evolution_key((app_label, evolution_label))
            for evolution_label in evolution_labels
        })

    def mark_migrations_applied(self, migrations):
        """Mark one or more migrations as applied.

        This will remove any pending dependencies referencing these migrations
        from the graph.

        Args:
            migrations (django_evolution.utils.migrations.MigrationList):
                The list of migrations to mark as applied.
        """
        self.remove_dependencies(set(
            self._make_migration_key(migration_target)
            for migration_target in migrations.to_targets()
        ))

    def iter_batches(self):
        """Iterate through batches of consecutive evolutions and migrations.

        The nodes will be iterated in dependency order, with each batch
        containing a sequence of either evolutions or migrations that can be
        applied at once.

        Yields:
            tuple:
            A 2-tuple containing:

            1. The batch type (one of :py:attr:`NODE_TYPE_CREATE_MODEL`,
               :py:attr:`NODE_TYPE_EVOLUTION`, or
               :py:attr:`NODE_TYPE_MIGRATION`).
            2. A list of :py:class:`Node` instances.
        """
        batch_nodes = []
        batch_type = None

        for node in self.get_ordered():
            if node.state.get('anchor'):
                continue

            node_type = node.state['type']

            if node_type != batch_type:
                if batch_nodes:
                    yield batch_type, batch_nodes

                batch_nodes = []
                batch_type = node_type

            batch_nodes.append(node)

        if batch_nodes:
            yield batch_type, batch_nodes

    def _add_create_model(self, app, model, extra_state={}):
        """Add a node for creating a model.

        Args:
            app (module):
                The app module the evolution applies to.

            model (type):
                The model class to create.

            extra_state (dict, optional):
                Extra state to set in the evolution node.

        Returns:
            Node:
            The resulting node.
        """
        key = self._make_create_model_key(get_app_label(app), model)
        node = self.add_node(
            key=key,
            state=dict({
                'app': app,
                'model': model,
                'type': self.NODE_TYPE_CREATE_MODEL,
            }, **extra_state))

        return node

    def _add_evolution(self, app, evolution, extra_state={}):
        """Add a node for an evolution.

        Node dependencies will be registered based on any evolution/migration
        dependencies defined by this evolution.

        Args:
            app (module):
                The app module the evolution applies to.

            evolution (django_evolution.models.Evolution):
                The evolution to add.

            extra_state (dict, optional):
                Extra state to set in the evolution node.

        Returns:
            Node:
            The resulting node.
        """
        key = self._make_evolution_key(evolution)
        node = self.add_node(
            key=key,
            state=dict({
                'app': app,
                'evolution': evolution,
                'type': self.NODE_TYPE_EVOLUTION,
            }, **extra_state))

        # Begin adding any dependencies between this evolution and any other
        # evolution or migration.
        deps = get_evolution_dependencies(app=app,
                                          evolution_label=evolution.label)

        if deps:
            self._add_evolution_node_before_deps(node, deps)
            self._add_evolution_node_after_deps(node, deps)

        return node

    def _add_evolution_node_before_deps(self, node, deps):
        """Add dependencies on evolutions/migrations to process before a node.

        Any dependencies in ``before_evolutions`` or ``before_migrations``
        will be registered in the graph.

        Args:
            node (Node):
                The graph node to add dependencies relative to.

            deps (dict):
                The dependencies owned by the evolution backed by this node.
        """
        # Add dependencies for any evolutions/migrations that this should
        # come before.
        key = node.key

        if self.process_evolution_deps:
            for evolution_target in deps['before_evolutions']:
                if isinstance(evolution_target, six.text_type):
                    # If only an app name is specified, then the special
                    # __first__ anchor node for the app will depend on this
                    # node.
                    evolution_target = (evolution_target, '__first__')

                self.add_dependency(
                    node_key=self._make_evolution_key(evolution_target),
                    dep_node_key=key)

        if self.process_migration_deps:
            for migration_target in deps['before_migrations']:
                self.add_dependency(
                    node_key=self._make_migration_key(migration_target),
                    dep_node_key=key)

    def _add_evolution_node_after_deps(self, node, deps):
        """Add dependencies on evolutions/migrations to process after a node.

        Any dependencies in ``after_evolutions`` or ``after_migrations``
        will be registered in the graph.

        Args:
            node (Node):
                The graph node to add dependencies relative to.

            deps (dict):
                The dependencies owned by the evolution backed by this node.
        """
        # Add dependencies for any evolutions/migrations that this should
        # come after.
        key = node.key

        if self.process_evolution_deps:
            for evolution_target in deps.get('after_evolutions', []):
                if isinstance(evolution_target, six.text_type):
                    # If only an app name is specified, then depend on the
                    # special __first__ anchor node for the app.
                    evolution_target = (evolution_target, '__last__')

                self.add_dependency(
                    node_key=key,
                    dep_node_key=self._make_evolution_key(evolution_target))

        if self.process_migration_deps:
            for migration_target in deps.get('after_migrations', []):
                self.add_dependency(
                    node_key=key,
                    dep_node_key=self._make_migration_key(migration_target))

    def _add_migration_plan_item(self, plan_item):
        """Add an item from a migration plan.

        Args:
            plan_item (tuple):
                The item from a migration plan to add.

        Returns:
            Node:
            The resulting node.
        """
        migration = plan_item[0]

        return self.add_node(
            key=self._make_migration_key(migration),
            state={
                'migration_plan_item': plan_item,
                'migration_target': (migration.app_label, migration.name),
                'type': self.NODE_TYPE_MIGRATION,
            })

    def _make_create_model_key(self, app_label, model):
        """Return a key representing a model to create.

        The key will uniquely identify the node for a model to create in the
        graph.

        Args:
            app_label (unicode):
                The app label that owns the model.

            model (django.db.models.Model):
                The model the key will represent.

        Returns:
            unicode:
            The key for the create model node.
        """
        return 'create-model:%s:%s' % (app_label, get_model_name(model))

    def _make_evolution_key(self, evolution):
        """Return a key representing an evolution.

        The key will uniquely identify the node for an evolution in the graph.
        It supports either an evolution or a tuple identifying one.

        Args:
            evolution (tuple or django_evolution.models.Evolution):
                The identifier for an evolution.

                For a tuple, this needs to be in
                ``(app_label, evolution_label)`` form.

        Returns:
            unicode:
            The key for the evolution node.

        Raises:
            TypeError:
                An invalid type was passed for ``evolution``.
        """
        if isinstance(evolution, tuple):
            assert len(evolution) == 2

            app_label, label = evolution
        elif isinstance(evolution, Evolution):
            app_label = evolution.app_label
            label = evolution.label
        else:
            raise TypeError('Invalid type %s: %s' % (type(evolution),
                                                     evolution))

        return 'evolution:%s:%s' % (app_label, label)

    def _make_migration_key(self, migration):
        """Return a key representing a migration.

        The key will uniquely identify the node for an migration in the graph.
        It supports either a migration or a tuple identifying one.

        Args:
            evolution (tuple or django.db.migrations.migration.Migration):
                The identifier for a migration.

                For a tuple, this needs to be in
                ``(app_label, migration_name)`` form.

        Returns:
            unicode:
            The key for the migration node.

        Raises:
            TypeError:
                An invalid type was passed for ``migration``.
        """
        if isinstance(migration, tuple):
            app_label, name = migration
        elif isinstance(migration, Migration):
            app_label = migration.app_label
            name = migration.name
        else:
            raise TypeError('Invalid type %s: %s' % (type(migration),
                                                     migration))

        return 'migration:%s:%s' % (app_label, name)
