"""Unit tests for django_evolution.utils.datastructures."""

from __future__ import unicode_literals

from django_evolution.tests.base_test_case import TestCase
from django_evolution.utils.datastructures import (filter_dup_list_items,
                                                   merge_dicts)


class DatastructuresTests(TestCase):
    """Unit tests for django_evolution.utils.datastructures."""

    def test_filter_dup_list_items(self):
        """Testing filter_dup_list_items"""
        self.assertEqual(
            filter_dup_list_items(['a', 'b', 1, 3, 'a', 'z', 2, 1, '', '']),
            ['a', 'b', 1, 3, 'z', 2, ''])

    def test_merge_dicts(self):
        """Testing merge_dicts with empty source"""
        dest = {
            'a': True,
            'b': [1, 2, 3],
            'c': {
                'key1': 'value1',
                'key2': {
                    'subkey1': ['foo', 'bar'],
                },
            },
        }

        merge_dicts(
            dest,
            {
                'foo': 'bar',
                'b': [4, 5, 6],
                'c': {
                    'key2': {
                        'subkey1': ['baz'],
                        'subkey2': True,
                    },
                    'key3': None,
                },
            })

        self.assertEqual(
            dest,
            {
                'a': True,
                'b': [1, 2, 3, 4, 5, 6],
                'c': {
                    'key1': 'value1',
                    'key2': {
                        'subkey1': ['foo', 'bar', 'baz'],
                        'subkey2': True,
                    },
                    'key3': None,
                },
                'foo': 'bar',
            })

    def test_merge_dicts_with_empty_dest(self):
        """Testing merge_dicts with empty destination"""
        dest = {}

        merge_dicts(
            dest,
            {
                'a': True,
                'b': [1, 2, 3],
                'c': {
                    'key1': 'value1',
                    'key2': None,
                },
            })

        self.assertEqual(
            dest,
            {
                'a': True,
                'b': [1, 2, 3],
                'c': {
                    'key1': 'value1',
                    'key2': None,
                },
            })

    def test_merge_dicts_with_empty_source(self):
        """Testing merge_dicts with empty source"""
        dest = {
            'a': True,
            'b': [1, 2, 3],
            'c': {
                'key1': 'value1',
                'key2': None,
            },
        }

        merge_dicts(dest, {})

        self.assertEqual(
            dest,
            {
                'a': True,
                'b': [1, 2, 3],
                'c': {
                    'key1': 'value1',
                    'key2': None,
                },
            })

    def test_merge_dicts_with_dict_and_mismatched_type(self):
        """Testing merge_dicts with merging dictionary into non-dictionary"""
        dest = {
            'a': 100,
        }

        message = (
            'Cannot merge a dictionary into a %s for key "a".' % int
        )

        with self.assertRaisesMessage(TypeError, message):
            merge_dicts(
                dest,
                {
                    'a': {
                        'b': 1,
                    },
                })

    def test_merge_dicts_with_list_and_mismatched_type(self):
        """Testing merge_dicts with merging list into non-list"""
        dest = {
            'a': 100,
        }

        message = (
            'Cannot merge a list into a %s for key "a".' % int
        )

        with self.assertRaisesMessage(TypeError, message):
            merge_dicts(
                dest,
                {
                    'a': [1, 2, 3],
                })

    def test_merge_dicts_with_unmergeable_type(self):
        """Testing merge_dicts with unmergeable type"""
        dest = {
            'a': 100,
        }

        message = (
            'Key "a" was not an expected type (found %s) when merging '
            'dictionaries.'
            % int
        )

        with self.assertRaisesMessage(TypeError, message):
            merge_dicts(
                dest,
                {
                    'a': 200,
                })
