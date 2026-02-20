"""Tests for server.py authentication -- PIN auth, token generation, lockout, rate limiting."""

import time

import pytest


class TestPINAuthentication:
    """Test the /api/auth endpoint."""

    async def test_valid_pin_returns_token(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) > 20

    async def test_invalid_pin_returns_401(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/auth", json={"pin": "wrong_pin"})
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data

    async def test_empty_pin_returns_400(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/auth", json={"pin": ""})
        assert resp.status_code == 400

    async def test_missing_body_returns_400(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post(
            "/api/auth",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    async def test_remaining_attempts_shown(self, test_app, unauthenticated_client):
        """After a failed attempt, remaining_attempts should be in the response."""
        import server
        server._auth_attempts.clear()

        resp = await unauthenticated_client.post("/api/auth", json={"pin": "bad"})
        assert resp.status_code == 401
        data = resp.json()
        assert "remaining_attempts" in data
        assert data["remaining_attempts"] >= 1

    async def test_multiple_tokens_can_coexist(self, test_app, unauthenticated_client):
        """Multiple tokens from separate auth calls should all work."""
        import server

        resp1 = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        token1 = resp1.json()["token"]

        resp2 = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        token2 = resp2.json()["token"]

        assert token1 != token2
        assert server.verify_token(token1)
        assert server.verify_token(token2)


class TestLockout:
    """Test IP lockout mechanism.

    The lockout logic in server.py works by tracking failed attempts per IP.
    We test it by directly setting up the _auth_attempts state, since the
    lockout check happens at the beginning of the /api/auth handler.
    """

    async def test_locked_ip_gets_429(self, test_app, unauthenticated_client):
        """An IP that is currently locked out should get 429."""
        import server
        server._auth_attempts.clear()

        # Directly set up a lockout state for the test client's IP
        server._auth_attempts["127.0.0.1"] = {
            "attempts": server.MAX_PIN_ATTEMPTS,
            "locked_until": time.time() + 300,  # locked for 5 more minutes
        }

        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 429
        data = resp.json()
        assert data.get("locked") is True
        assert "remaining_seconds" in data

    async def test_locked_ip_rejects_correct_pin(self, test_app, unauthenticated_client):
        """Even with correct PIN, a locked IP should get 429."""
        import server
        server._auth_attempts.clear()

        server._auth_attempts["127.0.0.1"] = {
            "attempts": server.MAX_PIN_ATTEMPTS,
            "locked_until": time.time() + 300,
        }

        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 429

    async def test_expired_lockout_allows_auth(self, test_app, unauthenticated_client):
        """Once the lockout expires, the IP can authenticate again."""
        import server
        server._auth_attempts.clear()

        # Set a lockout that already expired
        server._auth_attempts["127.0.0.1"] = {
            "attempts": server.MAX_PIN_ATTEMPTS,
            "locked_until": time.time() - 10,  # expired 10 seconds ago
        }

        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 200
        assert "token" in resp.json()

    async def test_successful_auth_clears_attempts(self, test_app, unauthenticated_client):
        """A successful login should clear the failed attempt counter."""
        import server
        server._auth_attempts.clear()

        # One failed attempt
        await unauthenticated_client.post("/api/auth", json={"pin": "wrong"})

        # Successful auth
        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 200

        # Verify we can auth again without issues
        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        assert resp.status_code == 200

    async def test_lockout_constants(self, test_app):
        """Verify lockout constants are reasonable."""
        import server
        assert server.MAX_PIN_ATTEMPTS >= 3
        assert server.LOCKOUT_SECONDS >= 60


class TestTokenVerification:
    """Test token validation on protected endpoints."""

    async def test_protected_endpoint_without_token(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_protected_endpoint_with_invalid_token(self, test_app, unauthenticated_client):
        unauthenticated_client.headers["Authorization"] = "Bearer invalid_token_here"
        resp = await unauthenticated_client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_protected_endpoint_with_valid_token(self, test_app, authenticated_client):
        resp = await authenticated_client.get("/api/metrics")
        assert resp.status_code == 200

    async def test_token_in_bearer_format(self, test_app, unauthenticated_client):
        """Token must be in 'Bearer <token>' format."""
        # Auth to get a token
        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        token = resp.json()["token"]

        # Without Bearer prefix -- should fail
        unauthenticated_client.headers["Authorization"] = token
        resp = await unauthenticated_client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_expired_token_rejected(self, test_app, unauthenticated_client):
        """An expired token should be rejected."""
        import server

        # Auth to get a token
        resp = await unauthenticated_client.post("/api/auth", json={"pin": test_app["pin"]})
        token = resp.json()["token"]

        # Manually expire the token
        server.active_tokens[token] = time.time() - 1

        unauthenticated_client.headers["Authorization"] = f"Bearer {token}"
        resp = await unauthenticated_client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_verify_token_function(self, test_app):
        """Test the verify_token function directly."""
        import server

        # None token
        assert server.verify_token(None) is False

        # Non-existent token
        assert server.verify_token("nonexistent") is False

        # Valid token
        token = "test_token_123"
        server.active_tokens[token] = time.time() + 3600
        assert server.verify_token(token) is True

        # Expired token
        server.active_tokens[token] = time.time() - 1
        assert server.verify_token(token) is False
        # Should be cleaned up
        assert token not in server.active_tokens


class TestLogout:
    """Test token revocation endpoints."""

    async def test_logout_revokes_token(self, test_app, authenticated_client):
        # Logout
        resp = await authenticated_client.post("/api/logout")
        assert resp.status_code == 200
        assert resp.json()["logged_out"] is True

        # Token should no longer work
        resp = await authenticated_client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_logout_without_token(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/logout")
        assert resp.status_code == 401

    async def test_logout_all_requires_pin(self, test_app, authenticated_client):
        # Without PIN
        resp = await authenticated_client.post("/api/logout-all", json={})
        assert resp.status_code == 401

    async def test_logout_all_with_wrong_pin(self, test_app, authenticated_client):
        resp = await authenticated_client.post("/api/logout-all", json={"pin": "wrong"})
        assert resp.status_code == 401

    async def test_logout_all_with_correct_pin(self, test_app, unauthenticated_client):
        """Logout-all with correct PIN revokes all tokens."""
        pin = test_app["pin"]

        # Auth to get a token
        resp = await unauthenticated_client.post("/api/auth", json={"pin": pin})
        token = resp.json()["token"]

        unauthenticated_client.headers["Authorization"] = f"Bearer {token}"
        resp = await unauthenticated_client.post("/api/logout-all", json={"pin": pin})
        assert resp.status_code == 200
        assert resp.json()["logged_out_all"] is True

    async def test_logout_all_invalid_body(self, test_app, authenticated_client):
        resp = await authenticated_client.post(
            "/api/logout-all",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400


class TestSecurityHeaders:
    """Test that security headers are present in responses."""

    async def test_security_headers_present(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/auth", json={"pin": "test"})
        headers = resp.headers
        assert "x-content-type-options" in headers
        assert headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in headers
        assert headers["x-frame-options"] == "DENY"
        assert "x-xss-protection" in headers

    async def test_referrer_policy_header(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/auth", json={"pin": "test"})
        assert "referrer-policy" in resp.headers

    async def test_permissions_policy_header(self, test_app, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/auth", json={"pin": "test"})
        assert "permissions-policy" in resp.headers
