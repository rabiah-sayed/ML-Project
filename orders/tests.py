from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Address, Wallet
from catalog.models import Category, Product

from .models import Order, Trigger, WishlistItem
from .services import check_and_fire_triggers, fire_trigger, progress_order_statuses


def _make_product(name='Widget', price='1000.00'):
    category, _ = Category.objects.get_or_create(name='Test Category')
    return Product.objects.create(
        name=name, category=category, base_price=Decimal(price),
        current_price=Decimal(price), stock=50,
    )


class TriggerFiringTests(TestCase):
    """Covers the reported bug: a trigger should fire (status ->
    'fired', an Order created) as soon as the product's current price
    reaches the target -- and only then, not before.
    """

    def setUp(self):
        self.user = User.objects.create_user('triguser', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.product = _make_product(price='1000.00')

    def _make_trigger(self, target):
        return Trigger.objects.create(
            user=self.user, product=self.product, target_price=Decimal(target),
            payment_method='cod', address=self.address,
        )

    def test_does_not_fire_while_price_above_target(self):
        trigger = self._make_trigger('900.00')  # target below current price (1000)
        fired = check_and_fire_triggers(Trigger.objects.filter(pk=trigger.pk))
        self.assertEqual(fired, [])
        trigger.refresh_from_db()
        self.assertEqual(trigger.status, 'active')
        self.assertEqual(Order.objects.count(), 0)

    def test_fires_when_price_drops_to_or_below_target(self):
        trigger = self._make_trigger('1000.00')
        self.product.current_price = Decimal('950.00')
        self.product.save(update_fields=['current_price'])

        fired = check_and_fire_triggers(Trigger.objects.filter(pk=trigger.pk))

        self.assertEqual(len(fired), 1)
        trigger.refresh_from_db()
        self.assertEqual(trigger.status, 'fired')
        order = Order.objects.get(trigger=trigger)
        self.assertEqual(order.status, 'pending_cancellation')
        self.assertEqual(order.price_paid, Decimal('950.00'))

    def test_fired_trigger_is_not_fired_again(self):
        trigger = self._make_trigger('1000.00')
        self.product.current_price = Decimal('950.00')
        self.product.save(update_fields=['current_price'])

        check_and_fire_triggers(Trigger.objects.filter(pk=trigger.pk))
        fired_again = check_and_fire_triggers(Trigger.objects.filter(pk=trigger.pk))

        self.assertEqual(fired_again, [])
        self.assertEqual(Order.objects.filter(trigger=trigger).count(), 1)

    def test_fire_trigger_sends_email(self):
        self.user.email = 'triguser@example.com'
        self.user.save(update_fields=['email'])
        trigger = self._make_trigger('1000.00')

        fire_trigger(trigger)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.product.name, mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['triguser@example.com'])


class CheckoutAtomicityTests(TestCase):
    """Regression coverage for a real bug: checking out a multi-item
    cart with wallet payment deducted funds and created orders for
    earlier items even when a later item failed for insufficient
    balance -- the checkout wasn't wrapped in a transaction.
    """

    def setUp(self):
        self.user = User.objects.create_user('checkoutuser', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal('1000.00'))
        self.cheap = _make_product('Cheap Item', '400.00')
        self.expensive = _make_product('Expensive Item', '5000.00')  # more than wallet balance

        self.client = Client()
        self.client.force_login(self.user)

    def test_failed_checkout_rolls_back_completely(self):
        self.client.post(f'/orders/cart/add/{self.cheap.id}/', {'qty': 1})
        self.client.post(f'/orders/cart/add/{self.expensive.id}/', {'qty': 1})

        response = self.client.post('/orders/checkout/', {
            'address': self.address.id, 'payment_method': 'wallet',
        })

        self.assertRedirects(response, '/orders/checkout/')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1000.00'), 'wallet must be untouched on a failed checkout')
        self.assertEqual(Order.objects.count(), 0, 'no orders should exist from a failed checkout')

    def test_successful_checkout_deducts_wallet_and_creates_orders(self):
        self.client.post(f'/orders/cart/add/{self.cheap.id}/', {'qty': 1})

        response = self.client.post('/orders/checkout/', {
            'address': self.address.id, 'payment_method': 'wallet',
        })

        self.assertRedirects(response, '/orders/my-orders/')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('600.00'))
        self.assertEqual(Order.objects.count(), 1)


class OrderCancellationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cancelluser', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.product = _make_product()

    def _make_order(self, created_at):
        order = Order.objects.create(
            user=self.user, product=self.product, price_paid=self.product.current_price,
            status='pending_cancellation', payment_method='cod', address=self.address,
        )
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        order.refresh_from_db()
        return order

    def test_cancellable_within_48h_window(self):
        order = self._make_order(timezone.now() - timezone.timedelta(hours=1))
        self.assertTrue(order.is_cancellable)

    def test_not_cancellable_after_48h_window(self):
        order = self._make_order(timezone.now() - timezone.timedelta(hours=49))
        self.assertFalse(order.is_cancellable)

    def test_confirm_pending_orders_flips_status_after_window(self):
        from .tasks import confirm_pending_orders

        self._make_order(timezone.now() - timezone.timedelta(hours=49))
        confirmed = confirm_pending_orders()

        self.assertEqual(confirmed, 1)
        self.assertEqual(Order.objects.first().status, 'confirmed')


class OrderStatusProgressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('progressuser', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.product = _make_product()

    def _make_order(self, status, created_at):
        order = Order.objects.create(
            user=self.user, product=self.product, price_paid=self.product.current_price,
            status=status, payment_method='cod', address=self.address,
        )
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        order.refresh_from_db()
        return order

    def test_placed_order_confirms_after_2h(self):
        """A directly-checked-out order ('placed') has no cancellation
        window to wait out -- it should still progress, just faster than
        a trigger-fired order's 48h confirm_pending_orders path."""
        order = self._make_order('placed', timezone.now() - timezone.timedelta(hours=3))
        confirmed, shipped, delivered = progress_order_statuses()

        self.assertEqual(confirmed, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')

    def test_placed_order_not_yet_confirmed_before_2h(self):
        order = self._make_order('placed', timezone.now() - timezone.timedelta(minutes=30))
        progress_order_statuses()

        order.refresh_from_db()
        self.assertEqual(order.status, 'placed')

    def test_confirmed_order_ships_after_72h(self):
        order = self._make_order('confirmed', timezone.now() - timezone.timedelta(hours=73))
        confirmed, shipped, delivered = progress_order_statuses()

        self.assertEqual(shipped, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')

    def test_confirmed_order_not_yet_shipped_before_72h(self):
        order = self._make_order('confirmed', timezone.now() - timezone.timedelta(hours=10))
        progress_order_statuses()

        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')

    def test_shipped_order_delivers_after_120h(self):
        order = self._make_order('shipped', timezone.now() - timezone.timedelta(hours=121))
        confirmed, shipped, delivered = progress_order_statuses()

        self.assertEqual(delivered, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

    def test_pending_cancellation_order_is_not_touched(self):
        order = self._make_order('pending_cancellation', timezone.now() - timezone.timedelta(hours=200))
        progress_order_statuses()

        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_cancellation')


class OrderTrackingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('trackuser', password='x')
        self.other_user = User.objects.create_user('trackuser2', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.product = _make_product()

    def _make_order(self, status, created_at, user=None):
        order = Order.objects.create(
            user=user or self.user, product=self.product, price_paid=self.product.current_price,
            status=status, payment_method='cod', address=self.address,
        )
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        order.refresh_from_db()
        return order

    def test_stages_for_a_placed_order_only_first_stage_reached(self):
        from .services import order_tracking_stages

        order = self._make_order('placed', timezone.now())
        stages = order_tracking_stages(order)

        self.assertEqual([s['key'] for s in stages if s['reached']], ['placed'])
        self.assertTrue(stages[0]['current'])

    def test_stages_for_a_delivered_order_all_reached(self):
        from .services import order_tracking_stages

        order = self._make_order('delivered', timezone.now() - timezone.timedelta(hours=200))
        stages = order_tracking_stages(order)

        self.assertTrue(all(s['reached'] for s in stages))
        self.assertTrue(stages[-1]['current'])

    def test_stages_for_pending_cancellation_treated_as_placed(self):
        from .services import order_tracking_stages

        order = self._make_order('pending_cancellation', timezone.now())
        stages = order_tracking_stages(order)

        self.assertEqual([s['key'] for s in stages if s['reached']], ['placed'])

    def test_tracking_view_advances_status_and_renders(self):
        order = self._make_order('confirmed', timezone.now() - timezone.timedelta(hours=73))
        c = Client()
        c.force_login(self.user)

        response = c.get(f'/orders/my-orders/{order.id}/')

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')
        self.assertContains(response, 'Shipped')

    def test_tracking_view_rejects_other_users_order(self):
        order = self._make_order('placed', timezone.now())
        c = Client()
        c.force_login(self.other_user)

        response = c.get(f'/orders/my-orders/{order.id}/')

        self.assertEqual(response.status_code, 404)

    def test_cancelled_order_shows_no_stepper(self):
        order = self._make_order('cancelled', timezone.now())
        c = Client()
        c.force_login(self.user)

        response = c.get(f'/orders/my-orders/{order.id}/')

        self.assertContains(response, 'Cancelled')
        self.assertNotContains(response, 'tracking-stepper')


class WishlistTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('wishuser', password='x')
        self.product = _make_product()

    def test_toggle_adds_then_removes(self):
        c = Client()
        c.force_login(self.user)

        c.post(f'/orders/wishlist/toggle/{self.product.id}/')
        self.assertTrue(WishlistItem.objects.filter(user=self.user, product=self.product).exists())

        c.post(f'/orders/wishlist/toggle/{self.product.id}/')
        self.assertFalse(WishlistItem.objects.filter(user=self.user, product=self.product).exists())

    def test_wishlist_list_shows_only_own_items(self):
        other_user = User.objects.create_user('wishuser2', password='x')
        WishlistItem.objects.create(user=self.user, product=self.product)
        other_product = _make_product(name='Other Widget')
        WishlistItem.objects.create(user=other_user, product=other_product)

        c = Client()
        c.force_login(self.user)
        response = c.get('/orders/wishlist/')

        self.assertContains(response, self.product.name)
        self.assertNotContains(response, other_product.name)


class AdvanceOrderStatusTests(TestCase):
    """orders.services.advance_order_status: the manual, admin-triggered
    equivalent of progress_order_statuses -- pushes one order forward
    immediately instead of waiting out the simulated timeline."""

    def setUp(self):
        self.user = User.objects.create_user('advanceuser', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.product = _make_product()

    def _make_order(self, status):
        return Order.objects.create(
            user=self.user, product=self.product, price_paid=self.product.current_price,
            status=status, payment_method='cod', address=self.address,
        )

    def test_advances_placed_to_confirmed(self):
        from .services import advance_order_status
        order = self._make_order('placed')

        result = advance_order_status(order)

        self.assertEqual(result, 'confirmed')
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')

    def test_advances_pending_cancellation_to_confirmed(self):
        """Skips straight to 'confirmed', bypassing the 48h cancellation
        window -- that's the point of a manual admin override."""
        from .services import advance_order_status
        order = self._make_order('pending_cancellation')

        result = advance_order_status(order)

        self.assertEqual(result, 'confirmed')

    def test_advances_through_full_lifecycle(self):
        from .services import advance_order_status
        order = self._make_order('placed')

        for expected in ['confirmed', 'shipped', 'delivered']:
            self.assertEqual(advance_order_status(order), expected)

    def test_delivered_order_cannot_advance_further(self):
        from .services import advance_order_status
        order = self._make_order('delivered')

        self.assertIsNone(advance_order_status(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

    def test_cancelled_order_cannot_advance(self):
        from .services import advance_order_status
        order = self._make_order('cancelled')

        self.assertIsNone(advance_order_status(order))


class OrderAdminActionTests(TestCase):
    """The Django Admin login IS the admin login (createsuperuser) --
    this exercises the "Advance to next status" action that lets staff
    push fulfillment forward from there without hand-editing fields."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser('orderadmin', 'admin@example.com', 'x')
        self.user = User.objects.create_user('adminactiontarget', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')
        self.product = _make_product()
        self.order = Order.objects.create(
            user=self.user, product=self.product, price_paid=self.product.current_price,
            status='placed', payment_method='cod', address=self.address,
        )

    def test_advance_action_pushes_order_forward(self):
        c = Client()
        c.force_login(self.admin_user)

        response = c.post('/admin/orders/order/', {
            'action': 'advance_to_next_status',
            '_selected_action': [str(self.order.id)],
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'confirmed')

    def test_order_change_form_is_read_only(self):
        c = Client()
        c.force_login(self.admin_user)

        response = c.get(f'/admin/orders/order/{self.order.id}/change/')

        self.assertEqual(response.status_code, 200)


class CartSavingsTests(TestCase):
    """cart_detail's 'savings' is base_price_total - current_price_total
    (orders/views.py) -- positive when the demand-curve price has dipped
    below base_price (a real discount), but the curve fluctuates *above*
    base_price just as often, making savings negative. The template used
    to render that as a literal '-' + a negative number ("--268.37") and
    label a markup as a discount -- only ever surfaced once prices
    actually moved on page load (catalog.services.maybe_update_prices),
    since before that current_price was static for the life of a test/demo.
    """

    def setUp(self):
        self.user = User.objects.create_user('cartuser', password='x')

    def _add_to_cart(self, client, product):
        client.post(f'/orders/cart/add/{product.id}/', {'qty': 1})

    def test_savings_row_hidden_when_price_is_above_base_price(self):
        product = _make_product(price='1000.00')
        product.current_price = Decimal('1200.00')  # demand curve pushed it above base_price
        product.save(update_fields=['current_price'])

        c = Client()
        c.force_login(self.user)
        self._add_to_cart(c, product)

        response = c.get('/orders/cart/')

        self.assertNotContains(response, 'Savings')
        self.assertNotContains(response, '--200.00')

    def test_savings_row_shown_when_price_is_a_genuine_discount(self):
        product = _make_product(price='1000.00')
        product.current_price = Decimal('800.00')
        product.save(update_fields=['current_price'])

        c = Client()
        c.force_login(self.user)
        self._add_to_cart(c, product)

        response = c.get('/orders/cart/')

        self.assertContains(response, 'Savings')
        self.assertContains(response, '-200.00')
        self.assertNotContains(response, 'name="status"')
