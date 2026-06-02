from __future__ import annotations

from pathlib import Path

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
        self.today = today
        self.products: list[ProductRecord] = []
        self.product_index: dict[str, ProductRecord] = {}
        raise NotImplementedError("Load product data and output paths in OrderDataStore.__init__().")

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
        raise NotImplementedError

    def get_product_details(self, product_ids: list[str]) -> list[dict]:
        """
        Student TODO:
        - Return exact pricing, stock, category, and warranty information for each product ID.
        - Return a deterministic validation token that later tools can verify.
        - Preserve the input order or document how you reorder it.
        """
        raise NotImplementedError

    def get_discount(self, *, seed_hint: str, customer_tier: str = "standard") -> dict:
        """
        Student TODO:
        - Simulate a random campaign discount with deterministic seeding for grading.
        - Supported discount rates should be `0.1` or `0.2`.
        """
        raise NotImplementedError

    def calculate_order_totals(self, *, items: list[OrderLineInput], detail_token: str, discount_rate: float) -> dict:
        """
        Student TODO:
        - Validate product IDs.
        - Validate the detail token produced by `get_product_details(...)`.
        - Validate requested quantities against stock.
        - Compute subtotal, discount amount, and final total.
        - Return an error payload instead of throwing for common user mistakes.
        """
        raise NotImplementedError

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
        raise NotImplementedError
