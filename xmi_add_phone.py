#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xmi_add_phone.py — Thêm số điện thoại vào tài khoản Xiaomi khi mục này bị ẩn.

Vì sao cần: MIUI/HyperOS bản global (đặc biệt tài khoản tạo qua Google/Facebook)
ẩn mục "Số điện thoại" khỏi Cài đặt → Tài khoản Xiaomi → Bảo mật tài khoản.
Hậu quả: mở bootloader bằng Mi Unlock trả lỗi 20041
"MI ID is not associated with a phone number".

Cách làm: mở thẳng Activity bị ẩn com.xiaomi.account/.ui.UserPhoneInfoActivity
qua ADB, rồi điều khiển UI bằng uiautomator để thêm số.

Không cần root. Không sửa gì trong hệ thống. Chỉ dùng ADB (USB debugging).

Author: Tấn Đạt Cáp (Penz7)
License: MIT
"""

import argparse
import getpass
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ACTIVITY = "com.xiaomi.account/.ui.UserPhoneInfoActivity"
DUMP_PATH = "/sdcard/xmi_dump.xml"

# ---------------------------------------------------------------- adb helpers


class Device:
    def __init__(self, serial=None, adb="adb", debug=False, wait=1.6):
        self.adb = adb
        self.serial = serial
        self.debug = debug
        self.wait = wait

    def _cmd(self, args):
        cmd = [self.adb]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd + args

    def sh(self, *args, timeout=25):
        try:
            p = subprocess.run(
                self._cmd(["shell", *args]),
                capture_output=True, text=True, timeout=timeout,
            )
            return (p.stdout or "").replace("\r\n", "\n").replace("\r", "")
        except subprocess.TimeoutExpired:
            return ""
        except FileNotFoundError:
            sys.exit("Không tìm thấy adb. Cài platform-tools hoặc dùng --adb /duong/dan/adb")

    def raw(self, *args):
        try:
            p = subprocess.run(self._cmd(list(args)), capture_output=True, text=True)
            return p.stdout + p.stderr
        except FileNotFoundError:
            sys.exit("Không tìm thấy adb.")

    # -- ui ---------------------------------------------------------------

    def dump(self):
        """Trả về list node: dict(text, cls, res, bounds(x1,y1,x2,y2), password)."""
        self.sh("uiautomator", "dump", DUMP_PATH)
        xml = self.sh("cat", DUMP_PATH)
        start = xml.find("<?xml")
        if start < 0:
            start = xml.find("<hierarchy")
        if start < 0:
            return []
        xml = xml[start:]
        end = xml.rfind(">")
        xml = xml[: end + 1]
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        out = []
        for n in root.iter("node"):
            b = n.get("bounds", "")
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
            if not m:
                continue
            out.append({
                "text": (n.get("text") or "").strip(),
                "desc": (n.get("content-desc") or "").strip(),
                "cls": n.get("class", ""),
                "res": n.get("resource-id", ""),
                "password": n.get("password") == "true",
                "checkable": n.get("checkable") == "true",
                "checked": n.get("checked") == "true",
                "clickable": n.get("clickable") == "true",
                "bounds": tuple(int(x) for x in m.groups()),
            })
        return out

    def tap(self, node):
        x1, y1, x2, y2 = node["bounds"]
        self.sh("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
        time.sleep(self.wait)

    def type_text(self, node, text):
        self.tap(node)
        self.sh("input", "text", text.replace(" ", "%s"))
        time.sleep(self.wait)

    def key(self, code):
        self.sh("input", "keyevent", str(code))
        time.sleep(0.6)


# ---------------------------------------------------------------- patterns

ADD_BTN = [
    "Thêm số điện thoại", "Thêm số điện thoại mới",
    "Add phone number", "Add a phone number",
    "添加电话号码", "添加手机号", "绑定手机号",
]
CHANGE = [
    "Thay đổi số điện thoại", "Đổi số điện thoại",
    "Change phone number", "更改手机号", "更换手机号",
]
VERIFY = [
    "Xác thực Tài khoản", "Xác minh danh tính", "Bạn cần nhập mật khẩu",
    "Verify", "Verify your identity", "身份验证", "请输入密码",
]
SUBMIT = [
    "Gửi", "Tiếp theo", "Xác nhận", "Đồng ý", "Lưu",
    "Submit", "Next", "Confirm", "Continue", "Send", "OK",
    "发送", "下一步", "确定",
]
OTP_HINT = [
    "mã xác minh", "mã xác nhận", "nhập mã", "verification code", "verify code",
    "验证码",
]
LINKED_HINT = ["liên kết", "linked", "已绑定"]
MASKED = re.compile(r"(\+\d{1,3}[\s\d\*]{6,}|\b0\d[\d\s\*]{6,})")


def _has(nodes, patterns):
    for n in nodes:
        t = (n["text"] + " " + n["desc"]).strip()
        if not t:
            continue
        for p in patterns:
            if p.lower() in t.lower():
                return n
    return None


def _edit_texts(nodes, password=None):
    out = [n for n in nodes if "EditText" in n["cls"]]
    if password is True:
        return [n for n in out if n["password"]]
    if password is False:
        return [n for n in out if not n["password"]]
    return out


def _buttons(nodes):
    return [n for n in nodes if "Button" in n["cls"]]


def _shot(dev, nodes, title):
    print(f"  [{title}]")
    for n in nodes:
        if n["text"]:
            print(f"    · {n['text'][:90]}")


# ---------------------------------------------------------------- states

S_LINKED, S_ADD, S_VERIFY, S_PHONE, S_OTP, S_UNKNOWN = range(6)


def detect(dev):
    nodes = dev.dump()
    texts = " ".join(n["text"] for n in nodes)

    if _has(nodes, CHANGE):
        return S_LINKED, nodes
    add = _has(nodes, ADD_BTN)
    if add:
        return S_ADD, nodes
    if _has(nodes, VERIFY) and _edit_texts(nodes, password=True):
        return S_VERIFY, nodes
    if _has(nodes, OTP_HINT) and _edit_texts(nodes, password=False):
        return S_OTP, nodes
    if _has(nodes, SUBMIT) and _edit_texts(nodes, password=False):
        return S_PHONE, nodes
    if MASKED.search(texts) and _has(nodes, LINKED_HINT):
        return S_LINKED, nodes
    return S_UNKNOWN, nodes


# ---------------------------------------------------------------- actions

def open_page(dev):
    dev.sh("am", "start", "-n", ACTIVITY)
    time.sleep(2.0)


def linked_number(nodes):
    for n in nodes:
        m = MASKED.search(n["text"])
        if m:
            return m.group(1).strip()
    return None


def add_phone(dev, phone, password=None, otp=None, manual=False):
    open_page(dev)
    for step in range(14):
        state, nodes = detect(dev)

        if state == S_LINKED:
            num = linked_number(nodes)
            print(f"\n✔ Tài khoản đã có số điện thoại liên kết: {num or '(không đọc được số)'}")
            return 0

        if state == S_ADD:
            print("\n→ Tìm thấy nút thêm số điện thoại, bấm vào…")
            dev.tap(_has(nodes, ADD_BTN))
            continue

        if state == S_VERIFY:
            print("\n→ Xiaomi yêu cầu xác thực lại mật khẩu tài khoản.")
            field = _edit_texts(nodes, password=True)[0]
            if password is None and not manual:
                password = getpass.getpass("  Mật khẩu tài khoản Xiaomi: ")
            if password:
                dev.type_text(field, password)
                btn = _has(nodes, SUBMIT) or (_buttons(nodes) or [None])[-1]
                if btn:
                    dev.tap(btn)
                else:
                    dev.key(66)
            else:
                input("  Nhập mật khẩu trên điện thoại rồi bấm Enter ở đây… ")
            continue

        if state == S_PHONE:
            print(f"\n→ Nhập số điện thoại: {phone}")
            field = _edit_texts(nodes, password=False)[0]
            dev.type_text(field, phone)
            btn = _has(nodes, SUBMIT) or (_buttons(nodes) or [None])[-1]
            if btn:
                dev.tap(btn)
            else:
                dev.key(66)
            continue

        if state == S_OTP:
            print("\n→ Xiaomi đã gửi mã xác minh (SMS/email).")
            if otp is None:
                otp = input("  Nhập mã xác minh: ").strip()
            field = _edit_texts(nodes, password=False)[0]
            dev.type_text(field, otp)
            btn = _has(nodes, SUBMIT) or (_buttons(nodes) or [None])[-1]
            if btn:
                dev.tap(btn)
            else:
                dev.key(66)
            otp = None
            continue

        # unknown state
        _shot(dev, nodes, f"bước {step + 1}: không nhận diện được màn hình")
        if manual:
            input("  Làm tiếp trên điện thoại rồi bấm Enter… ")
            continue
        print("\n✖ Không nhận diện được màn hình. Chạy lại với --manual để tự bấm tay,")
        print("  hoặc --debug để xem toàn bộ cây UI.")
        return 2

    print("\n✖ Quá số bước cho phép, dừng lại để tránh bấm loạn.")
    return 2


# ---------------------------------------------------------------- main

def list_devices(adb):
    p = subprocess.run([adb, "devices"], capture_output=True, text=True)
    out = []
    for line in p.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            out.append(parts[0])
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Thêm số điện thoại vào tài khoản Xiaomi khi mục này bị ẩn trong Cài đặt.")
    ap.add_argument("action", choices=["check", "open", "add"],
                    help="check: xem tài khoản đã có SĐT chưa | open: mở trang ẩn | add: thêm số")
    ap.add_argument("--phone", help="Số cần thêm, dạng +84914123456 hoặc 0914123456")
    ap.add_argument("--password", help="Mật khẩu tài khoản (bỏ trống sẽ hỏi, an toàn hơn)")
    ap.add_argument("--otp", help="Mã xác minh, nếu đã có sẵn")
    ap.add_argument("--serial", help="Serial thiết bị (khi cắm nhiều máy)")
    ap.add_argument("--adb", default="adb", help="Đường dẫn tới adb")
    ap.add_argument("--manual", action="store_true",
                    help="Không tự bấm; chỉ mở trang và để người dùng thao tác")
    ap.add_argument("--debug", action="store_true", help="In toàn bộ cây UI mỗi bước")
    args = ap.parse_args()

    devices = list_devices(args.adb)
    if not devices:
        sys.exit("Không thấy thiết bị nào. Bật USB debugging và cấp quyền trên điện thoại.")
    serial = args.serial or devices[0]
    if args.serial is None and len(devices) > 1:
        print(f"Có {len(devices)} thiết bị, dùng {serial}. Chọn máy khác bằng --serial.")

    dev = Device(serial=serial, adb=args.adb, debug=args.debug)

    if args.action == "open":
        open_page(dev)
        print("Đã mở trang Số điện thoại bị ẩn. Tự thao tác trên điện thoại.")
        return 0

    if args.action == "check":
        open_page(dev)
        state, nodes = detect(dev)
        if state == S_LINKED:
            print(f"Đã liên kết: {linked_number(nodes) or '(không đọc được số)'}")
            return 0
        if state == S_ADD:
            print("Chưa có số điện thoại liên kết (có nút 'Thêm số điện thoại').")
            print("Chạy:  xmi_add_phone.py add --phone +84xxxxxxxxx")
            return 1
        print("Không xác định được trạng thái, xem chi tiết bằng --debug.")
        return 2

    # action == add
    if not args.phone:
        sys.exit("Thiếu --phone. Ví dụ: --phone +84914123456")
    return add_phone(dev, args.phone, args.password, args.otp, args.manual)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit("\nĐã huỷ.")
