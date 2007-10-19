from django_evolution.management import signature

def test_app_sig(model, app_label='testapp', model_name='TestModel', version=1):
    return {
        app_label: {
            model_name: signature.create_model_sig(model),
        }, 
        '__version__': version,
    }

