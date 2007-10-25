from django.core.management.sql import *
from django.core.management.color import color_style
from django.db.backends.util import truncate_name
from django.db import connection, transaction, get_introspection_module


from django_evolution.management import signature

def test_app_sig(model, app_label='testapp', model_name='TestModel', version=1):
    return {
        app_label: {
            model_name: signature.create_model_sig(model),
        }, 
        '__version__': version,
    }

def mock_sql_create(app_models):
    # Modified code sourced from django/core/management/sql.py
    style = color_style()
    final_output = []
    known_models = set()
    pending_references = {}

    for model in app_models:
        output, references = sql_model_create(model, style, known_models)
        final_output.extend(output)
        for refto, refs in references.items():
            pending_references.setdefault(refto, []).extend(refs)
        final_output.extend(sql_for_pending_references(model, style, pending_references))
        # Keep track of the fact that we've created the table for this model.
        known_models.add(model)

    # Create the many-to-many join tables.
    for model in app_models:
        final_output.extend(many_to_many_sql_for_model(model, style))
    
    if pending_references:
        raise Exception, 'Mock SQL Create Error. Unresolved references %s'%str(pending_references)
        
    return final_output
    
def execute_sql(sql):
    try:
        # Begin Transaction
        transaction.enter_transaction_management()
        transaction.managed(True)
        cursor = connection.cursor()
        
        # Perform the SQL
        for statement in sql:
            cursor.execute(statement)  
        
        transaction.commit()
        transaction.leave_transaction_management()
    except Exception, ex:
        transaction.rollback()
        raise ex

def mock_sql_delete(app_models):
    # Modified code sourced from django/core/management/sql.py
    style = color_style()
    introspection = get_introspection_module()

    # This should work even if a connection isn't available
    try:
        cursor = connection.cursor()
    except:
        cursor = None

    table_names = introspection.get_table_list(cursor)

    if connection.features.uses_case_insensitive_names:
        table_name_converter = lambda x: x.upper()
    else:
        table_name_converter = lambda x: x

    output = []
    qn = connection.ops.quote_name

    # Output DROP TABLE statements for standard application tables.
    # What does to_delete actually do? Stuff gets added to it but never retrieved.
    to_delete = set()

    references_to_delete = {}
    for model in app_models:
        if cursor and table_name_converter(model._meta.db_table) in table_names:
            # The table exists, so it needs to be dropped
            opts = model._meta
            for f in opts.fields:
                if f.rel and f.rel.to not in to_delete:
                    references_to_delete.setdefault(f.rel.to, []).append( (model, f) )

            to_delete.add(model)

    for model in app_models:
        if cursor and table_name_converter(model._meta.db_table) in table_names:
            # Drop the table now
            output.append('%s %s;' % (style.SQL_KEYWORD('DROP TABLE'),
                style.SQL_TABLE(qn(model._meta.db_table))))
            if connection.features.supports_constraints and model in references_to_delete:
                for rel_class, f in references_to_delete[model]:
                    table = rel_class._meta.db_table
                    col = f.column
                    r_table = model._meta.db_table
                    r_col = model._meta.get_field(f.rel.field_name).column
                    r_name = '%s_refs_%s_%x' % (col, r_col, abs(hash((table, r_table))))
                    output.append('%s %s %s %s;' % \
                        (style.SQL_KEYWORD('ALTER TABLE'),
                        style.SQL_TABLE(qn(table)),
                        style.SQL_KEYWORD(connection.ops.drop_foreignkey_sql()),
                        style.SQL_FIELD(truncate_name(r_name, connection.ops.max_name_length()))))
                del references_to_delete[model]
            if model._meta.has_auto_field:
                ds = connection.ops.drop_sequence_sql(model._meta.db_table)
                if ds:
                    output.append(ds)

    # Output DROP TABLE statements for many-to-many tables.
    for model in app_models:
        opts = model._meta
        for f in opts.many_to_many:
            if cursor and table_name_converter(f.m2m_db_table()) in table_names:
                output.append("%s %s;" % (style.SQL_KEYWORD('DROP TABLE'),
                    style.SQL_TABLE(qn(f.m2m_db_table()))))
                ds = connection.ops.drop_sequence_sql("%s_%s" % (model._meta.db_table, f.column))
                if ds:
                    output.append(ds)


    # Close database connection explicitly, in case this output is being piped
    # directly into a database client, to avoid locking issues.
    if cursor:
        cursor.close()
        connection.close()

    return output[::-1] # Reverse it, to deal with table dependencies.