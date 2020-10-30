"""Unit tests for django_evolution.utils.graph.DependencyGraph."""

from __future__ import unicode_literals

from django_evolution.tests.base_test_case import TestCase
from django_evolution.utils.graph import DependencyGraph, NodeNotFoundError


class DependencyGraphTests(TestCase):
    """Unit tests for django_evolution.utils.graph.DependencyGraph."""

    def test_add_node(self):
        """Testing DependencyGraph.add_node"""
        graph = DependencyGraph()
        node1 = graph.add_node('my-key1', {
            'a': 'b',
        })
        node2 = graph.add_node('my-key2', {
            'c': 'd',
        })

        self.assertEqual(graph._nodes, {
            'my-key1': node1,
            'my-key2': node2,
        })

        self.assertEqual(node1.key, 'my-key1')
        self.assertEqual(node1.insert_index, 0)
        self.assertEqual(node1.required_by, set())
        self.assertEqual(node1.state, {
            'a': 'b',
        })

        self.assertEqual(node2.key, 'my-key2')
        self.assertEqual(node2.insert_index, 1)
        self.assertEqual(node1.dependencies, set())
        self.assertEqual(node1.required_by, set())
        self.assertEqual(node2.state, {
            'c': 'd',
        })

    def test_get_node(self):
        """Testing DependencyGraph.get_node"""
        graph = DependencyGraph()
        node = graph.add_node('foo')

        self.assertIs(graph.get_node('foo'), node)

    def test_get_node_with_bad_key(self):
        """Testing DependencyGraph.get_node with bad key"""
        graph = DependencyGraph()

        message = 'A graph node with key "foo" was not found.'

        with self.assertRaisesMessage(NodeNotFoundError, message):
            graph.get_node('foo')

    def test_add_dependency(self):
        """Testing DependencyGraph.add_dependency"""
        graph = DependencyGraph()
        graph.add_dependency(node_key='parent',
                             dep_node_key='child')
        graph.add_dependency(node_key='grandparent',
                             dep_node_key='parent')

        self.assertEqual(
            graph._pending_deps,
            {
                ('parent', 'child'),
                ('grandparent', 'parent'),
            })

    def test_remove_dependencies(self):
        """Testing DependencyGraph.remove_dependencies"""
        graph = DependencyGraph()
        graph.add_dependency(node_key='child',
                             dep_node_key='parent')
        graph.add_dependency(node_key='parent',
                             dep_node_key='grandparent')
        graph.add_dependency(node_key='grandparent',
                             dep_node_key='greatgrandparent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='bar')
        graph.remove_dependencies({'grandparent', 'bar'})

        self.assertEqual(
            graph._pending_deps,
            {
                ('child', 'parent'),
            })

    def test_finalize(self):
        """Testing DependencyGraph.finalize"""
        graph = DependencyGraph()

        grandparent = graph.add_node('grandparent')
        parent = graph.add_node('parent')
        child = graph.add_node('child')
        foo = graph.add_node('foo')

        graph.add_dependency(node_key='child',
                             dep_node_key='parent')
        graph.add_dependency(node_key='parent',
                             dep_node_key='grandparent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='child')
        graph.add_dependency(node_key='foo',
                             dep_node_key='parent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='grandparent')

        graph.finalize()

        self.assertEqual(graph._pending_deps, [])
        self.assertTrue(graph._finalized)

        self.assertEqual(grandparent.dependencies, set())
        self.assertEqual(grandparent.required_by, {foo, parent})

        self.assertEqual(parent.dependencies, {grandparent})
        self.assertEqual(parent.required_by, {child, foo})

        self.assertEqual(child.dependencies, {parent})
        self.assertEqual(child.required_by, {foo})

    def test_finalize_with_bad_dependency(self):
        """Testing DependencyGraph.finalize with missing dependency node"""
        graph = DependencyGraph()
        graph.add_node('bar')
        graph.add_dependency(node_key='foo',
                             dep_node_key='bar')

        message = '"foo" was not found (requires dependency "bar")'

        with self.assertRaisesMessage(AssertionError, message):
            graph.finalize()

    def test_finalize_with_bad_required_by(self):
        """Testing DependencyGraph.finalize with missing required_by node"""
        graph = DependencyGraph()
        graph.add_node('foo')
        graph.add_dependency(node_key='foo',
                             dep_node_key='bar')

        message = '"bar" was not found (required by "foo")'

        with self.assertRaisesMessage(AssertionError, message):
            graph.finalize()

    def test_get_leaf_nodes(self):
        """Testing DependencyGraph.get_leaf_nodes"""
        graph = DependencyGraph()

        first = graph.add_node('first')
        foo = graph.add_node('foo')
        graph.add_node('child')
        graph.add_node('grandparent')
        graph.add_node('parent')
        last = graph.add_node('last')

        graph.add_dependency(node_key='child',
                             dep_node_key='parent')
        graph.add_dependency(node_key='parent',
                             dep_node_key='grandparent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='child')
        graph.add_dependency(node_key='foo',
                             dep_node_key='parent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='grandparent')
        graph.finalize()

        self.assertEqual(graph.get_leaf_nodes(), [first, foo, last])

    def test_get_ordered(self):
        """Testing DependencyGraph.get_ordered"""
        graph = DependencyGraph()

        first = graph.add_node('first')
        foo = graph.add_node('foo')
        child = graph.add_node('child')
        grandparent = graph.add_node('grandparent')
        parent = graph.add_node('parent')
        last = graph.add_node('last')

        graph.add_dependency(node_key='child',
                             dep_node_key='parent')
        graph.add_dependency(node_key='parent',
                             dep_node_key='grandparent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='child')
        graph.add_dependency(node_key='foo',
                             dep_node_key='parent')
        graph.add_dependency(node_key='foo',
                             dep_node_key='grandparent')
        graph.finalize()

        self.assertEqual(graph.get_ordered(),
                         [first, grandparent, parent, child, foo, last])
