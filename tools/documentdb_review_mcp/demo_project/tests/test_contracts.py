from services.gateway.service import fetch_json


def test_fetch_json_shape():
    # smoke only; integration run starts actual services
    assert callable(fetch_json)
