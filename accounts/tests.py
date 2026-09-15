from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import Wallet


class WalletTests(TestCase):
    """Regression coverage for a real bug: Wallet.balance is a Decimal
    field, and Decimal + float raises TypeError in Python. add_funds/
    deduct must accept a plain float (as posted from a form) without
    that blowing up -- it silently did, since the view's broad
    `except (TypeError, ValueError)` swallowed it and just showed
    'Enter a valid amount' while the balance never actually changed.
    """

    def setUp(self):
        self.user = User.objects.create_user('walletuser', password='x')
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal('100.00'))

    def test_add_funds_accepts_float(self):
        self.wallet.add_funds(50.5)
        self.assertEqual(self.wallet.balance, Decimal('150.50'))

    def test_deduct_accepts_float(self):
        self.wallet.deduct(40.25)
        self.assertEqual(self.wallet.balance, Decimal('59.75'))

    def test_deduct_raises_on_insufficient_balance(self):
        with self.assertRaises(ValueError):
            self.wallet.deduct(1000.0)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100.00'))


class SharedLoginRoutingTests(TestCase):
    """One login form for everyone (SiteLoginView): staff land on the
    Admin dashboard, customers land on the shop -- and a logged-out
    visit to any /admin/... page reaches that same shared form instead
    of Django's separate built-in admin login page.
    """

    def setUp(self):
        self.staff_user = User.objects.create_superuser('siteadmin', 'a@example.com', 'x')
        self.customer = User.objects.create_user('sitecustomer', password='x')

    def test_staff_login_redirects_to_admin_dashboard(self):
        response = self.client.post('/login/', {'username': 'siteadmin', 'password': 'x'})
        self.assertRedirects(response, '/admin/', fetch_redirect_response=False)

    def test_customer_login_redirects_to_shop(self):
        response = self.client.post('/login/', {'username': 'sitecustomer', 'password': 'x'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_explicit_next_wins_over_staff_default(self):
        response = self.client.post('/login/?next=/orders/wishlist/', {'username': 'siteadmin', 'password': 'x'})
        self.assertRedirects(response, '/orders/wishlist/', fetch_redirect_response=False)

    def test_logged_out_admin_visit_reaches_shared_login_page(self):
        c = Client()
        response = c.get('/admin/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_staff_session_reaches_admin_directly_after_shared_login(self):
        c = Client()
        c.force_login(self.staff_user)
        response = c.get('/admin/')
        self.assertEqual(response.status_code, 200)
