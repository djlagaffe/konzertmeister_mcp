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


class ApiSyncTests(unittest.IsolatedAsyncioTestCase):
    async def run_tool(self, tool, params):
        seen = []

        def handle(request):
            seen.append(request)
            return httpx.Response(200, json=[])

        original = httpx.AsyncClient
        client = lambda **kw: original(transport=httpx.MockTransport(handle), **kw)
        with patch.object(server, 'API_KEY', secrets.token_hex(8)), patch.object(server.httpx, 'AsyncClient', client):
            result = await tool(params)
        return result, seen

    async def test_tags_filter_is_sent(self):
        _, seen = await self.run_tool(server.km_list_appointments,
                                      server.ListAppointmentsInput(tags=['Gala']))
        self.assertEqual(json.loads(seen[0].content)['tags'], ['Gala'])

    async def test_member_properties_are_mapped(self):
        params = server.AddMemberInput(mail='a@example.org', properties=[
            {'property_ext_id': 'P1', 'value_number': 3}])
        _, seen = await self.run_tool(server.km_add_member, params)
        self.assertEqual(json.loads(seen[0].content)['properties'],
                         [{'propertyExtId': 'P1', 'valueNumber': 3.0}])

    async def test_property_needs_exactly_one_value(self):
        params = server.UpdateMemberInput(mail='a@example.org', properties=[
            {'property_ext_id': 'P1', 'value_string': 'x', 'value_boolean': True}])
        result, seen = await self.run_tool(server.km_update_member, params)
        self.assertIn('exactly one', result)
        self.assertEqual(seen, [])

    def test_input_validation(self):
        bad = [(server.AddMemberInput, {'mail': 'not-an-email'}),
               (server.ListAppointmentsInput, {'filter_start': '2025-01-01'}),
               (server.ListAppointmentsInput, {'filter_start': '2025-01-01T10:00:00'}),
               (server.ListAppointmentsInput, {'response_format': 'xml'}),
               (server.CreateAppointmentInput, {
                   'name': 'x', 'start_zoned': '2025-11-22T19:30:00+01:00',
                   'appointment_template_ext_id': 'nope', 'creator_mail': 'a@example.org'})]
        for model, data in bad:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                model(**data)
        server.ListAppointmentsInput(filter_start='2025-01-01T10:00:00+01:00')

    def test_error_text_never_includes_response_body(self):
        request = httpx.Request('GET', 'https://example.invalid')
        response = httpx.Response(500, request=request, text='internal secret detail')
        error = httpx.HTTPStatusError('x', request=request, response=response)
        message = server._handle_error(error)
        self.assertIn('500', message)
        self.assertNotIn('secret', message)

    def test_extra_appointment_fields_are_formatted(self):
        text = server._fmt_appointment({'id': 1, 'name': 'n', 'active': False, 'cancelDescription': 'sick',
                                        'timezoneId': 'Europe/Zurich', 'group': {'name': 'Brass'}})
        for part in ('sick', 'Europe/Zurich', 'Brass'):
            self.assertIn(part, text)

    def test_cli_defaults_to_stdio(self):
        with patch.object(server.mcp, 'run') as run:
            server.main([])
        run.assert_called_once_with(transport='stdio')


if __name__ == '__main__':
    unittest.main()
