from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User


class Notification(models.Model):
    class Type(models.TextChoices):
        MATCH_RESULT   = 'match_result',   _('Résultat de match')
        MATCH_REMINDER = 'match_reminder', _('Rappel de match')
        SUSPENSION     = 'suspension',     _('Suspension de joueur')
        TOURNAMENT     = 'tournament',     _('Annonce du tournoi')
        INJURY         = 'injury',         _('Blessure signalée')
        TEAM_REGISTRATION = 'team_registration', _('Inscription d\'équipe')
        USER_REGISTRATION = 'user_registration', _('Demande d\'adhésion')
        SYSTEM         = 'system',         _('Système')

    recipient  = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='notifications')
    notif_type = models.CharField(max_length=20, choices=Type.choices)
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    link       = models.URLField(max_length=500, blank=True, null=True, verbose_name=_('Lien redirection'))
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Notification')

    def __str__(self):
        return f"[{self.get_notif_type_display()}] → {self.recipient.username}"
