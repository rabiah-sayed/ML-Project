"""Hand-mapped SVG line icons for every product type in seed_products.py.

Why this exists: a free keyword-tagged photo API (loremflickr) cannot
guarantee the returned photo actually matches the product name -- and it
didn't. Rather than gamble on photo relevance, every exact product type
string is mapped here to a specific, correct icon, so a "Cricket Bat" is
always guaranteed to render a bat, never an arbitrary photo. This is the
default product visual; a real photo uploaded via Django Admin
(Product.image) still takes priority over it.
"""

# Each value is the *inner* markup of a 48x48 viewBox line icon
# (stroke="currentColor", fill="none" unless noted). Kept intentionally
# simple/geometric -- these are illustrative placeholders, not attempts
# at photorealism.
ICON_SVGS = {
    # --- Electronics ---
    'phone': '<rect x="16" y="4" width="16" height="40" rx="3"/><line x1="16" y1="35" x2="32" y2="35"/><circle cx="24" cy="39.5" r="1.4" fill="currentColor" stroke="none"/>',
    'laptop': '<rect x="8" y="8" width="32" height="21" rx="2"/><path d="M4 33h40l-3.5 6.5a2 2 0 0 1-1.8 1.1H9.3a2 2 0 0 1-1.8-1.1z"/>',
    'headphones': '<path d="M8 26v-3a16 16 0 0 1 32 0v3"/><rect x="5" y="24" width="9" height="15" rx="3.5"/><rect x="34" y="24" width="9" height="15" rx="3.5"/>',
    'smartwatch': '<rect x="15" y="15" width="18" height="18" rx="4"/><path d="M19 15V9a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v6"/><path d="M19 33v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-6"/><path d="M24 21v3l2 2"/>',
    'tablet': '<rect x="11" y="4" width="26" height="40" rx="3"/><circle cx="24" cy="38" r="1.5" fill="currentColor" stroke="none"/>',
    'speaker': '<rect x="13" y="4" width="22" height="40" rx="4"/><circle cx="24" cy="15" r="4"/><circle cx="24" cy="30" r="7"/><circle cx="24" cy="30" r="2.5" fill="currentColor" stroke="none"/>',
    'router': '<rect x="6" y="20" width="36" height="14" rx="3"/><path d="M16 20v-6"/><path d="M24 20v-9"/><path d="M32 20v-6"/><circle cx="14" cy="27" r="1.3" fill="currentColor" stroke="none"/><circle cx="20" cy="27" r="1.3" fill="currentColor" stroke="none"/>',
    'battery': '<rect x="13" y="6" width="22" height="36" rx="4"/><rect x="20" y="3" width="8" height="4" rx="1"/><path d="M27 13l-8 13h6l-2 9 9-15h-6z" fill="currentColor" stroke="none"/>',
    'camera': '<rect x="5" y="14" width="38" height="24" rx="3"/><circle cx="24" cy="26" r="8"/><circle cx="24" cy="26" r="3" fill="currentColor" stroke="none"/><path d="M17 14l2.5-5h9l2.5 5"/>',
    'screen': '<rect x="6" y="8" width="36" height="24" rx="2"/><line x1="24" y1="32" x2="24" y2="39"/><line x1="15" y1="40.5" x2="33" y2="40.5"/>',
    'keyboard': '<rect x="4" y="14" width="40" height="20" rx="3"/><line x1="10" y1="20" x2="14" y2="20"/><line x1="18" y1="20" x2="22" y2="20"/><line x1="26" y1="20" x2="30" y2="20"/><line x1="34" y1="20" x2="38" y2="20"/><line x1="10" y1="27.5" x2="30" y2="27.5"/>',
    'mouse': '<rect x="15" y="6" width="18" height="30" rx="9"/><line x1="24" y1="6" x2="24" y2="17"/>',
    'controller': '<path d="M13 18h9l2-2 2 2h9a7 7 0 0 1 7 7v5a5 5 0 0 1-9 3l-3.5-4h-11L15 33a5 5 0 0 1-9-3v-5a7 7 0 0 1 7-7z"/><line x1="16.5" y1="23.5" x2="16.5" y2="29.5"/><line x1="13.5" y1="26.5" x2="19.5" y2="26.5"/><circle cx="34" cy="23.5" r="1.4" fill="currentColor" stroke="none"/><circle cx="30.5" cy="27" r="1.4" fill="currentColor" stroke="none"/>',
    'drive': '<rect x="10" y="9" width="28" height="30" rx="4"/><line x1="15" y1="30" x2="33" y2="30"/><circle cx="30" cy="17" r="1.6" fill="currentColor" stroke="none"/><circle cx="30" cy="23" r="1.6" fill="currentColor" stroke="none"/>',

    # --- Fashion ---
    'shoe': '<path d="M5 34h35a4 4 0 0 0 4-4c0-4-3.5-6-7.5-8l-9.5-8-4 2-8.5-2-5 4.5v9.5a6 6 0 0 0 0 6z"/><line x1="5" y1="34" x2="44" y2="34"/>',
    'boot': '<path d="M14 6h11v17l13 6.5a4 4 0 0 1 2.5 3.7V36H10V10a4 4 0 0 1 4-4z"/><line x1="10" y1="30.5" x2="40.5" y2="30.5"/>',
    'jacket': '<path d="M18 6h12l4 4 8 4.5-3.5 8-4.5-2v21.5H14V20.5l-4.5 2-3.5-8L14 10z"/><line x1="24" y1="10" x2="24" y2="41"/>',
    'shirt': '<path d="M16 6l8 4.5L32 6l8 8-6 6-2-2.3v23.8H18V17.7L16 20l-6-6z"/>',
    'trousers': '<path d="M14 6h20l1 12-2.2 24h-6L24 22l-2.8 20h-6L13 18z"/>',
    'wallet': '<rect x="6" y="14" width="36" height="24" rx="4"/><path d="M6 22h36"/><circle cx="32" cy="27" r="2" fill="currentColor" stroke="none"/>',
    'sunglasses': '<circle cx="14" cy="25" r="8"/><circle cx="34" cy="25" r="8"/><line x1="22" y1="23" x2="26" y2="23"/><line x1="6" y1="20" x2="2" y2="18"/><line x1="42" y1="20" x2="46" y2="18"/>',
    'backpack': '<rect x="10" y="14" width="28" height="28" rx="6"/><path d="M16 14v-4a8 8 0 0 1 16 0v4"/><rect x="17" y="24" width="14" height="10" rx="2"/>',
    'handbag': '<path d="M12 20h24l2 20H10z"/><path d="M18 20v-4a6 6 0 0 1 12 0v4"/>',
    'belt': '<line x1="4" y1="24" x2="44" y2="24"/><rect x="18" y="18" width="12" height="12" rx="2"/><circle cx="24" cy="24" r="2" fill="currentColor" stroke="none"/>',
    'cap': '<path d="M8 27a16 16 0 0 1 32 0z"/><path d="M4 27h16"/><line x1="24" y1="11" x2="24" y2="7"/>',
    'scarf': '<path d="M6 12c6 4 4 8 10 8s4-6 10-2 4 10 10 6"/><path d="M30 20l6 18-6 2-4-16z"/>',
    'socks': '<path d="M18 6h10v16l8 8a6 6 0 0 1 2 8 6 6 0 0 1-8 2l-14-8V6z"/>',

    # --- Home & Kitchen ---
    'pot': '<rect x="10" y="20" width="28" height="16" rx="2"/><line x1="4" y1="22" x2="10" y2="22"/><line x1="38" y1="22" x2="44" y2="22"/><ellipse cx="24" cy="20" rx="14" ry="3"/><line x1="24" y1="10" x2="24" y2="14"/><circle cx="24" cy="8" r="2"/>',
    'airfryer': '<rect x="10" y="10" width="28" height="30" rx="8"/><circle cx="24" cy="18" r="4"/><rect x="14" y="28" width="20" height="8" rx="2"/>',
    'blender': '<path d="M16 8h16l-2 26H18z"/><rect x="14" y="34" width="20" height="8" rx="2"/><line x1="20" y1="20" x2="28" y2="20"/>',
    'kettle': '<path d="M10 20a14 14 0 0 1 28 0v10a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4z"/><path d="M38 18l6-4"/><path d="M14 12a6 6 0 0 1 8-4"/><circle cx="24" cy="8" r="2"/>',
    'microwave': '<rect x="4" y="10" width="40" height="26" rx="2"/><rect x="8" y="14" width="22" height="18" rx="1"/><circle cx="36" cy="18" r="2"/><line x1="32" y1="26" x2="40" y2="26"/>',
    'vacuum': '<circle cx="17" cy="30" r="8"/><path d="M25 30h7a4 4 0 0 0 4-4V14"/><path d="M36 14h6"/><line x1="17" y1="38" x2="17" y2="42"/>',
    'bed': '<path d="M4 24h40v14H4z"/><path d="M4 24v-6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v6"/><line x1="4" y1="38" x2="4" y2="42"/><line x1="44" y1="38" x2="44" y2="42"/>',
    'lamp': '<path d="M16 6h16l4 12H12z"/><line x1="24" y1="18" x2="24" y2="38"/><line x1="16" y1="42" x2="32" y2="42"/>',
    'plate': '<circle cx="24" cy="24" r="18"/><circle cx="24" cy="24" r="10"/>',
    'coffeemaker': '<path d="M14 18h20v18a4 4 0 0 1-4 4H18a4 4 0 0 1-4-4z"/><rect x="10" y="8" width="28" height="8" rx="2"/><line x1="24" y1="16" x2="24" y2="18"/>',
    'toaster': '<rect x="6" y="14" width="36" height="20" rx="4"/><line x1="16" y1="14" x2="16" y2="8"/><line x1="24" y1="14" x2="24" y2="8"/><line x1="40" y1="24" x2="44" y2="24"/>',
    'fan': '<circle cx="24" cy="24" r="3"/><path d="M24 24l16-4a8 8 0 0 1-10 12z"/><path d="M24 24l-16 4a8 8 0 0 0 10 12z"/><path d="M24 24l4-18a8 8 0 0 0-12 10z"/>',
    'box': '<rect x="8" y="14" width="32" height="26" rx="2"/><path d="M8 14l16 8 16-8"/>',
    'curtain': '<path d="M8 6v36"/><path d="M40 6v36"/><path d="M8 6c4 8-4 8 0 16s-4 8 0 16"/><path d="M40 6c-4 8 4 8 0 16s4 8 0 16"/>',
    'waterdrop': '<path d="M24 6c8 10 14 18 14 26a14 14 0 0 1-28 0c0-8 6-16 14-26z"/>',
    'cushion': '<rect x="10" y="10" width="28" height="28" rx="6"/><line x1="10" y1="24" x2="20" y2="14"/><line x1="38" y1="24" x2="28" y2="34"/>',
    'cooktop': '<rect x="6" y="10" width="36" height="28" rx="3"/><circle cx="18" cy="24" r="6"/><circle cx="32" cy="24" r="6"/>',
    'clock': '<circle cx="24" cy="24" r="18"/><line x1="24" y1="24" x2="24" y2="14"/><line x1="24" y1="24" x2="31" y2="28"/>',
    'knife': '<path d="M8 30l24-24 8 8-24 24z"/><line x1="8" y1="30" x2="4" y2="42"/>',

    # --- Books ---
    'book': '<path d="M8 8h14a4 4 0 0 1 4 4v28a4 4 0 0 0-4-4H8z"/><path d="M40 8H26a4 4 0 0 0-4 4v28a4 4 0 0 1 4-4h14z"/>',
    'book-stack': '<rect x="8" y="30" width="32" height="8" rx="1"/><rect x="11" y="21" width="26" height="8" rx="1"/><rect x="14" y="12" width="20" height="8" rx="1"/>',

    # --- Sports & Fitness ---
    'mat': '<rect x="8" y="16" width="32" height="16" rx="4"/><line x1="14" y1="16" x2="14" y2="32"/><line x1="20" y1="16" x2="20" y2="32"/>',
    'dumbbell': '<line x1="12" y1="24" x2="36" y2="24"/><rect x="6" y="18" width="6" height="12" rx="2"/><rect x="36" y="18" width="6" height="12" rx="2"/><rect x="18" y="20" width="12" height="8" rx="2"/>',
    'bat': '<path d="M28 6l6 6-13.5 13.5-6-6z"/><path d="M20.5 25.5l-12 12a3 3 0 0 0 4 4l12-12z"/>',
    'ball': '<circle cx="24" cy="24" r="18"/><path d="M24 6v36M6 24h36M10.5 12.5c8 6 19 6 27 0M10.5 35.5c8-6 19-6 27 0"/>',
    'racquet': '<ellipse cx="21" cy="17" rx="12" ry="14"/><line x1="29.5" y1="27.5" x2="42" y2="42"/><line x1="15" y1="6" x2="27" y2="27"/><line x1="27" y1="6" x2="15" y2="27"/>',
    'paddle': '<circle cx="19" cy="18" r="14"/><line x1="27.5" y1="27.5" x2="38" y2="42"/>',
    'band': '<path d="M8 24c8-12 24-12 32 0"/><path d="M8 24c8 12 24 12 32 0"/>',
    'rope': '<path d="M8 12a30 30 0 0 0 0 24"/><path d="M40 12a30 30 0 0 1 0 24"/><line x1="8" y1="10" x2="8" y2="16"/><line x1="40" y1="10" x2="40" y2="16"/>',
    'helmet': '<path d="M8 28a16 16 0 0 1 32 0z"/><line x1="8" y1="28" x2="40" y2="28"/><path d="M18 28v-4M24 28v-6M30 28v-4"/>',
    'treadmill': '<rect x="8" y="26" width="26" height="8" rx="2"/><line x1="34" y1="14" x2="34" y2="30"/><line x1="34" y1="14" x2="40" y2="14"/><line x1="10" y1="34" x2="10" y2="40"/><line x1="30" y1="34" x2="30" y2="40"/>',
    'glove': '<path d="M14 26V10a3 3 0 0 1 6 0v10M20 20V8a3 3 0 0 1 6 0v12M26 20V9a3 3 0 0 1 6 0v13M32 22v-8a3 3 0 0 1 6 0v14a10 10 0 0 1-10 10H20a10 10 0 0 1-8-16z"/>',
    'bottle': '<path d="M20 6h8v6l3 4v26a3 3 0 0 1-3 3H20a3 3 0 0 1-3-3V16l3-4z"/><line x1="17" y1="24" x2="31" y2="24"/>',
    'tent': '<path d="M24 8l18 32H6z"/><line x1="24" y1="8" x2="24" y2="40"/><line x1="14" y1="24" x2="34" y2="24"/>',
    'shaker': '<path d="M16 10h16l2 6v22a3 3 0 0 1-3 3H17a3 3 0 0 1-3-3V16z"/><line x1="14" y1="20" x2="34" y2="20"/><rect x="17" y="4" width="14" height="6" rx="1"/>',
    'roller': '<rect x="8" y="16" width="32" height="16" rx="8"/><line x1="8" y1="20" x2="40" y2="20"/><line x1="8" y1="28" x2="40" y2="28"/>',
    'goggles': '<circle cx="15" cy="24" r="8"/><circle cx="33" cy="24" r="8"/><line x1="23" y1="22" x2="25" y2="22"/><path d="M9 18l-5-2M39 18l5-2"/>',
    'bike': '<circle cx="14" cy="34" r="7"/><circle cx="36" cy="34" r="4"/><path d="M14 34l10-18h8M24 16l10 18"/><line x1="24" y1="16" x2="24" y2="8"/><line x1="20" y1="8" x2="28" y2="8"/>',
}

TYPE_TO_ICON = {
    # Electronics
    'Smartphone': 'phone', 'Laptop': 'laptop', 'Wireless Earbuds': 'headphones',
    'Smartwatch': 'smartwatch', 'Tablet': 'tablet', 'Bluetooth Speaker': 'speaker',
    'Wi-Fi Router': 'router', 'Power Bank': 'battery', 'DSLR Camera': 'camera',
    'Monitor': 'screen', 'Mechanical Keyboard': 'keyboard', 'Wireless Mouse': 'mouse',
    'Home Theater System': 'speaker', 'Gaming Console': 'controller', 'Action Camera': 'camera',
    'Fitness Tracker': 'smartwatch', 'External SSD': 'drive',
    'Noise Cancelling Headphones': 'headphones', 'Smart TV': 'screen', 'Webcam': 'camera',

    # Fashion
    'Running Shoes': 'shoe', 'Denim Jacket': 'jacket', 'Cotton T-Shirt': 'shirt',
    'Formal Shirt': 'shirt', 'Leather Wallet': 'wallet', 'Sunglasses': 'sunglasses',
    'Analog Watch': 'clock', 'Backpack': 'backpack', 'Sneakers': 'shoe',
    'Hoodie': 'shirt', 'Chino Trousers': 'trousers', 'Leather Belt': 'belt',
    'Sports Cap': 'cap', 'Handbag': 'handbag', 'Rain Jacket': 'jacket',
    'Wool Sweater': 'shirt', 'Ankle Boots': 'boot', 'Silk Scarf': 'scarf',
    'Sports Socks (3-pack)': 'socks', 'Slim Fit Jeans': 'trousers',

    # Home & Kitchen
    'Non-Stick Cookware Set': 'pot', 'Air Fryer': 'airfryer', 'Blender': 'blender',
    'Electric Kettle': 'kettle', 'Microwave Oven': 'microwave', 'Vacuum Cleaner': 'vacuum',
    'Bedsheet Set': 'bed', 'Study Lamp': 'lamp', 'Dinner Set': 'plate',
    'Pressure Cooker': 'pot', 'Coffee Maker': 'coffeemaker', 'Toaster': 'toaster',
    'Ceiling Fan': 'fan', 'Storage Organizer Box': 'box', 'Curtain Set': 'curtain',
    'Water Purifier': 'waterdrop', 'Cushion Cover Set': 'cushion', 'Induction Cooktop': 'cooktop',
    'Wall Clock': 'clock', 'Knife Set': 'knife',

    # Books (alternate for visual variety -- all equally accurate, all books)
    'Self-Help Bestseller': 'book', 'Fantasy Novel': 'book-stack', 'Mystery Thriller': 'book',
    'Science Fiction Novel': 'book-stack', 'Biography': 'book', 'History Book': 'book-stack',
    'Personal Finance Guide': 'book', "Cookbook": 'book-stack', 'Poetry Collection': 'book',
    'Programming Handbook': 'book-stack', 'Business Strategy Book': 'book',
    "Children's Picture Book": 'book-stack', 'Graphic Novel': 'book', 'Travel Guide': 'book-stack',
    'Philosophy Book': 'book', 'Romance Novel': 'book-stack', 'Productivity Guide': 'book',
    'Language Learning Book': 'book-stack', 'Classic Literature': 'book', 'Comic Book': 'book-stack',

    # Sports & Fitness
    'Yoga Mat': 'mat', 'Adjustable Dumbbell Set': 'dumbbell', 'Cricket Bat': 'bat',
    'Football': 'ball', 'Badminton Racquet': 'racquet', 'Resistance Bands Set': 'band',
    'Skipping Rope': 'rope', 'Cycling Helmet': 'helmet', 'Treadmill': 'treadmill',
    'Gym Gloves': 'glove', 'Water Bottle (Sports)': 'bottle', 'Table Tennis Paddle Set': 'paddle',
    'Camping Tent': 'tent', 'Trekking Backpack': 'backpack', 'Protein Shaker': 'shaker',
    'Foam Roller': 'roller', 'Basketball': 'ball', 'Swimming Goggles': 'goggles',
    'Fitness Resistance Tube': 'band', 'Exercise Bike': 'bike',
}

CATEGORY_FALLBACK_ICON = {
    'Electronics': 'phone', 'Fashion': 'shirt', 'Home & Kitchen': 'box',
    'Books': 'book', 'Sports & Fitness': 'dumbbell',
}


def icon_for_product(product_name, category_name):
    """Find which known product type this generated name contains (names
    are built as "<brand> <type>" by seed_products.py, so the type is
    always a substring), and return that type's icon markup. Falls back
    to a category-level icon on a miss (e.g. a --csv-imported product).
    """
    from catalog.management.commands.seed_products import CATEGORY_PRODUCT_TYPES

    for product_type in CATEGORY_PRODUCT_TYPES.get(category_name, []):
        if product_type in product_name:
            icon_key = TYPE_TO_ICON.get(product_type)
            if icon_key:
                return ICON_SVGS[icon_key]

    fallback_key = CATEGORY_FALLBACK_ICON.get(category_name, 'box')
    return ICON_SVGS[fallback_key]
