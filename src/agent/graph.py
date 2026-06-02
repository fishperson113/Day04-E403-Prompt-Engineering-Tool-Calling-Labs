from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from src.core.llm import build_chat_model, normalize_content
from src.core.schemas import (
    AgentResult,
    CalculateTotalsInput,
    DiscountInput,
    ListProductsInput,
    ProductDetailInput,
    SaveOrderInput,
    ToolCallRecord,
    OrderLineInput
)
from src.utils.data_store import OrderDataStore

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "artifacts" / "orders"


def build_system_prompt(today: str | None = None) -> str:
    current_day = today or "2026-06-01"
    return f"""
<role>
Bạn là một chuyên gia hỗ trợ đặt hàng thiết bị điện tử thông minh, làm việc cho một công ty thương mại điện tử.
</role>

<context>
- Hôm nay là: {current_day}
- Bạn có 5 tools để sử dụng: list_products, get_product_details, get_discount, calculate_order_totals, save_order.
- Tất cả dữ liệu sản phẩm, giá cả, tồn kho đều đến từ catalog có sẵn (file products.json). KHÔNG tự bịa.
- Đơn hàng chỉ được lưu sau khi hoàn thành đủ 5 bước.
</context>

<chain_of_thought>
Trước mỗi hành động, hãy tự hỏi và suy luận từng bước trong <thinking> tags:

1. PHÂN TÍCH: Khách muốn gì? Đã có thông tin gì? Còn thiếu gì?
   - Kiểm tra: tên, SĐT, email, địa chỉ, sản phẩm + số lượng
2. QUYẾT ĐỊNH: Nếu thiếu → hỏi. Nếu đủ → tiến hành tools.
3. LẬP KẾ HOẠCH TOOLS: Xác định tool nào cần gọi và thứ tự chính xác.
4. THỰC THI: Gọi tool theo đúng thứ tự, KHÔNG lặp lại tool.
5. TỔNG KẾT: Tổng hợp kết quả từ tool thành câu trả lời cuối cùng.

<examples>
Ví dụ quy trình suy nghĩ ĐÚNG (Đủ thông tin):
<example_good>
User: "Tôi là Hùng, 0901234567, hung@gmail.com, ở HN. Mua 1 laptop gaming và 2 chuột không dây."
Thinking:
- Phân tích: Đủ thông tin cá nhân và sản phẩm.
- Quyết định: Tiến hành đặt hàng.
- Kế hoạch: list_products(query="", limit=15) -> get_product_details -> get_discount -> calculate_order_totals -> save_order
- Hành động: Gọi list_products(query="", limit=15)
</example_good>

Ví dụ quy trình suy nghĩ SAI (Thiếu thông tin):
<example_bad>
User: "Mua 1 laptop gaming"
Thinking: Có thông tin rồi → gọi list_products ngay
Kết quả: LỖI. Sai vì chưa hỏi tên, SĐT, email, địa chỉ.
</example_bad>
</examples>
</chain_of_thought>

<tool_workflow>
Khi đã có ĐỦ thông tin khách hàng, thực hiện CHÍNH XÁC theo thứ tự sau, KHÔNG bỏ qua bước nào:

<step order="1" name="list_products" once="true">
  Gọi 1 LẦN DUY NHẤT để tìm kiếm thông tin sản phẩm.
  Nếu khách yêu cầu nhiều sản phẩm, HÃY ĐỂ TRỐNG param `query` (query="") và tăng `limit=15` để lấy toàn bộ danh sách, sau đó tự chọn lọc.
  TUYỆT ĐỐI KHÔNG gọi list_products nhiều lần.
</step>

<step order="2" name="get_product_details">
  Gọi NGAY sau bước 1, dùng product_ids từ kết quả bước 1.
  Output: detail_token (dùng cho bước 4, 5).
</step>

<step order="3" name="get_discount">
  Dùng email khách hàng làm seed_hint.
  customer_tier: "standard" (mặc định), chỉ "vip" nếu khách tự nói.
</step>

<step order="4" name="calculate_order_totals">
  items = list of dicts, e.g. [{{"product_id": "LT-001", "quantity": 1}}, ...]
  detail_token = token từ bước 2. discount_rate = rate từ bước 3.
</step>

<step order="5" name="save_order">
  Lưu với ĐẦY ĐỦ: customer_name, customer_phone, customer_email, shipping_address, items, detail_token, discount_rate, campaign_code, customer_tier.
</step>
</tool_workflow>

<guardrails>
- TUYỆT ĐỐI KHÔNG gọi list_products nhiều hơn 1 lần trong cùng 1 yêu cầu.
- XỬ LÝ SẢN PHẨM THIẾU: Nếu một số sản phẩm không có trong catalog hoặc hết hàng, bạn hãy vẫn tiến hành tạo đơn cho NHỮNG SẢN PHẨM CÒN LẠI. Không dừng lại để hỏi.
- TỪ CHỐI: hóa đơn ảo, gian lận giá/thuế, bỏ qua tồn kho hoàn toàn.
- KHÔNG tự bịa product_id, giá, mã giảm giá, hoặc bất kỳ dữ liệu nào.
</guardrails>

<output_format>
Trả lời cuối cùng BẰNG TIẾNG VIỆT, ngắn gọn, đầy đủ theo cấu trúc:

Khi TẠO ĐƠN THÀNH CÔNG:
- ✅ Xác nhận + Mã đơn hàng (Order ID)
- 👤 Tên, Email, SĐT khách hàng
- 📦 Danh sách sản phẩm + số lượng
- 💰 Tổng tiền, chiết khấu (số tiền giảm), thành tiền
- 📍 Địa chỉ giao hàng

Khi TỪ CHỐI: "Rất tiếc, tôi không thể thực hiện yêu cầu này vì [lý do cụ thể]."

Khi CẦN LÀM RÕ: Chỉ hỏi đúng thông tin còn thiếu, không hỏi thừa.
</output_format>
""".strip()


def build_tools(store: OrderDataStore):
    """
    Student TODO:
    - Define exactly five tools with strong tool schemas:
      - `list_products`
      - `get_product_details`
      - `get_discount`
      - `calculate_order_totals`
      - `save_order`
    - Use the provided Pydantic schemas from `core.schemas` so the tool arguments stay explicit.
    - Keep outputs compact and JSON-friendly because the grader will inspect the saved order payload.
    - `get_product_details` should return a validation token, and later pricing/save tools should require it.
    """

    @tool(args_schema=ListProductsInput)
    def list_products(
        query: str | None = None,
        category: str | None = None,
        max_unit_price: int | None = None,
        required_tags: list[str] | None = None,
        in_stock_only: bool = True,
        limit: int = 8,
    ) -> str:
        """Find product IDs. CALL THIS ONCE. Do NOT call this multiple times in a row."""
        tags = required_tags or []
        payload = store.list_products(
            query=query,
            category=category,
            max_unit_price=max_unit_price,
            required_tags=tags,
            in_stock_only=in_stock_only,
            limit=limit,
        )
        return json.dumps(payload, ensure_ascii=False)

    @tool(args_schema=ProductDetailInput)
    def get_product_details(product_ids: list[str]) -> str:
        """Validate Price/Stock. MUST be called immediately after list_products to get the detail_token."""
        return json.dumps(store.get_product_details(product_ids), ensure_ascii=False)

    @tool(args_schema=DiscountInput)
    def get_discount(seed_hint: str, customer_tier: str = "standard") -> str:
        """Return the simulated campaign discount for the order."""
        return json.dumps(store.get_discount(seed_hint=seed_hint, customer_tier=customer_tier), ensure_ascii=False)

    @tool(args_schema=CalculateTotalsInput)
    def calculate_order_totals(items: list[dict], detail_token: str, discount_rate: float) -> str:
        """Validate stock and calculate the discounted order total."""
        norm_items = [OrderLineInput(**item) if isinstance(item, dict) else item for item in items]
        payload = store.calculate_order_totals(items=norm_items, detail_token=detail_token, discount_rate=discount_rate)
        return json.dumps(payload, ensure_ascii=False)

    @tool(args_schema=SaveOrderInput)
    def save_order(
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        shipping_address: str,
        items: list[dict],
        detail_token: str,
        discount_rate: float,
        campaign_code: str,
        customer_tier: str = "standard",
        notes: str = "",
    ) -> str:
        """Persist the final order to a local JSON file."""
        norm_items = [OrderLineInput(**item) if isinstance(item, dict) else item for item in items]
        result = store.save_order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            shipping_address=shipping_address,
            items=norm_items,
            detail_token=detail_token,
            discount_rate=discount_rate,
            campaign_code=campaign_code,
            customer_tier=customer_tier,
            notes=notes,
        )
        return json.dumps(result, ensure_ascii=False)

    return [list_products, get_product_details, get_discount, calculate_order_totals, save_order]


def build_agent(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    provider: str = "google",
    model_name: str | None = None,
    today: str | None = None,
):
    """
    Student TODO:
    1. Create `OrderDataStore`.
    2. Build the chat model with `build_chat_model(...)`.
    3. Build the tools with `build_tools(store)`.
    4. Return `create_agent(model=..., tools=..., system_prompt=...)`.
    """
    store = OrderDataStore(data_dir or DEFAULT_DATA_DIR, output_dir or DEFAULT_OUTPUT_DIR, today=today)
    model = build_chat_model(
        provider=provider,
        model_name=model_name,
        temperature=0.0
    ).bind_tools(build_tools(store))

    return create_agent(
        model=model,
        tools=build_tools(store),
        system_prompt=build_system_prompt(today or store.today),
    )


def run_agent(
    query: str,
    *,
    provider: str = "google",
    model_name: str | None = None,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    today: str | None = None,
) -> AgentResult:
    """
    Student TODO:
    - Build the agent.
    - Invoke it with one user message.
    - Extract:
      - the final AI answer
      - the tool trace
      - the saved order payload, if any
    - Return an `AgentResult`.
    """
    agent = build_agent(
        data_dir=data_dir,
        output_dir=output_dir,
        provider=provider,
        model_name=model_name,
        today=today,
    )
    response = agent.invoke({"messages": [{"role": "user", "content": query}]})
    messages = response["messages"] if isinstance(response, dict) else response
    tool_calls = extract_tool_calls(messages)
    saved_order, saved_order_path = extract_saved_order(tool_calls)

    return AgentResult(
        query=query,
        final_answer=extract_final_answer(messages),
        tool_calls=tool_calls,
        provider=provider,
        model_name=model_name,
        saved_order=saved_order,
        saved_order_path=saved_order_path,
    )


def extract_final_answer(messages) -> str:
    """Optional helper: return the last non-empty AI answer."""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = normalize_content(message.content)
            if text:
                return text
    return ""


def extract_tool_calls(messages) -> list[ToolCallRecord]:
    """Optional helper: convert tool calls and tool results into a simple grading trace."""
    pending: dict[str, dict[str, Any]] = {}
    records: list[ToolCallRecord] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in getattr(message, "tool_calls", []) or []:
                pending[tool_call["id"]] = {
                    "name": tool_call["name"],
                    "args": tool_call.get("args", {}) or {},
                }
        elif isinstance(message, ToolMessage):
            metadata = pending.pop(message.tool_call_id, {})
            records.append(
                ToolCallRecord(
                    name=str(getattr(message, "name", None) or metadata.get("name", "")),
                    args=metadata.get("args", {}),
                    output=normalize_content(message.content),
                )
            )

    for metadata in pending.values():
        records.append(ToolCallRecord(name=metadata["name"], args=metadata["args"], output=""))
    return records


def extract_saved_order(tool_calls: list[ToolCallRecord]) -> tuple[dict | None, str | None]:
    """Optional helper: parse the `save_order` tool output into `(saved_order, path)`."""
    for record in reversed(tool_calls):
        if record.name != "save_order" or not record.output:
            continue
        try:
            payload = json.loads(record.output)
        except json.JSONDecodeError:
            continue
        if payload.get("status") != "saved":
            return None, None
        return payload.get("saved_order"), payload.get("path")
    return None, None

