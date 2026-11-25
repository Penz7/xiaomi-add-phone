# Xiaomi Add Phone — thêm SĐT vào tài khoản Xiaomi khi mục này bị ẩn

Công cụ nhỏ để **thêm số điện thoại vào tài khoản Xiaomi** trong trường hợp MIUI/HyperOS
bản global đã ẩn mục "Số điện thoại" khỏi *Cài đặt → Tài khoản Xiaomi → Bảo mật tài khoản*.

## Vấn đề

Tài khoản Mi tạo qua Google/Facebook (hoặc một số tài khoản global) không có số điện thoại
liên kết, và Xiaomi ẩn luôn đường dẫn để thêm. Hệ quả thường gặp nhất:

```
Mi Unlock / MiUnlockTool → ahaUnlock
{
  "code": 20041,
  "descEN": "Sorry, your MI ID is not associated with a phone number."
}
```

Tức là bạn **không thể mở bootloader** dù đã bind tài khoản, đã chờ đủ ngày, vì bước unlock
yêu cầu MI ID phải có số điện thoại.

## Nguyên lý

Mục SĐT **không bị xoá**, chỉ bị ẩn khỏi menu. Activity vẫn tồn tại:

```
com.xiaomi.account/.ui.UserPhoneInfoActivity
```

Tool mở thẳng Activity đó bằng ADB rồi điều khiển giao diện (`uiautomator dump` + `input tap/text`):
bấm "Thêm số điện thoại" → xác thực mật khẩu → nhập số → nhập mã xác minh.

Không cần root. Không sửa gì trong hệ thống. Không đụng tới bootloader.

## Yêu cầu

- Python 3.8+ (chỉ dùng thư viện chuẩn)
- `adb` trong PATH (Android platform-tools)
- Trên điện thoại: bật **USB debugging**, đã đăng nhập tài khoản Xiaomi
- Nếu ROM chặn lệnh `am start`, bật thêm **USB debugging (Security settings)**

## Dùng

```sh
# 1. Xem tài khoản đã có SĐT chưa
python3 xmi_add_phone.py check

# 2. Chỉ mở trang ẩn rồi tự bấm tay
python3 xmi_add_phone.py open

# 3. Thêm số (tool tự bấm, sẽ hỏi mật khẩu và mã xác minh)
python3 xmi_add_phone.py add --phone +84914123456

# Nhiều máy cắm cùng lúc / adb ở chỗ khác
python3 xmi_add_phone.py add --phone +84914123456 --serial 9190f9e2 --adb /usr/local/bin/adb
```

Tuỳ chọn:

| Cờ | Ý nghĩa |
|---|---|
| `--phone` | Số cần thêm, dạng `+84…` hoặc `09…` |
| `--password` | Truyền mật khẩu thay vì hỏi (kém an toàn, dễ lọt shell history) |
| `--otp` | Truyền sẵn mã xác minh |
| `--manual` | Không tự bấm; tool dừng lại để bạn thao tác |
| `--debug` | In cây UI mỗi bước, dùng khi tool không nhận diện được màn hình |

Kết quả mong đợi:

```
✔ Tài khoản đã có số điện thoại liên kết: +84 961***817
```

Sau đó bước unlock sẽ trả `20036` (`waitHour: 168`) thay vì `20041`.

## Ghi chú

- Nhận diện chuỗi tiếng Việt / Anh / Trung. ROM ngôn ngữ khác thì dùng `--manual`.
- Mật khẩu được gõ bằng `adb shell input text` — không rời khỏi máy tính và điện thoại,
  nhưng vẫn hiện trong lệnh adb trên máy. Đừng dùng trên máy không phải của bạn.
- Đổi/bớt số điện thoại có thể ảnh hưởng tới trạng thái bind bootloader. Nếu đang trong
  168 giờ chờ unlock thì **đừng sửa gì** cho tới khi unlock xong.
- Tool chỉ là lớp tự động hoá UI. Xiaomi đổi giao diện là có thể hỏng — khi đó dùng `open`
  và bấm tay.

## License

MIT © 2026 Tấn Đạt Cáp (Penz7)
