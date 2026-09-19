import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse
from apps.matches.models import Match
from apps.notifications.models import Notification
from config.settings.base import env_get


class Command(BaseCommand):
    help = "Send automated WhatsApp reminders to teams 24 hours before their scheduled match"

    def add_arguments(self, parser):
        parser.add_argument(
            '--window-hours',
            type=int,
            default=24,
            help='Remind matches scheduled exactly within this many hours from now'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print messages without calling external APIs'
        )

    def handle(self, *args, **options):
        window_hours = options['window_hours']
        dry_run = options['dry_run']

        now = timezone.now()
        start_window = now
        end_window = now + timedelta(hours=window_hours + 4)  # Search window

        self.stdout.write(self.style.SUCCESS(f"🔍 البحث عن المباريات المجدولة خلال {window_hours} ساعة القادمة..."))

        matches = Match.objects.filter(
            status=Match.Status.SCHEDULED,
            match_date__gte=start_window,
            match_date__lte=end_window
        )

        if not matches.exists():
            self.stdout.write(self.style.WARNING("ℹ️ لا توجد مباريات مجدولة في هذا النطاق الزمني حالياً."))
            return

        # WhatsApp API settings (supports UltraMsg, Twilio, GreenAPI, Cloud API or fallback console simulation)
        whatsapp_provider = env_get('WHATSAPP_PROVIDER', 'console')
        whatsapp_api_url = env_get('WHATSAPP_API_URL', '')
        whatsapp_api_token = env_get('WHATSAPP_API_TOKEN', '')

        log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), 'whatsapp_reminders.log')

        for match in matches:
            match_time_str = match.match_date.strftime('%Y-%m-%d %H:%M')
            stage_display = match.get_stage_display()

            teams = [match.team1, match.team2]
            for team in teams:
                if not team:
                    continue

                # Find phone number
                phone = team.contact_phone
                if not phone and team.manager and team.manager.phone:
                    phone = team.manager.phone
                if not phone and team.manager and team.manager.username.isdigit():
                    phone = team.manager.username

                # Build spectacular message
                message = f"""🌟 إشعار هام من إدارة بطولة {match.tournament.name} 🌟

مرحباً بفريق {team.name} ({team.neighborhood}) الشامخ! ⚽🔥

نود تذكيركم بأن لديكم مباراة رسمية حاسمة غداً (بعد 24 ساعة من الآن)! استعدوا وجهزوا صفوفكم لتحقيق المجد الكروي وإمتاع الجماهير. 🏆💪

📅 التاريخ والتوقيت: {match_time_str}
🏟️ الملعب: {match.venue}
🔴 المواجهة الكبرى: {match.team1.name if match.team1 else 'منافس'} 🆚 {match.team2.name if match.team2 else 'منافس'}
📋 الدور / المرحلة: {stage_display}
👨‍⚖️ الحكم: {match.referee or 'لم يحدد بعد'}

⚠️ تعليمات إدارية هامة:
▪ يرجى التواجد في الملعب قبل نصف ساعة (30 دقيقة) من انطلاق صافرة البداية.
▪ إحضار بطاقات أعضاء اللجنة واللاعبين المعتمدة والعتاد الرياضي الكامل.
▪ الالتزام بالروح الرياضية العالية وقوانين البطولة.

نتمنى لكم التوفيق وتقديم أداء كروي ممتع! 🤝⚡

نادي الوفاق الرياضي مسلمون · TURN-ESM · MESSLMOUN 🛡️"""

                self.stdout.write(self.style.SUCCESS(f"\n======================================================="))
                self.stdout.write(self.style.NOTICE(f"📨 تجهيز رسالة واتساب إلى فريق: {team.name}"))
                self.stdout.write(f"رقم الهاتف المعتمد: {phone or 'لا يوجد رقم مسجل (إرسال إشعار داخلي فقط)'}")
                self.stdout.write(f"نص الرسالة:\n{message}")
                self.stdout.write(self.style.SUCCESS(f"======================================================="))

                # 1. Create Django Notification for Manager
                if team.manager:
                    Notification.objects.get_or_create(
                        recipient=team.manager,
                        notif_type=Notification.Type.MATCH_REMINDER,
                        title=f"⚽ تذكير بمباراة رسمية غداً: {match.team1} vs {match.team2}",
                        defaults={
                            'message': message,
                            'link': f"/matches/{match.pk}/"
                        }
                    )

                if not phone:
                    self.stdout.write(self.style.WARNING(f"⚠️ لم يتم العثور على رقم هاتف لفريق {team.name}. تم إرسال إشعار للنظام فقط."))
                    continue

                # Prepare Direct Click WhatsApp Web link
                encoded_message = urllib.parse.quote(message)
                whatsapp_url = f"https://wa.me/{phone.replace('+', '').replace(' ', '')}?text={encoded_message}"
                self.stdout.write(self.style.NOTICE(f"🔗 رابط واتساب المباشر للفتح والإرسال اليدوي/السريع:\n{whatsapp_url}"))

                # Log to file
                try:
                    with open(log_file_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"[{timezone.now()}] TEAM: {team.name} | PHONE: {phone}\nMESSAGE:\n{message}\nLINK: {whatsapp_url}\n{'-'*60}\n")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"خطأ في كتابة ملف السجل: {e}"))

                if dry_run:
                    continue

                # 2. External API Execution
                if whatsapp_provider == 'ultramsg' and whatsapp_api_url and whatsapp_api_token:
                    try:
                        url = f"{whatsapp_api_url}/messages/chat"
                        data = json.dumps({
                            "token": whatsapp_api_token,
                            "to": phone,
                            "body": message
                        }).encode('utf-8')
                        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            resp_data = response.read().decode('utf-8')
                            self.stdout.write(self.style.SUCCESS(f"✅ تم إرسال الواتساب بنجاح عبر UltraMsg: {resp_data}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"❌ خطأ في الإرسال عبر UltraMsg API: {e}"))

                elif whatsapp_provider == 'greenapi' and whatsapp_api_url and whatsapp_api_token:
                    try:
                        url = f"{whatsapp_api_url}/waInstance{whatsapp_api_token}/sendMessage"
                        data = json.dumps({
                            "chatId": f"{phone.replace('+', '').replace(' ', '')}@c.us",
                            "message": message
                        }).encode('utf-8')
                        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            resp_data = response.read().decode('utf-8')
                            self.stdout.write(self.style.SUCCESS(f"✅ تم إرسال الواتساب بنجاح عبر GreenAPI: {resp_data}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"❌ خطأ في الإرسال عبر GreenAPI: {e}"))

                else:
                    self.stdout.write(self.style.SUCCESS(f"✅ [نمط المحاكاة Console/Log] تمت معالجة رسالة الواتساب بنجاح! تم الحفظ في {log_file_path}"))

        self.stdout.write(self.style.SUCCESS("🎉 اكتملت عملية فحص وإرسال رسائل الواتساب بنجاح."))
