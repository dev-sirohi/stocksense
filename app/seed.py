import asyncio
import random
from datetime import date, timedelta
from faker import Faker

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.inventory import SKU, InventoryRecord

fake = Faker("en_IN")  # Indian locale for realistic FMCG brand names

# 8 categories with realistic Indian brands and product types
CATEGORIES = {
    "Dairy": {
        "brands": ["Amul", "Mother Dairy", "Nestle", "Britannia", "Gopaljee"],
        "products": [
            "Milk 1L", "Butter 500g", "Paneer 200g", "Curd 400g",
            "Ghee 1L", "Cheese 200g", "Lassi 200ml", "Yogurt 100g",
        ],
        "shelf_life_range": (3, 180),
        "price_range": (20, 600),
    },
    "Beverages": {
        "brands": ["Coca Cola", "Pepsi", "Dabur", "Parle", "Bisleri", "Paper Boat"],
        "products": [
            "Cola 2L", "Juice 1L", "Water 1L", "Soda 750ml",
            "Energy Drink 250ml", "Nimbu Pani 500ml",
        ],
        "shelf_life_range": (90, 365),
        "price_range": (15, 150),
    },
    "Snacks": {
        "brands": ["Haldiram", "Parle", "Britannia", "ITC", "PepsiCo", "Balaji"],
        "products": [
            "Bhujia 200g", "Biscuits 150g", "Chips 40g",
            "Namkeen 250g", "Cookies 100g", "Crackers 200g",
        ],
        "shelf_life_range": (90, 270),
        "price_range": (10, 120),
    },
    "Staples": {
        "brands": ["Aashirvaad", "Fortune", "India Gate", "Tata", "Patanjali", "Daawat"],
        "products": [
            "Atta 5kg", "Rice 5kg", "Dal 1kg", "Sugar 1kg",
            "Salt 1kg", "Oil 1L", "Poha 500g",
        ],
        "shelf_life_range": (180, 730),
        "price_range": (50, 400),
    },
    "Personal Care": {
        "brands": ["Hindustan Unilever", "P&G", "Colgate", "Dabur", "Patanjali", "Himalaya"],
        "products": [
            "Shampoo 200ml", "Soap 100g", "Toothpaste 150g",
            "Face Wash 100ml", "Moisturizer 200ml",
        ],
        "shelf_life_range": (365, 1095),
        "price_range": (30, 400),
    },
    "Household": {
        "brands": ["Surf Excel", "Ariel", "Vim", "Harpic", "Lizol", "Colin"],
        "products": [
            "Detergent 1kg", "Dish Wash 500ml", "Floor Cleaner 1L",
            "Toilet Cleaner 500ml", "Glass Cleaner 500ml",
        ],
        "shelf_life_range": (365, 1095),
        "price_range": (40, 350),
    },
    "Confectionery": {
        "brands": ["Cadbury", "Nestle", "Perfetti", "Parle", "ITC", "Haribo"],
        "products": [
            "Chocolate 50g", "Toffee Pack 100g", "Gum 18g",
            "Candy 150g", "Wafer 75g",
        ],
        "shelf_life_range": (90, 365),
        "price_range": (10, 200),
    },
    "Frozen": {
        "brands": ["McCain", "Godrej", "ITC", "Vadilal", "Amul", "Mother Dairy"],
        "products": [
            "French Fries 500g", "Peas 500g", "Ice Cream 1L",
            "Paratha 5pc", "Corn 250g",
        ],
        "shelf_life_range": (90, 365),
        "price_range": (80, 350),
    },
}

LOCATIONS = (
    [f"Rack {row}{num}" for row in "ABCDE" for num in range(1, 11)]
    + [f"Cold Storage {n}" for n in range(1, 6)]
    + [f"Floor {n}" for n in range(1, 4)]
)


def _generate_skus(target_count: int = 500) -> list[SKU]:
    skus: list[SKU] = []
    seen_codes: set[str] = set()
    per_category = target_count // len(CATEGORIES)

    for category, config in CATEGORIES.items():
        count = 0
        attempts = 0

        while count < per_category and attempts < 1000:
            attempts += 1
            brand = random.choice(config["brands"])
            product = random.choice(config["products"])
            name = f"{brand} {product}"

            brand_code = brand[:3].upper().replace(" ", "")
            product_code = product[:3].upper().replace(" ", "")
            number = str(random.randint(1, 999)).zfill(3)
            code = f"{brand_code}-{product_code}-{number}"

            if code in seen_codes:
                continue
            seen_codes.add(code)

            purchase_price = round(random.uniform(*config["price_range"]), 2)
            selling_price = round(purchase_price * random.uniform(1.1, 1.4), 2)
            shelf_life = random.randint(*config["shelf_life_range"])

            skus.append(SKU(
                code=code,
                name=name,
                category=category,
                unit=random.choice(["piece", "kg", "litre", "pack"]),
                reorder_level=random.randint(5, 50),
                shelf_life_days=shelf_life,
                purchase_price=purchase_price,
                selling_price=selling_price,
                description=(
                    f"{name} — {category} product by {brand}. "
                    f"Unit: {product.split()[-1]}. Shelf life: {shelf_life} days."
                ),
            ))
            count += 1

    return skus


def _generate_records(skus: list[SKU]) -> list[InventoryRecord]:
    records: list[InventoryRecord] = []
    today = date.today()

    # Reserve slots for guaranteed alert scenarios
    # Python note: random.sample(population, k) returns k unique items
    expiring_pool = random.sample(skus, min(25, len(skus)))
    expired_pool = random.sample(
        [s for s in skus if s not in expiring_pool],
        min(15, len(skus) - 25)
    )
    low_stock_pool = random.sample(
        [s for s in skus if s not in expiring_pool and s not in expired_pool],
        min(40, len(skus) - 40)
    )

    # Track which SKUs have received their guaranteed scenario
    guaranteed_expiring: set[int] = set()
    guaranteed_expired: set[int] = set()
    guaranteed_low_stock: set[int] = set()

    for idx, sku in enumerate(skus):
        num_batches = random.randint(2, 4)

        for batch_num in range(num_batches):
            received_date = today - timedelta(days=random.randint(1, 60))

            # Determine expiry date
            if sku.shelf_life_days:
                # First batch of guaranteed-expiring SKUs: set to expire within 7 days
                if sku in expiring_pool and idx not in guaranteed_expiring and batch_num == 0:
                    expiry_date = today + timedelta(days=random.randint(1, 7))
                    guaranteed_expiring.add(idx)

                # First batch of guaranteed-expired SKUs: set as already expired
                elif sku in expired_pool and idx not in guaranteed_expired and batch_num == 0:
                    expiry_date = today - timedelta(days=random.randint(1, 14))
                    guaranteed_expired.add(idx)

                # Random chance for other batches
                elif random.random() < 0.06:
                    expiry_date = today + timedelta(days=random.randint(0, 7))
                elif random.random() < 0.04:
                    expiry_date = today - timedelta(days=random.randint(1, 10))
                else:
                    expiry_date = received_date + timedelta(days=sku.shelf_life_days)
            else:
                expiry_date = None

            # Determine quantity
            # First batch of guaranteed low-stock SKUs: quantity below reorder level
            if sku in low_stock_pool and idx not in guaranteed_low_stock and batch_num == 0:
                quantity = random.randint(1, max(1, sku.reorder_level - 1))
                guaranteed_low_stock.add(idx)
            elif random.random() < 0.08:
                quantity = random.randint(1, sku.reorder_level)
            else:
                quantity = random.randint(sku.reorder_level + 1, sku.reorder_level * 8)

            records.append(InventoryRecord(
                sku=sku,   # SQLAlchemy auto-populates sku_id from this relationship
                quantity=quantity,
                received_date=received_date,
                expiry_date=expiry_date,
                location=random.choice(LOCATIONS),
                batch_number=f"BATCH-{fake.bothify('??###').upper()}",
            ))

    return records


async def seed() -> None:
    # Python note: 'async with' creates a new AsyncSession for this function's
    # lifetime, closing it automatically when the block exits.
    async with AsyncSessionLocal() as db:
        # Check if already seeded to avoid duplicates on repeated runs
        count_result = await db.execute(select(SKU).limit(1))
        existing = count_result.scalar_one_or_none()
        if existing is not None:
            print("Database already seeded. Skipping.")
            return

        print("Generating 500 SKUs...")
        skus = _generate_skus(500)

        print(f"Generated {len(skus)} SKUs. Saving to database...")
        db.add_all(skus)

        # flush() sends the INSERTs to Postgres and assigns auto-increment IDs,
        # but does NOT commit the transaction. We need the IDs before creating
        # InventoryRecord objects that reference sku.id via the relationship.
        await db.flush()

        print("Generating inventory records...")
        records = _generate_records(skus)

        db.add_all(records)
        await db.commit()

        print(f"Done. Seeded {len(skus)} SKUs and {len(records)} inventory records.")


if __name__ == "__main__":
    # asyncio.run() creates a new event loop, runs the coroutine to completion,
    # then closes the loop. This is how you run async code from a synchronous
    # script entry point.
    asyncio.run(seed())
