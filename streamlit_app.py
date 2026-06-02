from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
import subprocess
import shlex
import time

try:
    from src.agent.graph import run_agent
except Exception:
    run_agent = None


ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "artifacts" / "logs"
ORDERS_DIR = ROOT_DIR / "artifacts" / "orders"


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_json_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def format_money(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "-"
    return f"{number:,} VND".replace(",", ".")


def get_log_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {}) or {}
    return {
        "overall_score": summary.get("overall_score"),
        "total_earned": summary.get("total_earned"),
        "total_max": summary.get("total_max"),
        "case_count": len(summary.get("cases", []) or []),
    }


def get_order_summary(payload: dict[str, Any]) -> dict[str, Any]:
    pricing = payload.get("pricing", {}) or {}
    customer = payload.get("customer", {}) or {}
    items = payload.get("items", []) or []
    return {
        "order_id": payload.get("order_id"),
        "customer_name": customer.get("name"),
        "final_total": pricing.get("final_total"),
        "discount_rate": pricing.get("discount_rate"),
        "item_count": len(items),
        "save_path": payload.get("save_path"),
    }


st.set_page_config(page_title="OrderDesk Dashboard", page_icon="📦", layout="wide")

st.title("OrderDesk Dashboard")
st.caption("Xem nhanh score logs và order JSON đã được lưu trong artifacts/.")

logs = list_json_files(LOGS_DIR)
orders = list_json_files(ORDERS_DIR)

top_left, top_mid, top_right = st.columns(3)
top_left.metric("Score logs", len(logs))
top_mid.metric("Orders", len(orders))
top_right.metric("Total JSON files", len(logs) + len(orders))

source = st.sidebar.radio(
    "Nguồn dữ liệu",
    ["Cả hai", "Score logs", "Orders"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.write("Thư mục đang đọc:")
st.sidebar.code(str(LOGS_DIR))
st.sidebar.code(str(ORDERS_DIR))

tabs = st.tabs(["Tổng quan", "Score logs", "Orders", "Chat & Tools"])

with tabs[0]:
    left, right = st.columns(2)

    with left:
        st.subheader("Score logs gần nhất")
        if logs:
            latest_log = load_json_file(logs[0])
            summary = get_log_summary(latest_log)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Overall score", summary["overall_score"] if summary["overall_score"] is not None else "-")
            c2.metric("Total earned", summary["total_earned"] if summary["total_earned"] is not None else "-")
            c3.metric("Total max", summary["total_max"] if summary["total_max"] is not None else "-")
            c4.metric("Cases", summary["case_count"])
            st.write(f"File: {logs[0].name}")
        else:
            st.info("Không tìm thấy score log nào trong artifacts/logs/.")

    with right:
        st.subheader("Order gần nhất")
        if orders:
            latest_order = load_json_file(orders[0])
            summary = get_order_summary(latest_order)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Order ID", summary["order_id"] or "-")
            c2.metric("Khách hàng", summary["customer_name"] or "-")
            c3.metric("Final total", format_money(summary["final_total"]))
            c4.metric("Số món", summary["item_count"])
            st.write(f"File: {orders[0].name}")
        else:
            st.info("Không tìm thấy order JSON nào trong artifacts/orders/.")

with tabs[1]:
    st.subheader("Score logs")
    if source in {"Cả hai", "Score logs"}:
        if not logs:
            st.warning("Không có file score log để hiển thị.")
        else:
            selected_log = st.selectbox(
                "Chọn file score log",
                logs,
                format_func=lambda path: path.name,
                key="selected_log",
            )
            payload = load_json_file(selected_log)
            summary = get_log_summary(payload)

            col1, col2, col3 = st.columns(3)
            col1.metric("Overall score", summary["overall_score"] if summary["overall_score"] is not None else "-")
            col2.metric("Total earned", summary["total_earned"] if summary["total_earned"] is not None else "-")
            col3.metric("Total max", summary["total_max"] if summary["total_max"] is not None else "-")

            st.write(f"Cases: {summary['case_count']}")
            cases = (payload.get("summary", {}) or {}).get("cases", []) or []
            if cases:
                st.dataframe(
                    [
                        {
                            "case_id": case.get("case_id"),
                            "score": case.get("score"),
                            "max_score": case.get("max_score"),
                        }
                        for case in cases
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            st.json(payload)
    else:
        st.info("Chọn 'Score logs' hoặc 'Cả hai' ở sidebar để xem log.")

with tabs[2]:
    st.subheader("Orders")
    if source in {"Cả hai", "Orders"}:
        if not orders:
            st.warning("Không có file order để hiển thị.")
        else:
            selected_order = st.selectbox(
                "Chọn file order",
                orders,
                format_func=lambda path: path.name,
                key="selected_order",
            )
            payload = load_json_file(selected_order)
            summary = get_order_summary(payload)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Order ID", summary["order_id"] or "-")
            col2.metric("Khách hàng", summary["customer_name"] or "-")
            col3.metric("Final total", format_money(summary["final_total"]))
            col4.metric("Discount rate", summary["discount_rate"] if summary["discount_rate"] is not None else "-")

            st.write(f"Save path: {summary['save_path']}")
            items = payload.get("items", []) or []
            if items:
                st.dataframe(
                    [
                        {
                            "product_id": item.get("product_id"),
                            "name": item.get("name"),
                            "quantity": item.get("quantity"),
                            "unit_price": item.get("unit_price"),
                            "line_total": item.get("line_total"),
                        }
                        for item in items
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            st.json(payload)
    else:
        st.info("Chọn 'Orders' hoặc 'Cả hai' ở sidebar để xem đơn hàng.")

with tabs[3]:
    st.subheader("Chat with agent")

    provider = st.sidebar.selectbox("Provider preset", ["google", "ollama", "openai"], index=0)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    with st.form(key="chat_form", clear_on_submit=False):
        user_input = st.text_area("Nhập câu hỏi / lệnh cho agent", height=100)
        submitted = st.form_submit_button("Gửi")

    if submitted:
        if not user_input or not user_input.strip():
            st.warning("Nhập nội dung trước khi gửi.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            if run_agent is None:
                st.error("Agent runtime not available: cannot call run_agent. Ensure `src` package is importable and LLM config is set.")
            else:
                with st.spinner("Calling agent..."):
                    try:
                        result = run_agent(user_input, provider=provider)
                        st.session_state.chat_history.append({"role": "assistant", "content": result.final_answer})
                        st.success("Agent trả lời:")
                        st.write(result.final_answer)
                        if result.tool_calls:
                            st.write("Tool calls:")
                            st.json([c.model_dump() if hasattr(c, 'model_dump') else c.__dict__ for c in result.tool_calls])
                    except Exception as exc:
                        st.error(f"Agent invocation failed: {exc}")

    st.markdown("---")
    st.subheader("Chat history")
    for msg in st.session_state.chat_history[::-1]:
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            st.markdown(f"**You:** {content}")
        else:
            st.markdown(f"**Agent:** {content}")

    st.markdown("---")
    st.subheader("Run grader / tests")
    col_run1, col_run2 = st.columns(2)
    with col_run1:
        if st.button("Run grader (src.agent.graph)"):
            cmd = "python grade/scoring.py --module src.agent.graph --provider google"
            with st.spinner(f"Running: {cmd}"):
                proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
                st.subheader("Grader output")
                st.text_area("stdout", proc.stdout, height=300)
                if proc.stderr:
                    st.text_area("stderr", proc.stderr, height=200)
    with col_run2:
        if st.button("Run pytest (save_order test)"):
            cmd = "python -m pytest tests/test_reference_solution.py::test_save_order_matches_expected_fixture -q"
            with st.spinner(f"Running: {cmd}"):
                proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
                st.subheader("Pytest output")
                st.text_area("stdout", proc.stdout, height=300)
                if proc.stderr:
                    st.text_area("stderr", proc.stderr, height=200)