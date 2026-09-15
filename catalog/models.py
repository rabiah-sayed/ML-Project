from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    stock = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def lowest_price(self):
        agg = self.price_logs.aggregate(models.Min('price'))
        return agg['price__min'] or self.current_price

    @property
    def discount_percent(self):
        if self.base_price and self.current_price < self.base_price:
            return round((1 - float(self.current_price) / float(self.base_price)) * 100)
        return 0

    def active_sale(self):
        today = timezone.localdate()
        return Sale.objects.filter(
            start_date__lte=today, end_date__gte=today,
        ).filter(models.Q(category=self.category) | models.Q(category__isnull=True)).order_by(
            '-discount_percent'
        ).first()

    @property
    def average_rating(self):
        return self.reviews.aggregate(models.Avg('rating'))['rating__avg']

    @property
    def review_count(self):
        return self.reviews.count()


class PriceLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_logs')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [models.Index(fields=['product', 'timestamp'])]

    def __str__(self):
        return f'{self.product} @ {self.price} ({self.timestamp:%Y-%m-%d %H:%M})'


class Sale(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='sales',
        null=True, blank=True, help_text='Leave blank to apply to all categories',
    )
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        scope = self.category.name if self.category else 'All categories'
        return f'{self.name} ({scope}, -{self.discount_percent}%)'

    def is_active(self, on_date=None):
        on_date = on_date or timezone.localdate()
        return self.start_date <= on_date <= self.end_date


class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['product', 'user'], name='unique_review_per_user_product'),
        ]

    def __str__(self):
        return f'{self.user} rated {self.product} {self.rating}/5'
