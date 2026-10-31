"""Offline API contract checks; no real credentials or network access."""
import json
import secrets
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError
import server


class InputTests(unittest.TestCase):
    def test_rejects_invalid_ids_pages_and_unknown_fields(self):
        for model, data in [(server.GetRepliesInput, {'appointment_id': 0}),
                            (server.ListAppointmentsInput, {'page': -1}),
                            (server.ListAppointmentsInput, {'unexpected': True})]:
            with self.subTest(model=model), self.assertRaises(ValidationError):
                model(**data)

    def test_missing_credentials_fail_before_a_request(self):
        with patch.object(server, 'API_KEY', ''), self.assertRaisesRegex(ValueError, 'not set'):
            server._get_headers()

    def test_http_failures_have_actionable_messages(self):
        for status, expected in [(401, 'Invalid API key'), (403, 'Access denied'),
                                 (404, 'not found'), (429, 'Rate limit')]:
            request = httpx.Request('GET', 'https://example.invalid')
            response = httpx.Response(status, request=request)
            error = httpx.HTTPStatusError('test', request=request, response=response)
            self.assertIn(expected, server._handle_error(error))
        self.assertIn('timed out', server._handle_error(httpx.ReadTimeout('test')))


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.key = secrets.token_hex(16)
        self.original_client = httpx.AsyncClient
        self.seen = []

    def client(self, **kwargs):
        def handle(request):
            self.seen.append(request)
            return httpx.Response(200, json={'id': 42})
        return self.original_client(transport=httpx.MockTransport(handle), **kwargs)

    async def test_get_and_post_keep_auth_path_and_payload(self):
        with patch.object(server, 'API_KEY', self.key), patch.object(server.httpx, 'AsyncClient', self.client):
            self.assertEqual(await server._get('/api/test'), {'id': 42})
            self.assertEqual(await server._post('/api/test', {'page': 2}), {'id': 42})
        self.assertEqual([r.method for r in self.seen], ['GET', 'POST'])
        for request in self.seen:
            self.assertEqual(str(request.url), server.BASE_URL + '/api/test')
            self.assertEqual(request.headers['X-KM-ORG-API-KEY'], self.key)
        self.assertEqual(json.loads(self.seen[1].content), {'page': 2})

    async def test_http_failure_is_propagated_by_transport_helper(self):
        def client(**kwargs):
            return self.original_client(transport=httpx.MockTransport(lambda r: httpx.Response(403)), **kwargs)
        with patch.object(server, 'API_KEY', self.key), patch.object(server.httpx, 'AsyncClient', client):
            with self.assertRaises(httpx.HTTPStatusError):
                await server._get('/api/test')


if __name__ == '__main__':
    unittest.main()
