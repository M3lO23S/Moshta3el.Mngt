# -*- coding: utf-8 -*-
"""
MOSHTA3EL — Telegram Channel Manager
أداة طرفية لإدارة قناة تيليجرام عبر Telegram Bot API.
لا تطلب كلمة مرور حساب تيليجرام أو جلسة الحساب الشخصية.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

API_BASE = "https://api.telegram.org"
TIMEOUT = 30


class TelegramAPIError(RuntimeError):
    pass


class TelegramBot:
    def __init__(self, token: str):
        self.token = token.strip()
        self.base = f"{API_BASE}/bot{self.token}"

    def call(self, method: str, data: dict[str, Any] | None = None,
             files: dict[str, Any] | None = None) -> Any:
        try:
            response = requests.post(
                f"{self.base}/{method}",
                data=data or {},
                files=files,
                timeout=TIMEOUT,
            )
            payload = response.json()
        except requests.RequestException as exc:
            raise TelegramAPIError(f"تعذر الاتصال بتيليجرام: {exc}") from exc
        except ValueError as exc:
            raise TelegramAPIError("ردّ تيليجرام ليس JSON صالحًا.") from exc

        if not payload.get("ok"):
            description = payload.get("description", "خطأ غير معروف")
            code = payload.get("error_code", "?")
            raise TelegramAPIError(f"Telegram API ({code}): {description}")
        return payload.get("result")

    def get_me(self):
        return self.call("getMe")

    def get_chat(self, chat_id: str):
        return self.call("getChat", {"chat_id": chat_id})

    def get_admins(self, chat_id: str):
        return self.call("getChatAdministrators", {"chat_id": chat_id})

    def send_text(self, chat_id: str, text: str):
        return self.call("sendMessage", {
            "chat_id": chat_id, "text": text, "disable_web_page_preview": "true"
        })

    def send_photo(self, chat_id: str, path: str, caption: str = ""):
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            raise ValueError("لم أجد ملف الصورة في هذا المسار.")
        with file_path.open("rb") as photo:
            return self.call(
                "sendPhoto",
                {"chat_id": chat_id, "caption": caption},
                {"photo": (file_path.name, photo)},
            )

    def set_title(self, chat_id: str, title: str):
        return self.call("setChatTitle", {"chat_id": chat_id, "title": title})

    def set_description(self, chat_id: str, description: str):
        return self.call("setChatDescription", {
            "chat_id": chat_id, "description": description
        })

    def set_photo(self, chat_id: str, path: str):
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            raise ValueError("لم أجد ملف الصورة في هذا المسار.")
        with file_path.open("rb") as photo:
            return self.call(
                "setChatPhoto",
                {"chat_id": chat_id},
                {"photo": (file_path.name, photo)},
            )

    def delete_message(self, chat_id: str, message_id: int):
        return self.call("deleteMessage", {
            "chat_id": chat_id, "message_id": message_id
        })

    def edit_message(self, chat_id: str, message_id: int, text: str):
        return self.call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text,
            "disable_web_page_preview": "true"
        })

    def pin_message(self, chat_id: str, message_id: int, disable_notification: bool = True):
        return self.call("pinChatMessage", {
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": str(disable_notification).lower(),
        })

    def unpin_message(self, chat_id: str, message_id: int | None = None):
        data = {"chat_id": chat_id}
        if message_id is not None:
            data["message_id"] = message_id
        return self.call("unpinChatMessage", data)

    def promote_admin(self, chat_id: str, user_id: int, rights: dict[str, bool],
                      is_anonymous: bool = False):
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "is_anonymous": str(is_anonymous).lower(),
        }
        data.update({key: str(value).lower() for key, value in rights.items()})
        return self.call("promoteChatMember", data)

    def demote_admin(self, chat_id: str, user_id: int):
        rights = {
            "can_change_info": False,
            "can_post_messages": False,
            "can_edit_messages": False,
            "can_delete_messages": False,
            "can_invite_users": False,
            "can_restrict_members": False,
            "can_pin_messages": False,
            "can_promote_members": False,
            "can_manage_video_chats": False,
        }
        return self.promote_admin(chat_id, user_id, rights, False)


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else (default or "")


def pause():
    input("\nاضغط Enter للمتابعة...")


def show_chat(bot: TelegramBot, chat_id: str):
    chat = bot.get_chat(chat_id)
    print("\n--- معلومات القناة ---")
    for key, label in (
        ("title", "الاسم"),
        ("username", "المعرّف العام"),
        ("description", "الوصف"),
        ("type", "النوع"),
        ("id", "Chat ID"),
    ):
        value = chat.get(key)
        if value is not None:
            print(f"{label}: {value}")
    return chat


def show_admins(bot: TelegramBot, chat_id: str):
    admins = bot.get_admins(chat_id)
    print("\n--- مشرفو القناة ---")
    for admin in admins:
        user = admin.get("user", {})
        name = " ".join(filter(None, [
            user.get("first_name", ""),
            user.get("last_name", ""),
        ]))
        username = f"@{user['username']}" if user.get("username") else "لا يوجد username"
        print(
            f"- {name or 'بدون اسم'} | {username} | ID: {user.get('id')} "
            f"| الصفة: {admin.get('status')}"
        )
    return admins


def manage_admins(bot: TelegramBot, chat_id: str):
    print("\n1) عرض المشرفين\n2) ترقية مستخدم إلى مشرف\n3) خفض صلاحيات مشرف")
    choice = ask("اختر")
    if choice == "1":
        show_admins(bot, chat_id)
        return
    if choice == "3":
        user_id = ask("معرّف المستخدم الرقمي")
        if not user_id.isdigit():
            print("المعرّف يجب أن يكون رقمًا.")
            return
        confirm = ask("اكتب DEMOTE للتأكيد")
        if confirm == "DEMOTE":
            bot.demote_admin(chat_id, int(user_id))
            print("أُرسل طلب خفض الصلاحيات إلى تيليجرام.")
        else:
            print("تم الإلغاء.")
        return
    if choice != "2":
        print("اختيار غير صحيح.")
        return

    user_id = ask("معرّف المستخدم الرقمي المراد ترقيته")
    if not user_id.isdigit():
        print("المعرّف يجب أن يكون رقمًا.")
        return
    print("حدد الصلاحيات المطلوبة (y/n). اتركها فارغة لاختيار n.")
    rights = {
        "can_change_info": ask("تغيير معلومات القناة؟ (y/n)", "n").lower() == "y",
        "can_post_messages": ask("نشر الرسائل؟ (y/n)", "y").lower() == "y",
        "can_edit_messages": ask("تعديل رسائل القناة؟ (y/n)", "y").lower() == "y",
        "can_delete_messages": ask("حذف الرسائل؟ (y/n)", "n").lower() == "y",
        "can_invite_users": ask("دعوة المستخدمين؟ (y/n)", "n").lower() == "y",
        "can_restrict_members": ask("تقييد الأعضاء؟ (y/n)", "n").lower() == "y",
        "can_pin_messages": ask("تثبيت الرسائل؟ (y/n)", "n").lower() == "y",
        "can_promote_members": ask("إضافة مشرفين آخرين؟ (y/n)", "n").lower() == "y",
        "can_manage_video_chats": ask("إدارة المحادثات الصوتية/المرئية؟ (y/n)", "n").lower() == "y",
    }
    anon = ask("إخفاء هوية المشرف؟ (y/n)", "n").lower() == "y"
    confirm = ask("اكتب PROMOTE للتأكيد")
    if confirm == "PROMOTE":
        bot.promote_admin(chat_id, int(user_id), rights, anon)
        print("أُرسل طلب ترقية المشرف إلى تيليجرام.")
    else:
        print("تم الإلغاء.")


def menu(bot: TelegramBot, chat_id: str):
    while True:
        print("""
================ Moshta3el | Channel Manager ================
1) معلومات القناة
2) تغيير اسم القناة
3) تغيير وصف القناة
4) تغيير صورة القناة
5) نشر رسالة
6) نشر صورة مع وصف
7) تعديل منشور نصي بواسطة Message ID
8) حذف منشور بواسطة Message ID
9) تثبيت منشور بواسطة Message ID
10) إلغاء تثبيت منشور
11) إدارة المشرفين والصلاحيات
12) تغيير القناة المستهدفة
0) خروج
=============================================================
""")
        choice = ask("اختر العملية")
        try:
            if choice == "0":
                print("تم الخروج.")
                return
            elif choice == "1":
                show_chat(bot, chat_id)
            elif choice == "2":
                title = ask("الاسم الجديد")
                if title:
                    bot.set_title(chat_id, title)
                    print("تم تغيير الاسم.")
            elif choice == "3":
                description = input("اكتب الوصف الجديد (فارغ لمسح الوصف): ").strip()
                bot.set_description(chat_id, description)
                print("تم تحديث الوصف.")
            elif choice == "4":
                path = ask("مسار الصورة على جهازك")
                bot.set_photo(chat_id, path)
                print("تم تحديث صورة القناة.")
            elif choice == "5":
                text = input("اكتب نص المنشور: ").strip()
                if text:
                    result = bot.send_text(chat_id, text)
                    print(f"تم النشر. Message ID: {result.get('message_id')}")
            elif choice == "6":
                path = ask("مسار الصورة")
                caption = input("الوصف (اختياري): ").strip()
                result = bot.send_photo(chat_id, path, caption)
                print(f"تم النشر. Message ID: {result.get('message_id')}")
            elif choice == "7":
                mid = ask("Message ID")
                text = input("النص الجديد: ").strip()
                if mid.isdigit() and text:
                    bot.edit_message(chat_id, int(mid), text)
                    print("تم تعديل المنشور.")
                else:
                    print("تحقق من Message ID والنص.")
            elif choice == "8":
                mid = ask("Message ID")
                if mid.isdigit() and ask("اكتب DELETE للتأكيد") == "DELETE":
                    bot.delete_message(chat_id, int(mid))
                    print("تم حذف المنشور.")
                else:
                    print("تم الإلغاء أو أن المعرّف غير صحيح.")
            elif choice == "9":
                mid = ask("Message ID")
                if mid.isdigit():
                    bot.pin_message(chat_id, int(mid))
                    print("تم تثبيت المنشور.")
            elif choice == "10":
                mid = ask("Message ID (اتركه فارغًا لإلغاء تثبيت الرسالة المثبتة)")
                bot.unpin_message(chat_id, int(mid) if mid.isdigit() else None)
                print("تم إلغاء التثبيت.")
            elif choice == "11":
                manage_admins(bot, chat_id)
            elif choice == "12":
                new_chat = ask("معرّف القناة أو @username")
                if new_chat:
                    show_chat(bot, new_chat)
                    chat_id = new_chat
            else:
                print("اختيار غير صحيح.")
        except (TelegramAPIError, ValueError, OSError) as exc:
            print(f"\n❌ تعذّر تنفيذ العملية: {exc}")
            print("تحقق من صلاحيات البوت، ومعرّف القناة، وقيود Telegram Bot API.")
        pause()


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║       Moshta3el — Telegram Channel Manager         ║
║          إدارة القنوات عبر Bot API                  ║
╚══════════════════════════════════════════════════════╝
""")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("أدخل توكن البوت من BotFather (لن يُعرض أثناء الكتابة): ").strip()
    if not token:
        print("لم يتم إدخال توكن.")
        return 1

    bot = TelegramBot(token)
    try:
        me = bot.get_me()
        print(f"\nتم الاتصال بالبوت: @{me.get('username', 'بدون username')}")
        chat_id = ask("معرّف القناة أو @username")
        if not chat_id:
            print("يجب إدخال معرّف القناة.")
            return 1
        chat = show_chat(bot, chat_id)
        if chat.get("type") != "channel":
            print("تنبيه: المعرف المدخل لا يبدو قناة. بعض الخيارات قد لا تعمل.")
        menu(bot, chat_id)
    except TelegramAPIError as exc:
        print(f"\nتعذر بدء الأداة: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
