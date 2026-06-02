from __future__ import annotations

from pathlib import Path

from core.schemas import OrderLineInput, ProductRecord


from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from core.schemas import OrderLineInput, ProductRecord


class OrderDataStore:
    """
    Student TODO:
    - Load `products.json`.
    - Build lookup helpers for product IDs and normalized search.
    - Save final orders under `artifacts/orders/`.
    """

    def __init__(self, data_dir: Path, output_dir: Path, *, today: str | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.today = today or "2026-06-01"
        self.products: list[ProductRecord] = []
        self.product_index: dict[str, ProductRecord] = {}

        products_path = self.data_dir / "products.json"
        if products_path.exists():
            raw_data = json.loads(products_path.read_text(encoding="utf-8"))
            for item in raw_data:
                product = ProductRecord(**item)
                self.products.append(product)
                self.product_index[product.product_id] = product

        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def list_products(
        self,
        *,
        query: str | None = None,
        category: str | None = None,
        max_unit_price: int | None = None,
        required_tags: list[str] | None = None,
        in_stock_only: bool = True,
        limit: int = 8,
    ) -> list[dict]:
        """
        Student TODO:
        - Search by product name, brand, category, tags, and description.
        - Return compact catalog summaries that the model can reuse in later tool calls.
        """
        results = []
        for p in self.products:
            if in_stock_only and p.stock <= 0:
                continue
            if category and category.lower() != p.category.lower():
                continue
            if max_unit_price and p.unit_price > max_unit_price:
                continue
            if required_tags:
                if not all(tag.lower() in [t.lower() for t in p.tags] for tag in required_tags):
                    continue

            if query:
                q = query.lower()
                if not (q in p.name.lower() or q in p.brand.lower() or q in p.description.lower()):
                    continue

            results.append({
                "product_id": p.product_id,
                "name": p.name,
                "unit_price": p.unit_price,
                "stock": p.stock,
                "brand": p.brand
            })

            if len(results) >= limit:
                break

        return results

    def get_product_details(self, product_ids: list[str]) -> dict:
        """
        Student TODO:
        - Return exact pricing, stock, category, and warranty information for each product ID.
        - Return a deterministic validation token that later tools can verify.
        - Preserve the input order or document how you reorder it.
        """
        matched = []
        for pid in product_ids:
            if pid in self.product_index:
                p = self.product_index[pid]
                matched.append({
                    "product_id": p.product_id,
                    "sku": p.sku,
                    "name": p.name,
                    "unit_price": p.unit_price,
                    "stock": p.stock,
                    "category": p.category,
                    "warranty_months": p.warranty_months
                })

        # Create a deterministic validation token based on matched products
        token_src = ":".join(sorted(product_ids))
        detail_token = hashlib.md5(token_src.encode()).hexdigest()

        return {
            "products": matched,
            "detail_token": detail_token
        }

    def get_discount(self, *, seed_hint: str, customer_tier: str = "standard") -> dict:
        """
        Student TODO:
        - Simulate a random campaign discount with deterministic seeding for grading.
        - Supported discount rates should be `0.1` or `0.2`.
        """
        # Deterministic discount based on seed_hint
        h = int(hashlib.md5(seed_hint.encode()).hexdigest(), 16)
        discount_rate = 0.2 if (h % 2 == 0) else 0.1
        if customer_tier.lower() == "vip":
            discount_rate = 0.2

        campaign_code = f"CAMP-{(h % 1000):03d}"
        return {
            "discount_rate": discount_rate,
            "campaign_code": campaign_code
        }

    def calculate_order_totals(self, *, items: list[OrderLineInput], detail_token: str, discount_rate: float) -> dict:
        """
        Student TODO:
        - Validate product IDs.
        - Validate the detail token produced by `get_product_details(...)`.
        - Validate requested quantities against stock.
        - Compute subtotal, discount amount, and final total.
        - Return an error payload instead of throwing for common user mistakes.
        """
        # Validate token
        product_ids = [item.product_id for item in items]
        expected_token = hashlib.md5(":".join(sorted(product_ids)).encode()).hexdigest()

        if detail_token != expected_token:
            return {"error": "Invalid detail token. Please call get_product_details first."}

        subtotal = 0
        for item in items:
            if item.product_id not in self.product_index:
                return {"error": f"Product {item.product_id} not found."}
            p = self.product_index[item.product_id]
            if item.quantity > p.stock:
                return {"error": f"Insufficient stock for {p.name}. Available: {p.stock}"}
            subtotal += p.unit_price * item.quantity

        discount_amount = int(subtotal * discount_rate)
        total = subtotal - discount_amount

        return {
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "total": total,
            "items": [item.model_dump() for item in items]
        }

    def save_order(
        self,
        *,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        shipping_address: str,
        items: list[OrderLineInput],
        detail_token: str,
        discount_rate: float,
        campaign_code: str,
        customer_tier: str = "standard",
        notes: str = "",
    ) -> dict:
        """
        Student TODO:
        - Recompute totals before saving.
        - Build a deterministic order ID.
        - Persist the final JSON payload to the output directory.
        - Return both the saved order payload and the saved file path.
        """
        totals = self.calculate_order_totals(items=items, detail_token=detail_token, discount_rate=discount_rate)
        if "error" in totals:
            return totals

        order_id_src = f"{customer_email}:{self.today}:{totals['total']}"
        order_id = f"ORD-{hashlib.md5(order_id_src.encode()).hexdigest()[:8].upper()}"

        order_payload = {
            "order_id": order_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_email": customer_email,
            "shipping_address": shipping_address,
            "items": totals["items"],
            "subtotal": totals["subtotal"],
            "discount_rate": discount_rate,
            "discount_amount": totals["discount_amount"],
            "total": totals["total"],
            "campaign_code": campaign_code,
            "customer_tier": customer_tier,
            "notes": notes,
            "created_at": self.today
        }

        file_name = f"{order_id}.json"
        file_path = self.output_dir / file_name
        file_path.write_text(json.dumps(order_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "status": "saved",
            "order_id": order_id,
            "path": str(file_path),
            "saved_order": order_payload
        }

