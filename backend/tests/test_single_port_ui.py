"""
Tests for Single-Port Desktop / Web Application Serving:
Verifies that FastAPI serves frontend/dist directly at root and SPA paths
while maintaining clean JSON responses for API routes.
"""
from fastapi.testclient import TestClient
from backend.app_factory import create_app

def test_root_serves_frontend_html():
    app = create_app(mode="desktop")
    client = TestClient(app)
    
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "ClipFarm" in response.text
    assert "root" in response.text

def test_spa_route_fallback():
    app = create_app(mode="desktop")
    client = TestClient(app)
    
    # Non-API path should fallback to index.html for client-side routing
    response = client.get("/projects")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "ClipFarm" in response.text

def test_api_routes_not_shadowed():
    app = create_app(mode="desktop")
    client = TestClient(app)
    
    # Valid API route returns JSON
    response = client.get("/api/v1/projects/")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert "items" in response.json() or isinstance(response.json(), list)

    # Invalid API route returns 404 JSON (not HTML!)
    response_404 = client.get("/api/v1/invalid_route_xyz")
    assert response_404.status_code == 404
    assert "application/json" in response_404.headers.get("content-type", "")
