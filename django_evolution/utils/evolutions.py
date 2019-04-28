"""Utilities for working with evolutions and mutations."""

from __future__ import unicode_literals

import os
from importlib import import_module

from django.db.utils import DEFAULT_DB_ALIAS

from django_evolution.builtin_evolutions import BUILTIN_SEQUENCES
from django_evolution.errors import EvolutionException
from django_evolution.models import Evolution, Version
from django_evolution.mutations import RenameModel, SQLMutation
from django_evolution.signature import ProjectSignature
from django_evolution.utils.apps import get_app_label, get_app_name


def get_evolutions_module(app):
    """Return the evolutions module for an app.

    Args:
        app (module):
            The app.

    Returns:
        module:
        The evolutions module for the app, or ``None`` if it could not be
        found.
    """
    app_name = get_app_name(app)

    try:
        return __import__(app_name + '.evolutions', {}, {}, [''])
    except:
        return None


def get_evolutions_path(app):
    """Return the evolutions path for an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The path to the evolutions module for the app, or ``None`` if it
        could not be found.
    """
    module = get_evolutions_module(app)

    if module:
        return os.path.dirname(module.__file__)

    return None


def get_evolution_sequence(app):
    """Return the list of evolution labels for a Django app.

    Args:
        app (module):
            The app to return evolutions for.

    Returns:
        list of unicode:
        The list of evolution labels.
    """
    app_name = get_app_name(app)

    if app_name in BUILTIN_SEQUENCES:
        return BUILTIN_SEQUENCES[app_name]

    try:
        return import_module('%s.evolutions' % app_name).SEQUENCE
    except Exception:
        return []


def get_unapplied_evolutions(app, database=DEFAULT_DB_ALIAS):
    """Return the list of labels for unapplied evolutions for a Django app.

    Args:
        app (module):
            The app to return evolutions for.

        database (unicode, optional):
            The name of the database containing the
            :py:class:`~django_evolution.models.Evolution` entries.

    Returns:
        list of unicode:
        The labels of evolutions that have not yet been applied.
    """
    applied = set(
        Evolution.objects
        .using(database)
        .filter(app_label=get_app_label(app))
        .values_list('label', flat=True)
    )

    return [
        evolution_name
        for evolution_name in get_evolution_sequence(app)
        if evolution_name not in applied
    ]


def get_mutations(app, evolution_labels, database=DEFAULT_DB_ALIAS):
    """Return the mutations provided by the given evolution names.

    Args:
        app (module):
            The app the evolutions belong to.

        evolution_labels (unicode):
            The labels of the evolutions to return mutations for.

        database (unicode, optional):
            The name of the database the evolutions cover.

    Returns:
        list of django_evolution.mutations.BaseMutation:
        The list of mutations provided by the evolutions.

    Raises:
        django_evolution.errors.EvolutionException:
            One or more evolutions are missing.
    """
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    try:
        app_name = get_app_name(app)

        if app_name in BUILTIN_SEQUENCES:
            module_name = 'django_evolution.builtin_evolutions'
        else:
            module_name = '%s.evolutions' % app_name

        evolution_module = import_module(module_name)
    except ImportError:
        return []

    mutations = []

    for label in evolution_labels:
        directory_name = os.path.dirname(evolution_module.__file__)

        # The first element is used for compatibility purposes.
        filenames = [
            os.path.join(directory_name, label + '.sql'),
            os.path.join(directory_name, "%s_%s.sql" % (database, label)),
        ]

        found = False

        for filename in filenames:
            if os.path.exists(filename):
                sql_file = open(filename, 'r')
                sql = sql_file.readlines()
                sql_file.close()

                mutations.append(SQLMutation(label, sql))

                found = True
                break

        if not found:
            try:
                module_name = [evolution_module.__name__, label]
                module = __import__('.'.join(module_name),
                                    {}, {}, [module_name])
                mutations.extend(module.MUTATIONS)
            except ImportError:
                raise EvolutionException(
                    'Error: Failed to find an SQL or Python evolution named %s'
                    % label)

    latest_version = Version.objects.current_version(using=database)

    app_id = get_app_label(app)
    old_project_sig = latest_version.signature
    project_sig = ProjectSignature.from_database(database)

    old_app_sig = old_project_sig.get_app_sig(app_id)
    app_sig = project_sig.get_app_sig(app_id)

    if old_app_sig is not None and app_sig is not None:
        # We want to go through now and make sure we're only applying
        # evolutions for models where the signature is different between
        # what's stored and what's current.
        #
        # The reason for this is that we may have just installed a baseline,
        # which would have the up-to-date signature, and we might be trying
        # to apply evolutions on top of that (which would already be applied).
        # These would generate errors. So, try hard to prevent that.
        #
        # First, Find the list of models in the latest signature of this app
        # that aren't in the old signature.
        changed_models = set(
            model_sig.model_name
            for model_sig in app_sig.model_sigs
            if old_app_sig.get_model_sig(model_sig.model_name) != model_sig
        )

        # Now do the same for models in the old signature, in case the
        # model has been deleted.
        changed_models.update(
            old_model_sig.model_name
            for old_model_sig in old_app_sig.model_sigs
            if app_sig.get_model_sig(old_model_sig.model_name) is None
        )

        # We should now have a full list of which models changed. Filter
        # the list of mutations appropriately.
        #
        # Changes affecting a model that was newly-introduced are removed,
        # unless the mutation is a RenameModel, in which case we'll need it
        # during the optimization step (and will remove it if necessary then).
        mutations = [
            mutation
            for mutation in mutations
            if (not hasattr(mutation, 'model_name') or
                mutation.model_name in changed_models or
                isinstance(mutation, RenameModel))
        ]

    return mutations
