from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User
from apps.tournaments.models import Tournament, TournamentTeam, TournamentExpense
from apps.teams.models import Team

class TournamentFinanceTests(TestCase):
    def setUp(self):
        # Create users with different roles
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='password123',
            role='admin'
        )
        self.organizer = User.objects.create_user(
            username='organizer_user',
            email='org@test.com',
            password='password123',
            role='organizer'
        )
        self.player_user = User.objects.create_user(
            username='player_user',
            email='player@test.com',
            password='password123',
            role='player'
        )

        # Create tournament
        self.tournament = Tournament.objects.create(
            name="Ligue des Champions d'Alger",
            year=2026,
            edition=1,
            subscription_price=1000.00
        )

        # Create team & register it
        self.team1 = Team.objects.create(name="MC Alger", neighborhood="Bab El Oued")
        self.tournament_team1 = TournamentTeam.objects.create(
            tournament=self.tournament,
            team=self.team1,
            is_confirmed=True,
            amount_paid=0.00,
            payment_confirmed=False
        )

        # Finance detail url
        self.url = reverse('tournaments:finance', kwargs={'pk': self.tournament.pk})

    def test_anonymous_user_redirected(self):
        """Anonymous users must be redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_unprivileged_user_forbidden(self):
        """Players should be forbidden from accessing the finance panel."""
        self.client.login(username='player_user', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_and_organizer_access_granted(self):
        """Admins and organizers should be granted access."""
        # Test Organizer
        self.client.login(username='organizer_user', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tournaments/finance.html')

        # Test Admin
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_update_subscription_price(self):
        """Test updating the tournament's registration/subscription fee."""
        self.client.login(username='admin_user', password='password123')
        post_data = {
            'action': 'update_price',
            'subscription_price': '2500.00'
        }
        response = self.client.post(self.url, post_data)
        self.assertRedirects(response, self.url)
        
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.subscription_price, 2500.00)

    def test_update_payments(self):
        """Test updating team payments."""
        self.client.login(username='admin_user', password='password123')
        post_data = {
            'action': 'update_payments',
            f'amount_paid_{self.team1.pk}': '1500.00',
            f'payment_confirmed_{self.team1.pk}': 'on'
        }
        response = self.client.post(self.url, post_data)
        self.assertRedirects(response, self.url)

        self.tournament_team1.refresh_from_db()
        self.assertEqual(self.tournament_team1.amount_paid, 1500.00)
        self.assertTrue(self.tournament_team1.payment_confirmed)

    def test_add_and_delete_expense(self):
        """Test adding a tournament expense and then deleting it."""
        self.client.login(username='admin_user', password='password123')
        
        # 1. Add expense
        post_data = {
            'action': 'add_expense',
            'title': 'Achat de ballons',
            'amount': '450.00',
            'notes': '5 ballons Adidas'
        }
        response = self.client.post(self.url, post_data)
        self.assertRedirects(response, self.url)

        expense = TournamentExpense.objects.get(tournament=self.tournament)
        self.assertEqual(expense.title, 'Achat de ballons')
        self.assertEqual(expense.amount, 450.00)
        self.assertEqual(expense.notes, '5 ballons Adidas')

        # 2. Delete expense
        delete_data = {
            'action': 'delete_expense',
            'expense_id': expense.pk
        }
        response = self.client.post(self.url, delete_data)
        self.assertRedirects(response, self.url)
        
        self.assertFalse(TournamentExpense.objects.filter(pk=expense.pk).exists())

    def test_payment_receipt_view_permissions_and_rendering(self):
        """Test that the printable receipt is accessible to admins/organizers and renders correctly."""
        receipt_url = reverse('tournaments:payment_receipt', kwargs={'pk': self.tournament_team1.pk})
        
        # 1. Anonymous forbidden/redirected
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 302)

        # 2. Unprivileged user forbidden
        self.client.login(username='player_user', password='password123')
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 403)

        # 3. Organizer allowed
        self.client.login(username='organizer_user', password='password123')
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tournaments/payment_receipt.html')

        # 4. Admin allowed & displays details
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MC Alger")
        self.assertContains(response, "1000")
        self.assertContains(response, "REC")

    def test_finance_report_view_permissions_and_rendering(self):
        """Test that the detailed final financial statement is accessible and renders correctly."""
        report_url = reverse('tournaments:finance_report', kwargs={'pk': self.tournament.pk})
        
        # 1. Anonymous forbidden/redirected
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 302)

        # 2. Unprivileged user forbidden
        self.client.login(username='player_user', password='password123')
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 403)

        # 3. Organizer allowed
        self.client.login(username='organizer_user', password='password123')
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tournaments/finance_report.html')

        # 4. Admin allowed & displays general metrics
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MC Alger")
        self.assertContains(response, "BILAN FINANCIER")


