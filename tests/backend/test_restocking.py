"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockingEndpoints:
    """Test suite for restocking-related endpoints."""

    def test_get_recommendations_returns_200_and_shape(self, client):
        """Test that the recommendations endpoint returns the expected response shape."""
        response = client.get("/api/restocking/recommendations?budget=15000")
        assert response.status_code == 200

        data = response.json()
        assert "budget" in data
        assert "total_cost" in data
        assert "remaining_budget" in data
        assert "max_lead_time_days" in data
        assert "items" in data
        assert "considered_count" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

        first_item = data["items"][0]
        for field in [
            "sku", "item_name", "category", "current_stock", "forecasted_demand",
            "shortfall", "unit_cost", "recommended_quantity", "line_cost",
            "supplier", "lead_time_days"
        ]:
            assert field in first_item

    def test_recommendations_ranked_by_shortfall_desc(self, client):
        """Test that recommended items are sorted by shortfall, largest first."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()
        items = data["items"]
        assert len(items) > 1

        shortfalls = [item["shortfall"] for item in items]
        assert shortfalls == sorted(shortfalls, reverse=True)

    @pytest.mark.parametrize("budget", [0, 5000, 15000, 100000])
    def test_recommendations_total_cost_never_exceeds_budget(self, client, budget):
        """Test that the total cost of recommended items never exceeds the given budget."""
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        assert response.status_code == 200

        data = response.json()
        assert data["total_cost"] <= budget

    def test_recommendations_budget_zero_returns_no_items(self, client):
        """Test that a zero budget returns no recommended items."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total_cost"] == 0

    def test_recommendations_large_budget_includes_all_shortfall_items(self, client):
        """Test that a very large budget includes every candidate with a shortfall."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == data["considered_count"]
        assert data["considered_count"] > 0

    def test_recommendations_negative_budget_returns_400(self, client):
        """Test that a negative budget is rejected."""
        response = client.get("/api/restocking/recommendations?budget=-100")
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_recommendations_no_shortfall_items_excluded(self, client):
        """Test that items with stock already covering forecasted demand are never recommended."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        skus = {item["sku"] for item in data["items"]}
        assert "PSU-503" not in skus
        assert "DRV-405" not in skus

    def test_submit_restock_order_appends_to_orders(self, client):
        """Test that submitting a restock order makes it visible via GET /api/orders."""
        payload = {
            "budget": 5000,
            "items": [{"sku": "PCB-003", "quantity": 10}]
        }
        response = client.post("/api/restocking/order", json=payload)
        assert response.status_code == 201

        created_order = response.json()

        orders_response = client.get("/api/orders")
        all_orders = orders_response.json()
        matching = [o for o in all_orders if o["order_number"] == created_order["order_number"]]
        assert len(matching) == 1

    def test_submit_restock_order_response_shape(self, client):
        """Test that a submitted restock order has the expected fields and values."""
        payload = {
            "budget": 5000,
            "items": [{"sku": "PCB-003", "quantity": 10}, {"sku": "HMD-202", "quantity": 5}]
        }
        response = client.post("/api/restocking/order", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert isinstance(order["lead_time_days"], int)
        assert order["lead_time_days"] > 0
        assert order["supplier"]

        expected_total = 10 * 34.5 + 5 * 125.0
        assert abs(order["total_value"] - expected_total) < 0.01

    def test_submit_restock_order_unknown_sku_returns_404(self, client):
        """Test that ordering a nonexistent SKU returns 404."""
        payload = {
            "budget": 5000,
            "items": [{"sku": "NOT-A-REAL-SKU", "quantity": 1}]
        }
        response = client.post("/api/restocking/order", json=payload)
        assert response.status_code == 404

    def test_submit_restock_order_empty_items_returns_400(self, client):
        """Test that submitting an order with no items returns 400."""
        payload = {"budget": 5000, "items": []}
        response = client.post("/api/restocking/order", json=payload)
        assert response.status_code == 400

    def test_submit_restock_order_invalid_quantity_returns_400(self, client):
        """Test that a non-positive quantity is rejected."""
        payload = {
            "budget": 5000,
            "items": [{"sku": "PCB-003", "quantity": 0}]
        }
        response = client.post("/api/restocking/order", json=payload)
        assert response.status_code == 400
