import random
from datetime import date, timedelta
from faker import Faker
from app.database import SessionLocal
from app.models.inventory import SKU, InventoryRecord

fake = Faker("en_IN")  # Indian locale for realistic names and addresses

# 8 categories with realistic Indian FMCG brands and product types
CATEGORIES = {
    "Dairy": {
        "brands": ["Amul", "Mother Dairy", "Nestle", "Britannia", "Gopaljee"],
        "products": [
            "Milk 1L",
            "Butter 500g",
            "Paneer 200g",
            "Curd 400g",
            "Ghee 1L",
            "Cheese 200g",
            "Lassi 200ml",
            "Yogurt 100g",
        ],
        "shelf_life_range": (3, 180),
        "price_range": (20, 600),
    },
    "Beverages": {
        "brands": ["Coca Cola", "Pepsi", "Dabur", "Parle", "Bisleri", "Paper Boat"],
        "products": [
            "Cola 2L",
            "Juice 1L",
            "Water 1L",
            "Soda 750ml",
            "Energy Drink 250ml",
            "Nimbu Pani 500ml",
        ],
        "shelf_life_range": (90, 365),
        "price_range": (15, 150),
    },
    "Snacks": {
        "brands": ["Haldiram", "Parle", "Britannia", "ITC", "PepsiCo", "Balaji"],
        "products": [
            "Bhujia 200g",
            "Biscuits 150g",
            "Chips 40g",
            "Namkeen 250g",
            "Cookies 100g",
            "Crackers 200g",
        ],
        "shelf_life_range": (90, 270),
        "price_range": (10, 120),
    },
    "Staples": {
        "brands": [
            "Aashirvaad",
            "Fortune",
            "India Gate",
            "Tata",
            "Patanjali",
            "Daawat",
        ],
        "products": [
            "Atta 5kg",
            "Rice 5kg",
            "Dal 1kg",
            "Sugar 1kg",
            "Salt 1kg",
            "Oil 1L",
            "Poha 500g",
        ],
        "shelf_life_range": (180, 730),
        "price_range": (50, 400),
    },
    "Personal Care": {
        "brands": [
            "Hindustan Unilever",
            "P&G",
            "Colgate",
            "Dabur",
            "Patanjali",
            "Himalaya",
        ],
        "products": [
            "Shampoo 200ml",
            "Soap 100g",
            "Toothpaste 150g",
            "Face Wash 100ml",
            "Moisturizer 200ml",
        ],
        "shelf_life_range": (365, 1095),
        "price_range": (30, 400),
    },
    "Household": {
        "brands": ["Surf Excel", "Ariel", "Vim", "Harpic", "Lizol", "Colin"],
        "products": [
            "Detergent 1kg",
            "Dish Wash 500ml",
            "Floor Cleaner 1L",
            "Toilet Cleaner 500ml",
            "Glass Cleaner 500ml",
        ],
        "shelf_life_range": (365, 1095),
        "price_range": (40, 350),
    },
    "Confectionery": {
        "brands": ["Cadbury", "Nestle", "Perfetti", "Parle", "ITC", "Haribo"],
        "products": [
            "Chocolate 50g",
            "Toffee Pack 100g",
            "Gum 18g",
            "Candy 150g",
            "Wafer 75g",
        ],
        "shelf_life_range": (90, 365),
        "price_range": (10, 200),
    },
    "Frozen": {
        "brands": ["McCain", "Godrej", "ITC", "Vadilal", "Amul", "Mother Dairy"],
        "products": [
            "French Fries 500g",
            "Peas 500g",
            "Ice Cream 1L",
            "Paratha 5pc",
            "Corn 250g",
        ],
        "shelf_life_range": (90, 365),
        "price_range": (80, 350),
    },
}

# Warehouse locations
LOCATIONS = (
    [f"Rack {row}{num}" for row in "ABCDE" for num in range(1, 11)]
    + [f"Cold Storage {n}" for n in range(1, 6)]
    + [f"Floor {n}" for n in range(1, 4)]
)


def generate_skus(target_count=500):
    """Generate SKU objects until we hit target count."""
    skus = []
    seen_codes = set()  # track codes to avoid duplicates

    # Calculate how many products per category to hit 500 total
    per_category = target_count // len(CATEGORIES)

    for category, config in CATEGORIES.items():
        count = 0
        attempts = 0

        while count < per_category and attempts < 1000:
            attempts += 1

            brand = random.choice(config["brands"])
            product = random.choice(config["products"])
            name = f"{brand} {product}"

            # Generate code like "AMU-MLK-001"
            brand_code = brand[:3].upper().replace(" ", "")
            product_code = product[:3].upper().replace(" ", "")
            number = str(random.randint(1, 999)).zfill(3)
            code = f"{brand_code}-{product_code}-{number}"

            # Skip if code already exists
            if code in seen_codes:
                continue

            seen_codes.add(code)

            purchase_price = round(random.uniform(*config["price_range"]), 2)

            # Selling price is always higher than purchase price
            selling_price = round(purchase_price * random.uniform(1.1, 1.4), 2)

            shelf_life = random.randint(*config["shelf_life_range"])

            sku = SKU(
                code=code,
                name=name,
                category=category,
                unit=random.choice(["piece", "kg", "litre", "pack"]),
                reorder_level=random.randint(5, 50),
                shelf_life_days=shelf_life,
                purchase_price=purchase_price,
                selling_price=selling_price,
                # Description used later for generating embeddings
                description=f"{name} - {category} product by {brand}. Unit: {product.split()[-1]}. Shelf life: {shelf_life} days.",
            )

            skus.append(sku)
            count += 1

    return skus


def generate_inventory_records(skus):
    """Generate 2-4 inventory records per SKU."""
    records = []
    today = date.today()

    for sku in skus:
        # Each SKU has 2-4 batches in the warehouse
        num_batches = random.randint(2, 4)

        for batch_num in range(num_batches):
            # Received date somewhere in the last 60 days
            received_date = today - timedelta(days=random.randint(1, 60))

            # Expiry date based on shelf life — some items already close to expiry
            if sku.shelf_life_days:
                # 10% chance the batch is expiring very soon (within 7 days) — for dashboard alerts
                if random.random() < 0.10:
                    expiry_date = today + timedelta(days=random.randint(0, 7))
                # 5% chance already expired — also for dashboard alerts
                elif random.random() < 0.05:
                    expiry_date = today - timedelta(days=random.randint(1, 10))
                else:
                    expiry_date = received_date + timedelta(days=sku.shelf_life_days)
            else:
                expiry_date = None

            # 10% chance a batch has low stock — for reorder alerts
            if random.random() < 0.10:
                quantity = random.randint(1, sku.reorder_level)
            else:
                quantity = random.randint(sku.reorder_level + 1, sku.reorder_level * 10)

            record = InventoryRecord(
                sku=sku,  # SQLAlchemy handles the sku_id foreign key automatically
                quantity=quantity,
                received_date=received_date,
                expiry_date=expiry_date,
                location=random.choice(LOCATIONS),
                batch_number=f"BATCH-{fake.bothify('??###').upper()}",
            )

            records.append(record)

    return records


def seed():
    db = SessionLocal()

    try:
        # Check if already seeded to avoid duplicates
        existing = db.query(SKU).count()
        if existing > 0:
            print(f"Database already has {existing} SKUs. Skipping seed.")
            return

        print("Generating SKUs...")
        skus = generate_skus(500)

        print(f"Generated {len(skus)} SKUs. Saving to database...")
        db.add_all(skus)
        db.flush()  # flush assigns IDs without committing — needed before creating records

        print("Generating inventory records...")
        records = generate_inventory_records(skus)

        print(f"Generated {len(records)} inventory records. Saving...")
        db.add_all(records)

        db.commit()
        print(f"Done. Seeded {len(skus)} SKUs and {len(records)} inventory records.")

    except Exception as e:
        db.rollback()  # roll back everything if anything fails
        print(f"Seed failed: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()
