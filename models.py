from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.db import models

from voting.managers import VoteManager

SCORES = (
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4),
    (5, 5),
)

class Vote(models.Model):
    """
    A vote on an object by a User.
    """
    user = models.ForeignKey(User, blank=True, null=True)
    ip = models.IPAddressField()
    
    content_type = models.ForeignKey(ContentType)
    object_id  = models.PositiveIntegerField()
    object = generic.GenericForeignKey('content_type', 'object_id')
    vote = models.SmallIntegerField(choices=SCORES)
    
    date = models.DateTimeField(auto_now_add=True)
    
    objects = VoteManager()

    class Meta:
        db_table = 'votes'
        # One vote per user (and ip) per object
        unique_together = (('user', 'content_type', 'object_id', 'ip'),)

    def __unicode__(self):
        return u'%s: %s on %s' % (self.user or self.ip, self.vote, self.object)