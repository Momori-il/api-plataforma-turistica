"""OpenAPI documents effective middleware/domain behavior without changing public DTOs."""
from main import app


def test_openapi_operations_have_unique_ids_tags_and_effective_validation():
    schema=app.openapi();ids=[]
    for path,methods in schema['paths'].items():
        for method,operation in methods.items():
            ids.append(operation['operationId'])
            assert operation['tags'], (path,method)
            assert '422' not in operation['responses']
            if method in {'post','put','patch'}:
                assert '413' in operation['responses']
    assert len(ids)==len(set(ids))


def test_openapi_rate_limit_and_unavailability_are_documented():
    paths=app.openapi()['paths']
    for path in ['/auth/login','/auth/register','/api/v1/reservas/{reserva_id}/pagos/simular']:
        assert {'429','503'}<=paths[path]['post']['responses'].keys()


def test_openapi_reservation_auth_and_idempotency_header():
    paths=app.openapi()['paths']
    for path in ['/api/v1/reservas/hotel','/api/v1/reservas/actividad']:
        operation=paths[path]['post']
        assert operation['security']==[{'JWT':[]}]
        assert any(p['name']=='Idempotency-Key' and not p['required'] for p in operation['parameters'])
    assert 'security' not in paths['/auth/login']['post']
    assert '/metrics' not in paths


def test_openapi_legacy_viajes_documents_real_errors():
    paths=app.openapi()['paths']
    assert '404' in paths['/api/v2/viajes/{id}']['get']['responses']
    assert {'404','409'}<=paths['/api/v2/viajes/{id}/hoteles']['post']['responses'].keys()
