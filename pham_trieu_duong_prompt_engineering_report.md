# Báo Cáo Cá Nhân: Kết Quả Cải Thiện Agent Bằng Prompt Engineering

**Họ và tên:** Phạm Triều Dương  
**Mã HV:** 2A20260083  
**Bài lab:** Day 04 - Prompt Engineering Tool Calling

## 1. Mục Tiêu

Mục tiêu của bài lab này là cải thiện hành vi của order agent sao cho:

- hiểu đúng yêu cầu đặt hàng bằng tiếng Việt và pha trộn tiếng Anh - Việt
- gọi đúng chuỗi tool theo quy trình
- hỏi lại khi thiếu thông tin bắt buộc
- từ chối các yêu cầu vi phạm chính sách
- lưu đơn hàng dưới dạng JSON đúng cấu trúc và đúng dữ liệu thực tế từ tool

Điểm quan trọng của bài lab không nằm ở việc “code chạy được”, mà là làm cho agent hành xử ổn định hơn nhờ prompt, schema và guardrails tốt hơn.

## 2. Kết Quả Đạt Được

Sau khi cải thiện prompt và tinh chỉnh một số chi tiết liên quan đến luồng xử lý, agent đã tăng điểm rất rõ rệt.

- Điểm trước khi cải thiện: 59.54/100
- Điểm sau khi cải thiện: 99.69/100
- Tổng điểm hệ thống: 1296/1300

Một số case nổi bật đã được khắc phục tốt:

- case quoted item names như creator_premium_bundle_quotes đã chuyển từ trạng thái không gọi tool sang đạt 100/100
- các case cần xác nhận đơn hàng bằng tiếng Việt đã trả lời gọn, đúng trọng tâm hơn
- các case thiếu thông tin vẫn dừng đúng lúc để hỏi thêm, không gọi tool sai thời điểm
- các case từ chối chính sách vẫn giữ được hành vi an toàn

## 3. Những Kỹ Thuật Prompt Đã Triển Khai

### 3.1. Prompt phân vai rõ ràng

Mình viết system prompt theo hướng định vị rất rõ vai trò của agent: đây là trợ lý đặt hàng điện tử, trả lời bằng tiếng Việt, ngắn gọn, và chỉ được dùng dữ liệu thật từ tool.

Lợi ích:

- giảm tình trạng trả lời lan man
- hạn chế suy diễn ngoài catalog
- tăng độ nhất quán của final answer

### 3.2. Ép thứ tự tool cố định

Prompt được chốt một workflow bắt buộc gồm 5 bước:

1. list_products
2. get_product_details
3. get_discount
4. calculate_order_totals
5. save_order

Kỹ thuật này giúp agent không “nhảy cóc” sang bước lưu đơn khi chưa có đủ dữ liệu kiểm tra.

### 3.3. Cơ chế kiểm tra trước khi gọi tool

Mình thêm một cổng kiểm tra rõ ràng trước tool đầu tiên, yêu cầu đủ:

- tên khách hàng
- số điện thoại
- email
- địa chỉ giao hàng
- danh sách sản phẩm hợp lệ

Đây là cách giảm lỗi gọi tool quá sớm. Với những case thiếu email hoặc thiếu địa chỉ giao hàng, agent vẫn dừng đúng và hỏi lại thay vì tự đoán.

### 3.4. Guardrails cho yêu cầu sai chính sách

Prompt cũng nói thẳng các tình huống phải từ chối ngay:

- hóa đơn giả
- giảm giá thủ công
- bỏ qua tồn kho
- bỏ qua catalog thật

Điều này giúp agent giữ được ranh giới an toàn, không cố “giúp” người dùng bằng cách làm sai nghiệp vụ.

### 3.5. Grounding nghiêm ngặt theo kết quả tool

Một kỹ thuật rất quan trọng là bắt agent chỉ dùng các giá trị thật từ tool:

- product_id
- SKU
- giá
- discount rate
- campaign code
- đường dẫn lưu file

Nhờ vậy, final answer và JSON lưu ra đều grounded hơn, ít bịa đặt hơn.

### 3.6. Sửa prompt cho case quoted item names

Đây là điểm cải thiện quan trọng nhất cho case khó `creator_premium_bundle_quotes`.

Trước đó, prompt quá cứng ở chỗ bắt phải có “số lượng cụ thể”, nên agent bị kẹt và chỉ hỏi lại thay vì đi tiếp. Mình đã sửa prompt theo hướng:

- nếu người dùng chỉ nêu tên món nhưng không ghi số lượng thì mặc định mỗi món = 1
- nếu danh sách sản phẩm được đặt trong dấu ngoặc kép hoặc có ngữ cảnh như “Tôi chốt các món sau”, hãy hiểu đó là danh sách hợp lệ
- chỉ hỏi lại khi thật sự mơ hồ

Sau sửa đổi này, case quoted items đã được xử lý đúng và đạt 100/100.

## 4. Bài Học Rút Ra

Qua bài lab này, mình rút ra một số điểm thực tế:

- prompt không chỉ là mô tả chung chung; nó là cơ chế điều khiển hành vi
- những câu chữ tưởng nhỏ như “số lượng cụ thể” có thể làm agent dừng sai hoàn toàn
- với agent tool-calling, cần ưu tiên workflow, điều kiện dừng, và quy tắc grounding hơn là mô tả dài dòng
- khi case thất bại, phải đọc tool trace và saved artifact chứ không chỉ nhìn final answer
- với các câu nhập hàng hóa tự nhiên, cần cho agent một quy ước hợp lý, ví dụ mặc định quantity = 1 nếu người dùng chỉ liệt kê tên món

## 5. Kết Luận

Sau khi cải thiện prompt, agent đã tiến từ mức hoạt động còn nhiều lỗi sang mức gần như đạt trọn bộ rubric, với điểm 99.69/100.

Điều đáng giá nhất của bài lab không phải chỉ là điểm số, mà là việc kiểm soát hành vi của agent tốt hơn bằng prompt engineering: rõ vai trò, rõ luồng tool, rõ điều kiện dừng, rõ guardrails, và rõ cách xử lý các câu người dùng tự nhiên hơn.

Nếu tiếp tục làm sâu hơn, mình sẽ tập trung vào hai hướng:

- làm prompt ngắn hơn nhưng vẫn giữ đủ ràng buộc
- xây thêm test case cho các dạng câu nhập hàng hoá mơ hồ để agent ổn định hơn nữa
