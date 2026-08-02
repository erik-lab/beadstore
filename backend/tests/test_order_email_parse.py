from unittest.mock import MagicMock, patch


def test_parse_unconfigured_returns_503(client, auth_headers):
    resp = client.post(
        "/api/v1/order-email-parse",
        json={"subject": "Order confirmation", "from_header": "a@b.com", "date_header": "", "body_text": "hi"},
        headers=auth_headers,
    )
    assert resp.status_code == 503


def test_parse_returns_structured_order(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.routers.order_email_parse.settings.anthropic_api_key", "fake-key")

    fake_text_block = MagicMock()
    fake_text_block.type = "text"
    fake_text_block.text = (
        '{"vendor_name": "Bead Paradise", "order_number": "12345", "order_date": "2026-07-20", '
        '"lines": [{"description": "8mm Round Turquoise Strand", "quantity": 2, "unit": "strand", "unit_cost": 4.5}]}'
    )
    fake_response = MagicMock()
    fake_response.stop_reason = "end_turn"
    fake_response.content = [fake_text_block]

    with patch("app.routers.order_email_parse.anthropic.Anthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create.return_value = fake_response
        resp = client.post(
            "/api/v1/order-email-parse",
            json={
                "subject": "Your order confirmation #12345",
                "from_header": "orders@beadparadise.com",
                "date_header": "Mon, 20 Jul 2026 10:15:00 -0500",
                "body_text": "2 x 8mm Round Turquoise Strand $4.50",
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["vendor_name"] == "Bead Paradise"
    assert data["order_number"] == "12345"
    assert len(data["lines"]) == 1
    assert data["lines"][0]["quantity"] == 2
