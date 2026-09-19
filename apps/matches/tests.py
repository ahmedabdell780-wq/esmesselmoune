from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.db.utils import IntegrityError
from apps.accounts.models import User
from apps.tournaments.models import Tournament
from apps.teams.models import Team, Player
from apps.matches.models import Match, MatchVote, PlayerMatchPerformance
from apps.matches.views import MatchVoteView


from django.utils import timezone

class MatchVoteTests(TestCase):
    def setUp(self):
        # Create a tournament
        self.tournament = Tournament.objects.create(
            name="Test Tournament",
            year=2026,
            edition=1
        )
        
        # Create teams
        self.team1 = Team.objects.create(name="Team A")
        self.team2 = Team.objects.create(name="Team B")
        
        # Create players
        self.player1 = Player.objects.create(
            team=self.team1,
            first_name="Player",
            last_name="One",
            jersey_number=10,
            position="FWD",
            is_active=True,
            national_id="NID1"
        )
        self.player2 = Player.objects.create(
            team=self.team2,
            first_name="Player",
            last_name="Two",
            jersey_number=7,
            position="MID",
            is_active=True,
            national_id="NID2"
        )

        # Create a match
        self.match = Match.objects.create(
            tournament=self.tournament,
            team1=self.team1,
            team2=self.team2,
            status=Match.Status.LIVE,
            match_date=timezone.now()
        )

        # Create player performances
        self.perf1 = PlayerMatchPerformance.objects.create(
            match=self.match,
            player=self.player1,
            rating=7.5,
            is_starter=True
        )
        self.perf2 = PlayerMatchPerformance.objects.create(
            match=self.match,
            player=self.player2,
            rating=6.5,
            is_starter=True
        )

    def test_create_vote_success(self):
        """Test casting a vote successfully."""
        vote = MatchVote.objects.create(
            match=self.match,
            player=self.player1,
            user_ip="192.168.1.1"
        )
        self.assertEqual(vote.match, self.match)
        self.assertEqual(vote.player, self.player1)
        self.assertEqual(vote.user_ip, "192.168.1.1")
        self.assertEqual(self.match.votes.count(), 1)

    def test_unique_ip_vote_constraint(self):
        """Test that a user cannot vote twice for the same match from the same IP."""
        MatchVote.objects.create(
            match=self.match,
            player=self.player1,
            user_ip="192.168.1.1"
        )
        
        with self.assertRaises(IntegrityError):
            MatchVote.objects.create(
                match=self.match,
                player=self.player2,
                user_ip="192.168.1.1"
            )

    def test_vote_view_post_success(self):
        """Test POSTing a vote to MatchVoteView."""
        url = reverse('matches:vote', kwargs={'pk': self.match.pk})
        response = self.client.post(url, {'player_id': self.player1.pk}, REMOTE_ADDR="192.168.1.5")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MatchVote.objects.filter(match=self.match, user_ip="192.168.1.5").count(), 1)

    def test_vote_view_post_duplicate_blocked(self):
        """Test that MatchVoteView blocks duplicate votes from the same IP."""
        url = reverse('matches:vote', kwargs={'pk': self.match.pk})
        
        # First vote
        response1 = self.client.post(url, {'player_id': self.player1.pk}, REMOTE_ADDR="192.168.1.5")
        self.assertEqual(response1.status_code, 200)
        
        # Second vote from same IP
        response2 = self.client.post(url, {'player_id': self.player2.pk}, REMOTE_ADDR="192.168.1.5")
        self.assertEqual(response2.status_code, 400)
        self.assertEqual(self.match.votes.count(), 1)

    def test_vote_view_htmx_response(self):
        """Test that MatchVoteView returns the vote_results partial when called via HTMX."""
        url = reverse('matches:vote', kwargs={'pk': self.match.pk})
        response = self.client.post(
            url, 
            {'player_id': self.player1.pk}, 
            REMOTE_ADDR="192.168.1.10",
            HTTP_HX_REQUEST="true"
        )
        
        self.assertEqual(response.status_code, 200)
        # Check that it rendered the partial containing results instead of returning standard JSON
        self.assertContains(response, "fan-voting-container")
        self.assertContains(response, "VOTE FAN : MOTM")
        self.assertContains(response, "100")


from apps.matches.models import MatchEvent

class MatchLiveControlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="organizer_test",
            email="org@test.com",
            password="testpassword",
            role="organizer"
        )
        self.client.login(username="organizer_test", password="testpassword")
        
        self.tournament = Tournament.objects.create(
            name="Live Tournament",
            year=2026,
            edition=1
        )
        self.team1 = Team.objects.create(name="Team A")
        self.team2 = Team.objects.create(name="Team B")
        self.match = Match.objects.create(
            tournament=self.tournament,
            team1=self.team1,
            team2=self.team2,
            status=Match.Status.LIVE,
            match_date=timezone.now(),
            current_period="1H",
            current_minute=10
        )
        self.player1 = Player.objects.create(
            team=self.team1,
            first_name="Live",
            last_name="Player",
            jersey_number=10,
            position="FWD",
            is_active=True,
            national_id="LIVEP1"
        )

    def test_update_live_timer(self):
        """Test updating live match status, period and minute."""
        url = reverse('matches:update_live_timer', kwargs={'pk': self.match.pk})
        response = self.client.post(url, {
            'status': 'live',
            'period': '2H',
            'minute': 46
        })
        self.assertEqual(response.status_code, 302)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.LIVE)
        self.assertEqual(self.match.current_period, '2H')
        self.assertEqual(self.match.current_minute, 46)

    def test_add_generic_event_substitution(self):
        """Test adding a generic substitution event."""
        url = reverse('matches:add_generic_event', kwargs={'pk': self.match.pk})
        response = self.client.post(url, {
            'event_type': 'substitution',
            'minute': 55,
            'team': self.team1.pk,
            'player1': self.player1.pk,
            'description': 'Live Player is substituted'
        })
        self.assertEqual(response.status_code, 302)
        events = MatchEvent.objects.filter(match=self.match)
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.event_type, 'substitution')
        self.assertEqual(event.minute, 55)
        self.assertEqual(event.team, self.team1)
        self.assertEqual(event.player1, self.player1)
