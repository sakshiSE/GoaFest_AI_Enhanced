from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.tools import calculate_trip_budget, validate_itinerary

client = TestClient(app)

def payload():
    return {"festival": "Goa Carnival", "start_date": str(date(2027, 2, 10)), "days": 3,
            "travellers": 2, "budget_inr": 12000, "interests": ["beaches", "heritage"],
            "food_preferences": ["Goan food"], "travel_style": "balanced", "accommodation": "budget hotel"}

def test_health():
    assert client.get('/health').status_code == 200

def test_three_day_plan():
    response = client.post('/plan', json=payload())
    assert response.status_code == 200
    result = response.json()
    assert len(result['itinerary']['days']) == 3
    assert result['budget']['total_inr'] >= 0
    assert 'warnings' in result['validation']
    assert result['workflow']['engine'] in {'LangGraph', 'deterministic fallback'}

def test_invalid_days():
    request = payload(); request['days'] = 0
    assert client.post('/plan', json=request).status_code == 422

def test_budget_arithmetic():
    request = payload()
    budget = calculate_trip_budget(request, {"days": []})
    assert budget['total_inr'] == sum(line['amount_inr'] for line in budget['lines'])

def test_validation_overlap():
    itinerary = {'days': [{'day': 1, 'schedule': [
        {'start_time': '10:00', 'end_time': '12:00', 'title': 'A'},
        {'start_time': '11:00', 'end_time': '13:00', 'title': 'B'}]}]}
    output = validate_itinerary(itinerary, {'within_budget': True, 'remaining_inr': 0})
    assert any('overlap' in warning for warning in output['warnings'])

def test_fallback_without_key(monkeypatch):
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    response = client.get('/search', params={'q': 'Goa festival'})
    assert response.status_code == 200
    assert response.json()['status'] == 'unavailable'

def test_catalog_reads_csv_and_categories(monkeypatch):
    from app import catalog
    monkeypatch.setattr(catalog, 'find_image', lambda query: {'url': None, 'source_url': None, 'status': 'test-fallback'})
    response = client.get('/catalog')
    assert response.status_code == 200
    data = response.json()
    assert {'places', 'food', 'restaurants', 'events', 'activities', 'transport'} <= data.keys()
    assert data['places'] and data['food'] and data['restaurants'] and data['events']

def test_empty_search_is_rejected():
    assert client.get('/search', params={'q': '  '}).status_code == 422
