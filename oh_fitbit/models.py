from datetime import timedelta
import os

import arrow
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
import requests

OH_CLIENT_ID = os.getenv('OH_CLIENT_ID', '')
OH_CLIENT_SECRET = os.getenv('OH_CLIENT_SECRET', '')


def make_unique_username(base):
    """
    Ensure a unique username. Probably this never actually gets used.
    """
    try:
        User.objects.get(username=base)
    except User.DoesNotExist:
        return base
    n = 2
    while True:
        name = base + str(n)
        try:
            User.objects.get(username=name)
            n += 1
        except User.DoesNotExist:
            return name

@python_2_unicode_compatible
class OpenHumansMember(models.Model):
    """
    Store OAuth2 data for Open Humans member.

    A User account is created for this Open Humans member.
    """
    user = models.OneToOneField(User, related_name="oh_member", 
                                on_delete=models.CASCADE)
    oh_id = models.CharField(max_length=16, primary_key=True, unique=True)
    access_token = models.CharField(max_length=256)
    refresh_token = models.CharField(max_length=256)
    token_expires = models.DateTimeField()

    @staticmethod
    def get_expiration(expires_in):
        return (arrow.now() + timedelta(seconds=expires_in)).format()

    @classmethod
    def create(cls, oh_id, access_token, refresh_token, expires_in):
        new_username = make_unique_username(
            base='{}_openhumans'.format(oh_id))
        new_user = User(username=new_username)
        new_user.save()
        oh_member = cls(
            user=new_user,
            oh_id=oh_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires=cls.get_expiration(expires_in))
        return oh_member

    def __str__(self):
        return "<OpenHumansMember(oh_id='{}')>".format(
            self.oh_id)

    def get_access_token(self):
        """
        Return access token. Refresh first if necessary.
        """
        # Also refresh if nearly expired (less than 60s remaining).
        delta = timedelta(seconds=60)
        if arrow.get(self.token_expires) - delta < arrow.now():
            self._refresh_tokens()
        return self.access_token

    def _refresh_tokens(self):
        """
        Refresh access token.
        """
        response = requests.post(
            'https://www.openhumans.org/oauth2/token/',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token},
            auth=requests.auth.HTTPBasicAuth(
                settings.OH_CLIENT_ID, settings.OH_CLIENT_SECRET))
        if response.status_code == 200:
            data = response.json()
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.token_expires = self.get_expiration(data['expires_in'])
            self.save()


class FitbitMember(models.Model):
    """
    Store OAuth2 data for a Fitbit Member.
    This is a one to one relationship with a OpenHumansMember object.
    """
    user = models.OneToOneField(OpenHumansMember, on_delete=models.CASCADE)
    userid = models.CharField(max_length=255, unique=True, null=True)
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255)
    expires_in = models.CharField(max_length=255)
    scope = models.CharField(max_length=500)
    token_type = models.CharField(max_length=255)


@python_2_unicode_compatible
class CacheItem(models.Model):
    '''
    Cache request responses for fitbit data.
    '''
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=2014)
    response = JSONField()
    request_time = models.DateTimeField()

    def __init__(self, key, response):
        self.key = key
        self.response = response
        self.request_time = datetime.now()

    def __str__(self):
        return "<CacheItem(url='{}')>".format(self.url)
