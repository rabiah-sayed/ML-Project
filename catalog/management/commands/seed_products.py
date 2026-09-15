import csv
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from catalog.models import Category, Product

CATEGORY_PRODUCT_TYPES = {
    'Electronics': [
        'Smartphone', 'Laptop', 'Wireless Earbuds', 'Smartwatch', 'Tablet',
        'Bluetooth Speaker', 'Wi-Fi Router', 'Power Bank', 'DSLR Camera',
        'Monitor', 'Mechanical Keyboard', 'Wireless Mouse', 'Home Theater System',
        'Gaming Console', 'Action Camera', 'Fitness Tracker', 'External SSD',
        'Noise Cancelling Headphones', 'Smart TV', 'Webcam',
    ],
    'Fashion': [
        'Running Shoes', 'Denim Jacket', 'Cotton T-Shirt', 'Formal Shirt',
        'Leather Wallet', 'Sunglasses', 'Analog Watch', 'Backpack',
        'Sneakers', 'Hoodie', 'Chino Trousers', 'Leather Belt',
        'Sports Cap', 'Handbag', 'Rain Jacket', 'Wool Sweater',
        'Ankle Boots', 'Silk Scarf', 'Sports Socks (3-pack)', 'Slim Fit Jeans',
    ],
    'Home & Kitchen': [
        'Non-Stick Cookware Set', 'Air Fryer', 'Blender', 'Electric Kettle',
        'Microwave Oven', 'Vacuum Cleaner', 'Bedsheet Set', 'Study Lamp',
        'Dinner Set', 'Pressure Cooker', 'Coffee Maker', 'Toaster',
        'Ceiling Fan', 'Storage Organizer Box', 'Curtain Set', 'Water Purifier',
        'Cushion Cover Set', 'Induction Cooktop', 'Wall Clock', 'Knife Set',
    ],
    'Books': [
        'Self-Help Bestseller', 'Fantasy Novel', 'Mystery Thriller',
        'Science Fiction Novel', 'Biography', 'History Book',
        'Personal Finance Guide', 'Cookbook', 'Poetry Collection',
        'Programming Handbook', 'Business Strategy Book', 'Children\'s Picture Book',
        'Graphic Novel', 'Travel Guide', 'Philosophy Book', 'Romance Novel',
        'Productivity Guide', 'Language Learning Book', 'Classic Literature', 'Comic Book',
    ],
    'Sports & Fitness': [
        'Yoga Mat', 'Adjustable Dumbbell Set', 'Cricket Bat', 'Football',
        'Badminton Racquet', 'Resistance Bands Set', 'Skipping Rope',
        'Cycling Helmet', 'Treadmill', 'Gym Gloves', 'Water Bottle (Sports)',
        'Table Tennis Paddle Set', 'Camping Tent', 'Trekking Backpack',
        'Protein Shaker', 'Foam Roller', 'Basketball', 'Swimming Goggles',
        'Fitness Resistance Tube', 'Exercise Bike',
    ],
}

# Per-type (not per-category) price ranges -- a flat category-wide range
# let a Power Bank and a DSLR Camera roll the same price, which is why a
# power bank could come out at 80,000. Every one of the 100 product types
# above gets its own realistic (low, high) range instead.
PRICE_RANGES = {
    # Electronics
    'Smartphone': (8999, 149999), 'Laptop': (24999, 149999),
    'Wireless Earbuds': (999, 14999), 'Smartwatch': (1499, 34999),
    'Tablet': (7999, 89999), 'Bluetooth Speaker': (799, 11999),
    'Wi-Fi Router': (899, 7999), 'Power Bank': (599, 3499),
    'DSLR Camera': (24999, 149999), 'Monitor': (5999, 59999),
    'Mechanical Keyboard': (1499, 14999), 'Wireless Mouse': (299, 3999),
    'Home Theater System': (4999, 59999), 'Gaming Console': (24999, 64999),
    'Action Camera': (4999, 44999), 'Fitness Tracker': (1199, 7999),
    'External SSD': (2499, 19999), 'Noise Cancelling Headphones': (2499, 34999),
    'Smart TV': (14999, 119999), 'Webcam': (799, 7999),

    # Fashion
    'Running Shoes': (999, 7999), 'Denim Jacket': (999, 5999),
    'Cotton T-Shirt': (299, 1999), 'Formal Shirt': (599, 3499),
    'Leather Wallet': (399, 2999), 'Sunglasses': (399, 5999),
    'Analog Watch': (799, 14999), 'Backpack': (599, 4999),
    'Sneakers': (999, 7999), 'Hoodie': (799, 3499),
    'Chino Trousers': (799, 3499), 'Leather Belt': (399, 2499),
    'Sports Cap': (249, 1499), 'Handbag': (799, 7999),
    'Rain Jacket': (999, 4999), 'Wool Sweater': (799, 3999),
    'Ankle Boots': (1499, 7999), 'Silk Scarf': (399, 2999),
    'Sports Socks (3-pack)': (199, 999), 'Slim Fit Jeans': (899, 3999),

    # Home & Kitchen
    'Non-Stick Cookware Set': (999, 7999), 'Air Fryer': (3499, 14999),
    'Blender': (1299, 7999), 'Electric Kettle': (799, 3999),
    'Microwave Oven': (4999, 24999), 'Vacuum Cleaner': (3999, 29999),
    'Bedsheet Set': (699, 4999), 'Study Lamp': (399, 3499),
    'Dinner Set': (999, 7999), 'Pressure Cooker': (999, 4999),
    'Coffee Maker': (1999, 14999), 'Toaster': (899, 3999),
    'Ceiling Fan': (1999, 7999), 'Storage Organizer Box': (299, 2499),
    'Curtain Set': (599, 3999), 'Water Purifier': (3999, 24999),
    'Cushion Cover Set': (299, 1999), 'Induction Cooktop': (1499, 6999),
    'Wall Clock': (299, 2499), 'Knife Set': (599, 3999),

    # Books
    'Self-Help Bestseller': (199, 999), 'Fantasy Novel': (249, 1299),
    'Mystery Thriller': (199, 999), 'Science Fiction Novel': (249, 1299),
    'Biography': (299, 1499), 'History Book': (299, 1499),
    'Personal Finance Guide': (249, 1199), 'Cookbook': (349, 1499),
    'Poetry Collection': (149, 799), 'Programming Handbook': (399, 1999),
    'Business Strategy Book': (299, 1499), "Children's Picture Book": (149, 699),
    'Graphic Novel': (299, 1299), 'Travel Guide': (249, 1199),
    'Philosophy Book': (299, 1499), 'Romance Novel': (199, 999),
    'Productivity Guide': (249, 1199), 'Language Learning Book': (299, 1499),
    'Classic Literature': (149, 899), 'Comic Book': (149, 799),

    # Sports & Fitness
    'Yoga Mat': (399, 2499), 'Adjustable Dumbbell Set': (2999, 24999),
    'Cricket Bat': (999, 14999), 'Football': (599, 3999),
    'Badminton Racquet': (799, 7999), 'Resistance Bands Set': (399, 2499),
    'Skipping Rope': (199, 1199), 'Cycling Helmet': (999, 7999),
    'Treadmill': (14999, 89999), 'Gym Gloves': (299, 1999),
    'Water Bottle (Sports)': (199, 1499), 'Table Tennis Paddle Set': (599, 3999),
    'Camping Tent': (2999, 19999), 'Trekking Backpack': (1999, 11999),
    'Protein Shaker': (199, 1199), 'Foam Roller': (599, 2999),
    'Basketball': (799, 3999), 'Swimming Goggles': (399, 2499),
    'Fitness Resistance Tube': (299, 1999), 'Exercise Bike': (8999, 59999),
}


class Command(BaseCommand):
    help = (
        'Seed the catalog with products across 5 categories. Reads from a '
        '--csv file (columns: name,category,price) if given -- e.g. a '
        'Kaggle Flipkart/Amazon products export -- otherwise generates '
        'realistic products via Faker brand names + category templates.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, default=None, help='Path to a product CSV to import from')
        parser.add_argument('--per-category', type=int, default=130, help='Products per category when generating synthetically')
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, **options):
        random.seed(options['seed'])
        fake = Faker()
        Faker.seed(options['seed'])

        if options['csv']:
            created = self._seed_from_csv(options['csv'])
        else:
            created = self._seed_synthetic(fake, options['per_category'])

        self.stdout.write(self.style.SUCCESS(f'Seeded {created} products.'))

    def _seed_from_csv(self, path):
        created = 0
        with open(path, newline='', encoding='utf-8') as f, transaction.atomic():
            reader = csv.DictReader(f)
            for row in reader:
                category, _ = Category.objects.get_or_create(name=row['category'].strip())
                price = float(row.get('price') or random.uniform(199, 9999))
                Product.objects.get_or_create(
                    name=row['name'].strip(),
                    category=category,
                    defaults={
                        'base_price': round(price, 2),
                        'current_price': round(price, 2),
                        'description': row.get('description', ''),
                        'stock': random.randint(10, 300),
                    },
                )
                created += 1
        return created

    def _seed_synthetic(self, fake, per_category):
        created = 0
        with transaction.atomic():
            for category_name, product_types in CATEGORY_PRODUCT_TYPES.items():
                category, _ = Category.objects.get_or_create(name=category_name)
                seen_names = set()
                products = []

                while len(products) < per_category:
                    brand = fake.company().split(' ')[0].rstrip(',.')
                    product_type = random.choice(product_types)
                    name = f'{brand} {product_type}'
                    if name in seen_names:
                        name = f'{name} ({fake.word().capitalize()})'
                    seen_names.add(name)

                    low, high = PRICE_RANGES[product_type]
                    price = round(random.uniform(low, high), 2)
                    products.append(Product(
                        name=name,
                        category=category,
                        base_price=price,
                        current_price=price,
                        description=fake.sentence(nb_words=12),
                        stock=random.randint(10, 300),
                    ))

                Product.objects.bulk_create(products)
                created += len(products)
        return created
