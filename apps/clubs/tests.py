from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from apps.clubs.models import Category, ClubPlayer, Session, Attendance

User = get_user_model()


class AttendanceModelTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='U15', min_age=14, max_age=15)
        self.player1 = ClubPlayer.objects.create(
            first_name='أحمد',
            last_name='بن علي',
            date_of_birth='2011-05-10',
            category=self.category,
            is_active=True
        )
        self.player2 = ClubPlayer.objects.create(
            first_name='ياسين',
            last_name='قدور',
            date_of_birth='2011-08-20',
            category=self.category,
            is_active=True
        )
        self.session = Session.objects.create(
            team=self.category,
            date=timezone.now().date(),
            kind=Session.Kind.TRAINING,
            title='تدريب صباحي'
        )

    def test_session_creation_and_properties(self):
        self.assertEqual(self.session.team, self.category)
        self.assertEqual(self.session.total_players_count, 2)
        self.assertEqual(self.session.recorded_attendances_count, 0)

        # Create attendance
        att = Attendance.objects.create(
            session=self.session,
            player=self.player1,
            status=Attendance.Status.PRESENT
        )
        self.assertEqual(self.session.recorded_attendances_count, 1)
        self.assertEqual(self.session.present_count, 1)
        self.assertEqual(self.session.absent_count, 0)
        self.assertIn('حاضر', str(att))

    def test_attendance_unique_together(self):
        Attendance.objects.create(
            session=self.session,
            player=self.player1,
            status=Attendance.Status.PRESENT
        )
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(
                session=self.session,
                player=self.player1,
                status=Attendance.Status.ABSENT
            )


class AttendancePermissionsTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='U17', min_age=16, max_age=17)
        self.session = Session.objects.create(
            team=self.category,
            date=timezone.now().date(),
            kind=Session.Kind.TRAINING
        )

        self.viewer_user = User.objects.create_user(
            username='viewer_user', password='password123', role='viewer'
        )
        self.coach_user = User.objects.create_user(
            username='coach_user', password='password123', role='coach'
        )
        self.admin_user = User.objects.create_user(
            username='admin_user', password='password123', role='admin'
        )

        # User belonging to auth group 'coach'
        self.group_coach_user = User.objects.create_user(
            username='group_coach_user', password='password123', role='viewer'
        )
        coach_group, _ = Group.objects.get_or_create(name='coach')
        self.group_coach_user.groups.add(coach_group)

        self.client = Client()

    def test_unauthenticated_user_redirected(self):
        url = reverse('clubs:session_list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)

    def test_viewer_access_denied(self):
        self.client.login(username='viewer_user', password='password123')
        url = reverse('clubs:session_list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_coach_access_granted(self):
        self.client.login(username='coach_user', password='password123')
        url = reverse('clubs:session_list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_admin_access_granted(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('clubs:session_list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_group_coach_user_access_granted(self):
        self.client.login(username='group_coach_user', password='password123')
        url = reverse('clubs:session_list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)


class AttendanceHTMXAndStatsTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='U20', min_age=18, max_age=20)
        self.player1 = ClubPlayer.objects.create(
            first_name='كريم', last_name='سليماني', date_of_birth='2006-03-15', category=self.category, is_active=True
        )
        self.player2 = ClubPlayer.objects.create(
            first_name='سامي', last_name='بلحاج', date_of_birth='2006-07-22', category=self.category, is_active=True
        )
        self.session = Session.objects.create(
            team=self.category,
            date=timezone.now().date(),
            kind=Session.Kind.TRAINING
        )
        self.coach_user = User.objects.create_user(
            username='coach_tester', password='password123', role='coach'
        )
        self.client = Client()
        self.client.login(username='coach_tester', password='password123')

    def test_attendance_record_htmx(self):
        url = reverse('clubs:attendance_record', kwargs={
            'session_pk': self.session.pk,
            'player_pk': self.player1.pk
        })
        res = self.client.post(url, {'status': 'late', 'note': 'تأخر 10 دقائق'})
        self.assertEqual(res.status_code, 200)

        # Check DB
        att = Attendance.objects.get(session=self.session, player=self.player1)
        self.assertEqual(att.status, Attendance.Status.LATE)
        self.assertEqual(att.note, 'تأخر 10 دقائق')

        # Check response has out-of-band swap
        content = res.content.decode('utf-8')
        self.assertIn('hx-swap-oob="true"', content)
        self.assertIn('متأخر', content)

    def test_attendance_mark_all_present_htmx(self):
        url = reverse('clubs:attendance_mark_all_present', kwargs={'session_pk': self.session.pk})
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)

        # Check all players have present status
        self.assertEqual(Attendance.objects.filter(session=self.session, status='present').count(), 2)

    def test_attendance_stats_view(self):
        # player1 attended, player2 absent
        Attendance.objects.create(session=self.session, player=self.player1, status='present')
        Attendance.objects.create(session=self.session, player=self.player2, status='absent')

        url = reverse('clubs:attendance_stats')
        res = self.client.get(url, {'category': self.category.pk})
        self.assertEqual(res.status_code, 200)

        stats = res.context['player_stats']
        self.assertEqual(len(stats), 2)

        p1_stat = next(s for s in stats if s['player'] == self.player1)
        self.assertEqual(p1_stat['present'], 1)
        self.assertEqual(p1_stat['rate'], 100.0)

        p2_stat = next(s for s in stats if s['player'] == self.player2)
        self.assertEqual(p2_stat['absent'], 1)
        self.assertEqual(p2_stat['rate'], 0.0)


# ==============================================================================
# اختبارات بوابة ولي الأمر والخصوصية والإعلانات (Guardian Portal & Privacy Tests)
# ==============================================================================

import datetime
from django.core.management import call_command
from apps.clubs.models import Guardian, Announcement, Receipt, ClubMatch, format_algerian_phone_for_whatsapp


class GuardianPrivacyTestCase(TestCase):
    """اختبارات صارمة للخصوصية: ولي أمر لا يرى أبناء غيره"""
    def setUp(self):
        self.cat_u15 = Category.objects.create(name='U15', min_age=14, max_age=15)
        self.cat_u17 = Category.objects.create(name='U17', min_age=16, max_age=17)

        # Player A belongs to Guardian A
        self.player_a = ClubPlayer.objects.create(
            first_name='يوسف', last_name='منصوري', date_of_birth='2011-01-10', category=self.cat_u15, is_active=True,
            parent_phone='0550112233'
        )
        self.user_guardian_a = User.objects.create_user(
            username='guardian_a', password='password123', role='parent'
        )
        self.guardian_a = Guardian.objects.create(
            user=self.user_guardian_a, phone='0550112233', relationship='أب'
        )
        self.guardian_a.players.add(self.player_a)

        # Player B belongs to Guardian B
        self.player_b = ClubPlayer.objects.create(
            first_name='أمين', last_name='بوعلام', date_of_birth='2009-04-12', category=self.cat_u17, is_active=True,
            parent_phone='0661998877'
        )
        self.user_guardian_b = User.objects.create_user(
            username='guardian_b', password='password123', role='parent'
        )
        self.guardian_b = Guardian.objects.create(
            user=self.user_guardian_b, phone='0661998877', relationship='أب'
        )
        self.guardian_b.players.add(self.player_b)

        self.client = Client()

    def test_guardian_portal_shows_only_own_children(self):
        self.client.login(username='guardian_a', password='password123')
        res = self.client.get(reverse('clubs:guardian_portal'))
        self.assertEqual(res.status_code, 200)

        kids = [item['player'] for item in res.context['kids_data']]
        self.assertIn(self.player_a, kids)
        self.assertNotIn(self.player_b, kids)

        content = res.content.decode('utf-8')
        self.assertIn('يوسف منصوري', content)
        self.assertNotIn('أمين بوعلام', content)

    def test_guardian_cannot_access_other_child_detail(self):
        # Guardian A trying to access Player B detail page
        self.client.login(username='guardian_a', password='password123')
        url_b = reverse('clubs:player_detail', kwargs={'pk': self.player_b.pk})
        res = self.client.get(url_b)
        self.assertEqual(res.status_code, 403)

        # Guardian A accessing own child Player A
        url_a = reverse('clubs:player_detail', kwargs={'pk': self.player_a.pk})
        res = self.client.get(url_a)
        self.assertEqual(res.status_code, 200)
        self.assertIn('يوسف منصوري', res.content.decode('utf-8'))


class AnnouncementAndReceiptTestCase(TestCase):
    def setUp(self):
        self.cat_u15 = Category.objects.create(name='U15', min_age=14, max_age=15)
        self.cat_u17 = Category.objects.create(name='U17', min_age=16, max_age=17)

        self.player_a = ClubPlayer.objects.create(
            first_name='بلال', last_name='حداد', date_of_birth='2011-02-14', category=self.cat_u15, is_active=True
        )
        self.user_guardian_a = User.objects.create_user(
            username='guardian_a2', password='password123', role='parent'
        )
        self.guardian_a = Guardian.objects.create(user=self.user_guardian_a, phone='0555001122')
        self.guardian_a.players.add(self.player_a)

        self.coach_user = User.objects.create_user(
            username='coach_u15', password='password123', role='coach'
        )

        # 1 Announcement for U15
        self.ann_u15 = Announcement.objects.create(
            team=self.cat_u15,
            title='تغيير موعد تدريب U15',
            body='سيكون التدريب غداً على الساعة 09:00 صباحاً.',
            author=self.coach_user
        )

        # 1 Announcement for U17
        self.ann_u17 = Announcement.objects.create(
            team=self.cat_u17,
            title='استدعاء U17',
            body='مباراة يوم السبت لفئة U17.',
            author=self.coach_user
        )

        # 1 General Announcement for all
        self.ann_all = Announcement.objects.create(
            team=None,
            title='إعلان عام لإدارة النادي',
            body='اجتماع عام لجميع أولياء الأمور.',
            author=self.coach_user
        )

        self.client = Client()

    def test_guardian_receives_only_relevant_announcements_and_records_receipt(self):
        self.client.login(username='guardian_a2', password='password123')
        res = self.client.get(reverse('clubs:guardian_portal'))
        self.assertEqual(res.status_code, 200)

        announcements = res.context['announcements']
        self.assertIn(self.ann_u15, announcements)
        self.assertIn(self.ann_all, announcements)
        self.assertNotIn(self.ann_u17, announcements)

        # Check Receipt auto-recorded
        self.assertTrue(Receipt.objects.filter(announcement=self.ann_u15, guardian=self.guardian_a).exists())
        self.assertTrue(Receipt.objects.filter(announcement=self.ann_all, guardian=self.guardian_a).exists())
        self.assertFalse(Receipt.objects.filter(announcement=self.ann_u17, guardian=self.guardian_a).exists())

        # Check metrics
        self.assertEqual(self.ann_u15.read_count, 1)
        self.assertEqual(self.ann_u15.read_percentage, 100)


class WhatsAppPhoneFormatTestCase(TestCase):
    def test_format_algerian_phone(self):
        self.assertEqual(format_algerian_phone_for_whatsapp('0550123456'), '213550123456')
        self.assertEqual(format_algerian_phone_for_whatsapp('0661987654'), '213661987654')
        self.assertEqual(format_algerian_phone_for_whatsapp('0770112233'), '213770112233')
        self.assertEqual(format_algerian_phone_for_whatsapp('+213550123456'), '213550123456')
        self.assertEqual(format_algerian_phone_for_whatsapp('00213550123456'), '213550123456')
        self.assertEqual(format_algerian_phone_for_whatsapp(''), '')

    def test_attendance_whatsapp_absence_url(self):
        category = Category.objects.create(name='U15', min_age=14, max_age=15)
        player = ClubPlayer.objects.create(
            first_name='حمزة', last_name='دحماني', date_of_birth='2011-06-18', category=category,
            parent_phone='0555123456'
        )
        session = Session.objects.create(
            team=category,
            date=datetime.date(2026, 10, 26),
            kind=Session.Kind.TRAINING
        )
        att = Attendance.objects.create(session=session, player=player, status='absent')
        url = att.whatsapp_absence_url
        self.assertTrue(url.startswith('https://wa.me/213555123456?text='))
        self.assertIn('%D8%BA%D9%8A%D8%A7%D8%A8', url)  # encoded 'غياب'


class MatchReminderCommandTestCase(TestCase):
    def test_send_match_reminders_command(self):
        category = Category.objects.create(name='U20', min_age=18, max_age=20)
        tomorrow = timezone.now().date() + datetime.timedelta(days=1)
        ClubMatch.objects.create(
            category=category,
            date=tomorrow,
            time=datetime.time(10, 0),
            opponent='شبيبة الداموس',
            location='الملعب البلدي مسالمون',
            is_home=True
        )

        call_command('send_match_reminders', days=1)

        # Check that announcement was created for category U20
        announcement = Announcement.objects.filter(team=category).first()
        self.assertIsNotNone(announcement)
        self.assertIn('شبيبة الداموس', announcement.title)
        self.assertIn('شبيبة الداموس', announcement.body)

