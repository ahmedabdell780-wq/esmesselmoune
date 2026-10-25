import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.clubs.models import ClubMatch, Announcement

User = get_user_model()


class Command(BaseCommand):
    help = "يجهّز وينشر إعلانات تذكير بمباريات اليوم التالي لأولياء أمور الفئات المعنية"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='عدد الأيام المقبلة للبحث عن المباريات (الافتراضي: 1 لمباراة الغد)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فحص ومعاينة المباريات دون حفظ الإعلانات في قاعدة البيانات'
        )

    def handle(self, *args, **options):
        days_ahead = options['days']
        dry_run = options['dry_run']
        target_date = timezone.now().date() + datetime.timedelta(days=days_ahead)

        self.stdout.write(self.style.NOTICE(f"[*] جاري البحث عن مباريات نادي ESM لتاريخ: {target_date} (بعد {days_ahead} يوم)..."))

        matches = ClubMatch.objects.filter(date=target_date).select_related('category')
        if not matches.exists():
            self.stdout.write(self.style.WARNING(f"[-] لا توجد مباريات مبرمجة لتاريخ {target_date}."))
            return

        author = User.objects.filter(is_superuser=True).first() or User.objects.filter(role__in=['admin', 'organizer']).first()

        created_count = 0
        for match in matches:
            category_name = match.category.name if match.category else "عام"
            venue_type = "داخل الديار (الملعب البلدي مسالمون)" if match.is_home else "خارج الديار"
            time_str = match.time.strftime('%H:%M') if match.time else "يُحدد لاحقاً"

            title = f"تذكير بمباراة الغد: الوفاق ضد {match.opponent} ({category_name})"
            body = (
                f"السلام عليكم ورحمة الله،\n\n"
                f"نذكّر أولياء أمور ولاعبي فئة {category_name} بمباراة الغد الرسمية:\n"
                f"- المنافس: {match.opponent}\n"
                f"- التاريخ: {match.date.strftime('%Y-%m-%d')}\n"
                f"- التوقيت: {time_str}\n"
                f"- المكان: {match.location} ({venue_type})\n\n"
                f"تعليمات هامة:\n"
                f"- التواجد بمقر التجمع أو الملعب قبل ساعة من انطلاق المباراة.\n"
                f"- إحضار العتاد الرياضي الكامل (القميص الرسمي، واقي الساقين، الحذاء الملائم).\n"
                f"- بطاقة اللاعب ضرورية للدخول.\n\n"
                f"بالتوفيق لفرسان وفاق مسلمون!"
            )

            # Avoid duplicate announcement on same day for same match/team
            existing = Announcement.objects.filter(
                team=match.category,
                title=title,
                created_at__date=timezone.now().date()
            ).exists()

            if existing:
                self.stdout.write(self.style.WARNING(f"[!] إعلان المباراة لفئة {category_name} منشور مسبقاً اليوم."))
                continue

            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"[DRY-RUN] سيتم نشر إعلان: {title}"))
            else:
                announcement = Announcement.objects.create(
                    team=match.category,
                    title=title,
                    body=body,
                    author=author
                )
                target_guardians = announcement.target_guardians_count
                self.stdout.write(self.style.SUCCESS(
                    f"[+] تم نشر إعلان المباراة لفئة {category_name} (موجه لـ {target_guardians} ولي أمر)."
                ))
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"[+] اكتمل التجهيز. تم إنشاء {created_count} إعلان بنجاح."))
