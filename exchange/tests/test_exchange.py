from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth.models import User
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from exchange.models import Handover, PartListing, Report, Reservation
from exchange.services import ExchangeError, cancel_reservation, confirm_handover, reserve_part


def create_part(owner, **overrides):
    values = {
        'title': 'Test screen', 'manufacturer': 'DemoMaker', 'part_code': 'LCD-TEST-01',
        'category': 'screen', 'condition': 'tested', 'supported_models': 'DemoModel A',
        'description': 'Fictional tested component.', 'pickup_area': 'Campus lab',
    }
    values.update(overrides)
    return PartListing.objects.create(owner=owner, **values)


class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.donor = User.objects.create_user('testdonor', password='Test-Donor-2026!')
        cls.repairer = User.objects.create_user('testrepairer', password='Test-Repairer-2026!')
        cls.other = User.objects.create_user('outsider', password='Test-Other-2026!')

    def setUp(self):
        self.part = create_part(self.donor)
        self.api = APIClient()
        self.api.force_authenticate(self.repairer)

    def claim(self):
        return reserve_part(part_id=self.part.pk, user=self.repairer, compatibility_confirmed=True, repair_note='Fixing a matching screen.')

    def test_complete_handover_lifecycle(self):
        reservation = self.claim()
        self.part.refresh_from_db()
        self.assertEqual(self.part.status, 'reserved')
        confirmed = confirm_handover(reservation_id=reservation.pk, user=self.donor, note='Collected at the lab.')
        self.part.refresh_from_db()
        self.assertEqual(confirmed.status, 'collected')
        self.assertEqual(self.part.status, 'collected')
        self.assertEqual(Handover.objects.get(reservation=reservation).confirmed_by, self.donor)
        with self.assertRaises(ExchangeError):
            confirm_handover(reservation_id=reservation.pk, user=self.donor)
        self.assertEqual(Handover.objects.count(), 1)

    def test_cancellation_releases_part_and_keeps_history(self):
        first = self.claim()
        cancel_reservation(reservation_id=first.pk, user=self.repairer)
        self.part.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(self.part.status, 'available')
        self.assertEqual(first.status, 'cancelled')
        second = reserve_part(part_id=self.part.pk, user=self.other, compatibility_confirmed=True)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(self.part.reservations.count(), 2)

    def test_donor_can_cancel_incoming_request(self):
        reservation = self.claim()
        result = cancel_reservation(reservation_id=reservation.pk, user=self.donor)
        self.assertEqual(result.status, 'cancelled')

    def test_self_reservation_denied(self):
        with self.assertRaises(ExchangeError) as error:
            reserve_part(part_id=self.part.pk, user=self.donor, compatibility_confirmed=True)
        self.assertEqual(error.exception.status_code, 403)
        self.assertFalse(Reservation.objects.exists())

    def test_compatibility_confirmation_required(self):
        result = self.api.post('/api/reservations/', {'part_id': self.part.pk, 'compatibility_confirmed': False}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(Reservation.objects.exists())

    def test_duplicate_claim_returns_conflict(self):
        self.claim()
        response = self.api.post('/api/reservations/', {'part_id': self.part.pk, 'compatibility_confirmed': True}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_unknown_part_returns_404(self):
        result = self.api.post('/api/reservations/', {'part_id': 99999, 'compatibility_confirmed': True}, format='json')
        self.assertEqual(result.status_code, 404)

    def test_unauthorized_listing_edit_denied(self):
        result = self.api.patch(f'/api/parts/{self.part.pk}/', {'title': 'Hijacked'}, format='json')
        self.assertEqual(result.status_code, 403)
        self.part.refresh_from_db()
        self.assertEqual(self.part.title, 'Test screen')

    def test_owner_can_edit_available_listing(self):
        self.api.force_authenticate(self.donor)
        result = self.api.patch(f'/api/parts/{self.part.pk}/', {'title': 'Updated screen', 'part_code': 'lower-case'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.part_code, 'LOWER-CASE')

    def test_reserved_listing_cannot_be_changed(self):
        self.claim()
        self.api.force_authenticate(self.donor)
        result = self.api.patch(f'/api/parts/{self.part.pk}/', {'part_code': 'CHANGED'}, format='json')
        self.assertEqual(result.status_code, 409)

    def test_client_cannot_set_owner_or_status(self):
        self.api.force_authenticate(self.donor)
        for field, value in [('owner', self.other.pk), ('status', 'collected')]:
            result = self.api.patch(f'/api/parts/{self.part.pk}/', {field: value}, format='json')
            self.assertEqual(result.status_code, 400)

    def test_cannot_withdraw_reserved_part(self):
        self.claim()
        self.api.force_authenticate(self.donor)
        result = self.api.post(f'/api/parts/{self.part.pk}/withdraw/', {}, format='json')
        self.assertEqual(result.status_code, 409)

    def test_withdrawn_part_cannot_be_reserved(self):
        self.api.force_authenticate(self.donor)
        result = self.api.post(f'/api/parts/{self.part.pk}/withdraw/', {}, format='json')
        self.assertEqual(result.status_code, 200)
        self.api.force_authenticate(self.repairer)
        result = self.api.post('/api/reservations/', {'part_id': self.part.pk, 'compatibility_confirmed': True}, format='json')
        self.assertEqual(result.status_code, 409)

    def test_only_donor_can_confirm_collection(self):
        reservation = self.claim()
        result = self.api.post(f'/api/reservations/{reservation.pk}/collect/', {}, format='json')
        self.assertEqual(result.status_code, 403)
        self.assertFalse(Handover.objects.exists())

    def test_outsider_cannot_read_or_cancel_reservation(self):
        reservation = self.claim()
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get(f'/api/reservations/{reservation.pk}/').status_code, 404)
        self.assertEqual(self.api.post(f'/api/reservations/{reservation.pk}/cancel/').status_code, 404)
        self.assertEqual(self.api.get('/api/reservations/').data['count'], 0)

    def test_failed_insert_rolls_back_listing_state(self):
        with patch('exchange.services.Reservation.objects.create', side_effect=RuntimeError('Simulated insertion failure')):
            with self.assertRaises(RuntimeError):
                self.claim()
        self.part.refresh_from_db()
        self.assertEqual(self.part.status, 'available')

    def test_search_supports_model_and_exact_code(self):
        create_part(self.donor, title='Other item', part_code='LCD-TEST-010', supported_models='Different model')
        result = self.api.get('/api/parts/', {'part_code': 'lcd-test-01'})
        self.assertEqual(result.data['count'], 1)
        result = self.api.get('/api/parts/', {'q': 'DemoModel A'})
        self.assertEqual(result.data['count'], 1)

    def test_api_lifecycle_and_handover_serialization(self):
        result = self.api.post('/api/reservations/', {'part_id': self.part.pk, 'compatibility_confirmed': True, 'repair_note': 'A repair'}, format='json')
        self.assertEqual(result.status_code, 201)
        reservation_id = result.data['id']
        self.api.force_authenticate(self.donor)
        result = self.api.post(f'/api/reservations/{reservation_id}/collect/', {'note': 'Collected'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['handover']['note'], 'Collected')
        self.assertEqual(result.data['part']['status'], 'collected')

    def test_anonymous_cannot_mutate_data(self):
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get('/api/parts/').status_code, 200)
        self.assertEqual(self.api.post('/api/reservations/', {'part_id': self.part.pk}, format='json').status_code, 401)

    def test_report_is_private_and_reviewable(self):
        result = self.api.post('/api/reports/', {'part': self.part.pk, 'reason': 'mismatch', 'details': 'Model does not match.'}, format='json')
        self.assertEqual(result.status_code, 201)
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get('/api/reports/').data['count'], 0)
        self.assertEqual(Report.objects.count(), 1)

    def test_web_pages_render_for_each_account(self):
        for user in [None, self.donor, self.repairer]:
            if user:
                self.client.force_login(user)
            for url in ['/', self.part.get_absolute_url(), '/how-it-works/', '/developer/', '/api/']:
                with self.subTest(user=user, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
            if user:
                for url in ['/dashboard/', '/parts/new/']:
                    self.assertEqual(self.client.get(url).status_code, 200)
                self.client.logout()
        self.assertEqual(self.client.get('/login/').status_code, 200)
        self.assertEqual(self.client.get('/signup/').status_code, 200)

    def test_web_reservation_errors_stay_visible(self):
        self.client.force_login(self.repairer)
        response = self.client.post(reverse('part-reserve', args=[self.part.pk]), {'repair_note': 'No confirmation'})
        self.assertContains(response, 'This field is required.')
        self.assertFalse(Reservation.objects.exists())

    def test_web_mutations_use_post_and_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.repairer)
        self.assertEqual(csrf_client.post(reverse('part-reserve', args=[self.part.pk]), {'compatibility_confirmed': True}).status_code, 403)
        self.assertEqual(csrf_client.get(reverse('part-reserve', args=[self.part.pk])).status_code, 405)
        self.client.force_login(self.repairer)
        self.assertEqual(self.client.get('/logout/').status_code, 405)

    def test_reservation_is_visible_in_both_dashboards(self):
        reservation = self.claim()
        for user in [self.donor, self.repairer]:
            self.client.force_login(user)
            self.assertContains(self.client.get('/dashboard/'), f'RES-{reservation.pk:04d}')

    def test_api_token_authentication(self):
        client = APIClient()
        token_response = client.post('/api/token/', {'username': 'testrepairer', 'password': 'Test-Repairer-2026!'})
        self.assertEqual(token_response.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION='Token ' + token_response.data['token'])
        self.assertEqual(client.get('/api/reservations/').status_code, 200)

    def test_new_account_can_publish_listing(self):
        result = self.client.post('/signup/', {'username': 'newmember', 'password1': 'Uncommon-Repair-2026!', 'password2': 'Uncommon-Repair-2026!'})
        self.assertEqual(result.status_code, 302)
        payload = {'title': 'My spare keyboard', 'manufacturer': 'DemoMaker', 'part_code': 'kbd-2', 'category': 'keyboard', 'condition': 'untested', 'supported_models': 'DemoModel K', 'description': 'Spare component', 'pickup_area': 'Repair club'}
        result = self.client.post('/parts/new/', payload)
        self.assertEqual(result.status_code, 302)
        part = PartListing.objects.get(part_code='KBD-2')
        self.assertEqual(part.owner.username, 'newmember')

    def test_complete_handover_through_html_forms(self):
        self.client.force_login(self.repairer)
        result = self.client.post(reverse('part-reserve', args=[self.part.pk]), {
            'compatibility_confirmed': 'on', 'repair_note': 'Matching model checked.',
        }, follow=True)
        self.assertContains(result, 'Part reserved.')
        reservation = Reservation.objects.get(part=self.part)
        self.client.force_login(self.donor)
        self.assertContains(self.client.get('/dashboard/'), 'Matching model checked.')
        result = self.client.post(reverse('reservation-collect', args=[reservation.pk]), {'note': 'Collected by repairer.'}, follow=True)
        self.assertContains(result, 'Collection confirmed.')
        self.assertContains(result, 'Collected by repairer.')
        self.client.force_login(self.repairer)
        self.assertContains(self.client.get('/dashboard/'), 'Collected by repairer.')

    def test_malformed_withdrawal_id_returns_404(self):
        self.assertEqual(self.api.post('/api/parts/not-an-id/withdraw/').status_code, 404)


class ConcurrentClaimTests(TransactionTestCase):
    """Use independent DB connections and a real file-backed SQLite test database."""
    def setUp(self):
        self.donor = User.objects.create_user('concurrent-donor')
        self.first = User.objects.create_user('first-repairer')
        self.second = User.objects.create_user('second-repairer')
        self.part = create_part(self.donor)

    def test_two_simultaneous_claims_create_one_reservation(self):
        barrier = Barrier(2)
        part_id = self.part.pk

        def attempt(user_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                barrier.wait(timeout=10)
                try:
                    reserve_part(part_id=part_id, user=user, compatibility_confirmed=True)
                    return 201
                except ExchangeError as error:
                    return error.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, self.first.pk), pool.submit(attempt, self.second.pk)]
            results = [future.result(timeout=25) for future in futures]
        self.assertCountEqual(results, [201, 409])
        self.assertEqual(Reservation.objects.filter(part=self.part, status='active').count(), 1)
        self.part.refresh_from_db()
        self.assertEqual(self.part.status, 'reserved')
