import json
import requests

from mock import patch
from django_digest.test import DigestAuth


from httmock import all_requests, HTTMock

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.main.models import UserProfile
from django.contrib.auth.models import User
from onadata.libs.serializers.user_profile_serializer import (
    _get_first_last_names
)
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.libs.authentication import DigestAuthentication


def _profile_data():
    return {
        'username': u'deno',
        'first_name': u'Dennis',
        'last_name': u'erama',
        'email': u'deno@columbia.edu',
        'city': u'Denoville',
        'country': u'US',
        'organization': u'Dono Inc.',
        'website': u'deno.com',
        'twitter': u'denoerama',
        'require_auth': False,
        'password': 'denodeno',
        'is_org': False,
        'name': u'Dennis erama'
    }


class TestUserProfileViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = UserProfileViewSet.as_view({
            'get': 'list',
            'post': 'create',
            'patch': 'partial_update',
            'put': 'update'
        })

    def test_profiles_list(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.user_profile_data()])

    def test_user_profile_list(self):
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(_profile_data()),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        data = {"users": "bob,deno"}
        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)

        deno_profile_data = _profile_data()
        deno_profile_data.pop('password', None)
        user_deno = User.objects.get(username='deno')
        deno_profile_data.update({
            'id': user_deno.pk,
            'url': 'http://testserver/api/v1/profiles/%s' % user_deno.username,
            'user': 'http://testserver/api/v1/users/%s' % user_deno.username,
            'gravatar': user_deno.profile.gravatar,
            'metadata': {},
            'joined_on': user_deno.date_joined
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted([dict(d) for d in response.data]),
                         sorted([self.user_profile_data(), deno_profile_data]))
        self.assertEqual(len(response.data), 2)

    def test_user_profile_list_with_and_without_users_param(self):
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(_profile_data()),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # anonymous user gets empty response
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # authenicated user without users query param only gets his/her profile
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertDictEqual(self.user_profile_data(), response.data[0])

        # authenicated user with blank users query param only gets his/her
        # profile
        data = {"users": ""}
        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertDictEqual(self.user_profile_data(), response.data[0])

        # authenicated user with comma separated usernames as users query param
        # value gets profiles of the usernames provided
        data = {"users": "bob,deno"}
        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)
        deno_profile_data = _profile_data()
        deno_profile_data.pop('password', None)
        user_deno = User.objects.get(username='deno')
        deno_profile_data.update({
            'id': user_deno.pk,
            'url': 'http://testserver/api/v1/profiles/%s' % user_deno.username,
            'user': 'http://testserver/api/v1/users/%s' % user_deno.username,
            'gravatar': user_deno.profile.gravatar,
            'metadata': {},
            'joined_on': user_deno.date_joined
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            response.data,
            [self.user_profile_data(), deno_profile_data]
        )

    def test_profiles_get(self):
        """Test get user profile"""
        view = UserProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {'detail': 'Expected URL keyword argument `user`.'})

        # by username
        response = view(request, user='bob')
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.user_profile_data())

        # by username mixed case
        response = view(request, user='BoB')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data, self.user_profile_data())

        # by pk
        response = view(request, user=self.user.pk)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.user_profile_data())

    def test_profiles_get_anon(self):
        view = UserProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {'detail': 'Expected URL keyword argument `user`.'})
        request = self.factory.get('/')
        response = view(request, user='bob')
        data = self.user_profile_data()
        del data['email']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)
        self.assertNotIn('email', response.data)

    def test_profiles_get_org_anon(self):
        self._org_create()
        self.client.logout()
        view = UserProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/')
        response = view(request, user=self.company_data['org'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'],
                         self.company_data['name'])
        self.assertIn('is_org', response.data)
        self.assertEqual(response.data['is_org'], True)

    def test_profile_create(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data['name']
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        password = data['password']
        del data['password']
        profile = UserProfile.objects.get(user__username=data['username'])
        data['id'] = profile.user.pk
        data['gravatar'] = profile.gravatar
        data['url'] = 'http://testserver/api/v1/profiles/deno'
        data['user'] = 'http://testserver/api/v1/users/deno'
        data['metadata'] = {}
        data['joined_on'] = profile.user.date_joined
        data['name'] = "%s %s" % ('Dennis', 'erama')
        self.assertEqual(response.data, data)

        user = User.objects.get(username='deno')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(password), password)

    def test_profile_create_without_last_name(self):
        data = {
            'username': u'deno',
            'first_name': u'Dennis',
            'email': u'deno@columbia.edu',
        }

        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

    def test_profile_create_with_malfunctioned_email(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = {
            'username': u'nguyenquynh',
            'first_name': u'Nguy\u1ec5n Th\u1ecb',
            'last_name': u'Di\u1ec5m Qu\u1ef3nh',
            'email': u'onademo0+nguyenquynh@gmail.com\ufeff',
            'city': u'Denoville',
            'country': u'US',
            'organization': u'Dono Inc.',
            'website': u'nguyenquynh.com',
            'twitter': u'nguyenquynh',
            'require_auth': False,
            'password': u'onademo',
            'is_org': False,
        }

        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        password = data['password']
        del data['password']

        profile = UserProfile.objects.get(user__username=data['username'])
        data['id'] = profile.user.pk
        data['gravatar'] = profile.gravatar
        data['url'] = 'http://testserver/api/v1/profiles/nguyenquynh'
        data['user'] = 'http://testserver/api/v1/users/nguyenquynh'
        data['metadata'] = {}
        data['joined_on'] = profile.user.date_joined
        data['name'] = "%s %s" % (
            u'Nguy\u1ec5n Th\u1ecb', u'Di\u1ec5m Qu\u1ef3nh')
        self.assertEqual(response.data, data)

        user = User.objects.get(username='nguyenquynh')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(password), password)

    def test_profile_create_with_invalid_username(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        data['username'] = u'de'
        del data['name']
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('username'),
            [u'Ensure this field has at least 3 characters.'])

    def test_profile_create_anon(self):
        data = _profile_data()
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json")
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        del data['password']
        del data['email']
        profile = UserProfile.objects.get(user__username=data['username'])
        data['id'] = profile.user.pk
        data['gravatar'] = profile.gravatar
        data['url'] = 'http://testserver/api/v1/profiles/deno'
        data['user'] = 'http://testserver/api/v1/users/deno'
        data['metadata'] = {}
        data['joined_on'] = profile.user.date_joined
        self.assertEqual(response.data, data)
        self.assertNotIn('email', response.data)

    def test_profile_create_missing_name_field(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data['first_name']
        del data['name']
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        response.render()
        self.assertContains(response,
                            'Either name or first_name should be provided',
                            status_code=400)

    def test_split_long_name_to_first_name_and_last_name(self):
        name = "(CPLTGL) Centre Pour la Promotion de la Liberte D'Expression "\
            "et de la Tolerance Dans La Region de"
        first_name, last_name = _get_first_last_names(name)
        self.assertEqual(first_name, "(CPLTGL) Centre Pour la Promot")
        self.assertEqual(last_name, "ion de la Liberte D'Expression")

    def test_partial_updates(self):
        self.assertEqual(self.user.profile.country, u'US')
        country = u'KE'
        username = 'george'
        metadata = {u'computer': u'mac'}
        json_metadata = json.dumps(metadata)
        data = {'username': username,
                'country': country,
                'metadata': json_metadata}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.country, country)
        self.assertEqual(profile.metadata, metadata)
        self.assertEqual(profile.user.username, username)

    def test_partial_updates_empty_metadata(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = dict()
        profile.save()
        metadata = {u"zebra": {u"key1": "value1", u"key2": "value2"}}
        json_metadata = json.dumps(metadata)
        data = {
            'metadata': json_metadata,
            'overwrite': 'false'
        }
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, metadata)

    def test_partial_updates_too_long(self):
        # the max field length for username is 30 in django
        username = 'a' * 31
        data = {'username': username}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {'username':
             [u'Ensure this field has no more than 30 characters.']})
        self.assertNotEqual(profile.user.username, username)

    def test_partial_update_metadata_field(self):
        metadata = {u"zebra": {u"key1": "value1", u"key2": "value2"}}
        json_metadata = json.dumps(metadata)
        data = {
            'metadata': json_metadata,
        }
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, metadata)

        # create a new key/value object if it doesn't exist
        data = {
            'metadata': '{"zebra": {"key3": "value3"}}',
            'overwrite': u'false'
        }
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata, {u"zebra": {
                u"key1": "value1", u"key2": "value2", u"key3": "value3"}})

        # update an existing key/value object
        data = {
            'metadata': '{"zebra": {"key2": "second"}}', 'overwrite': u'false'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata, {u"zebra": {
                u"key1": "value1", u"key2": "second", u"key3": "value3"}})

        # add a new key/value object if the key doesn't exist
        data = {
            'metadata': '{"animal": "donkey"}', 'overwrite': u'false'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata, {
                u"zebra": {
                    u"key1": "value1", u"key2": "second", u"key3": "value3"},
                u'animal': u'donkey'})

        # don't pass overwrite param
        data = {'metadata': '{"b": "caah"}'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata, {u'b': u'caah'})

        # pass 'overwrite' param whose value isn't false
        data = {'metadata': '{"b": "caah"}', 'overwrite': u'falsey'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata, {u'b': u'caah'})

    def test_put_update(self):

        data = _profile_data()
        # create profile
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # edit username with existing different user's username
        data['username'] = 'bob'
        request = self.factory.put(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request, user='deno')
        self.assertEqual(response.status_code, 400)

        # update
        data['username'] = 'roger'
        data['city'] = 'Nairobi'
        request = self.factory.put(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request, user='deno')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['city'], data['city'])

    def test_profile_create_mixed_case(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        del data['password']
        profile = UserProfile.objects.get(
            user__username=data['username'].lower())
        data['id'] = profile.user.pk
        data['gravatar'] = unicode(profile.gravatar)
        data['url'] = 'http://testserver/api/v1/profiles/deno'
        data['user'] = 'http://testserver/api/v1/users/deno'
        data['username'] = u'deno'
        data['metadata'] = {}
        data['joined_on'] = profile.user.date_joined
        self.assertEqual(response.data, data)

        data['username'] = u'deno'
        data['joined_on'] = str(profile.user.date_joined)
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("%s already exists" %
                      data['username'], response.data['username'])

    def test_change_password(self):
        view = UserProfileViewSet.as_view(
            {'post': 'change_password'})
        current_password = "bobbob"
        new_password = "bobbob1"
        post_data = {'current_password': current_password,
                     'new_password': new_password}

        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, user='bob')
        user = User.objects.get(username__iexact=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.check_password(new_password))

    def test_change_password_wrong_current_password(self):
        view = UserProfileViewSet.as_view(
            {'post': 'change_password'})
        current_password = "wrong_pass"
        new_password = "bobbob1"
        post_data = {'current_password': current_password,
                     'new_password': new_password}

        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, user='bob')
        user = User.objects.get(username__iexact=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(user.check_password(new_password))

    def test_profile_create_with_name(self):
        data = {
            'username': u'deno',
            'name': u'Dennis deno',
            'email': u'deno@columbia.edu',
            'city': u'Denoville',
            'country': u'US',
            'organization': u'Dono Inc.',
            'website': u'deno.com',
            'twitter': u'denoerama',
            'require_auth': False,
            'password': 'denodeno',
            'is_org': False,
        }
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 201)
        del data['password']
        profile = UserProfile.objects.get(user__username=data['username'])
        data['id'] = profile.user.pk
        data['first_name'] = 'Dennis'
        data['last_name'] = 'deno'
        data['gravatar'] = profile.gravatar
        data['url'] = 'http://testserver/api/v1/profiles/deno'
        data['user'] = 'http://testserver/api/v1/users/deno'
        data['metadata'] = {}
        data['joined_on'] = profile.user.date_joined

        self.assertEqual(response.data, data)

        user = User.objects.get(username='deno')
        self.assertTrue(user.is_active)

    def test_twitter_username_validation(self):
        data = {
            'username': u'deno',
            'name': u'Dennis deno',
            'email': u'deno@columbia.edu',
            'city': u'Denoville',
            'country': u'US',
            'organization': u'Dono Inc.',
            'website': u'deno.com',
            'twitter': u'denoerama',
            'require_auth': False,
            'password': 'denodeno',
            'is_org': False,
        }
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 201)
        data['twitter'] = 'denoerama'
        data = {
            'username': u'deno',
            'name': u'Dennis deno',
            'email': u'deno@columbia.edu',
            'city': u'Denoville',
            'country': u'US',
            'organization': u'Dono Inc.',
            'website': u'deno.com',
            'twitter': u'denoeramaddfsdsl8729320392ujijdswkp--22kwklskdsjs',
            'require_auth': False,
            'password': 'denodeno',
            'is_org': False,
        }
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['twitter'],
            [u'Invalid twitter username {}'.format(data['twitter'])]
        )

        user = User.objects.get(username='deno')
        self.assertTrue(user.is_active)

    def test_put_patch_method_on_names(self):
        data = _profile_data()
        # create profile
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # update
        data['first_name'] = 'Tom'
        del data['name']
        request = self.factory.put(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = self.view(request, user='deno')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], data['first_name'])

        first_name = u'Henry'
        last_name = u'Thierry'

        data = {'first_name': first_name, 'last_name': last_name}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data['first_name'], data['first_name'])
        self.assertEqual(response.data['last_name'], data['last_name'])

    @patch('django.core.mail.EmailMultiAlternatives.send')
    def test_send_email_activation_api(self, mock_send_mail):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data['name']
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        # Activation email not sent
        self.assertFalse(mock_send_mail.called)
        user = User.objects.get(username='deno')
        self.assertTrue(user.is_active)

    def test_partial_update_without_password_fails(self):
        data = {'email': 'user@example.com'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            [u'Your password is required when updating your email address.'],
            response.data)

    def test_partial_update_with_invalid_email_fails(self):
        data = {'email': 'user@example'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 400)

    def test_partial_update_email(self):
        data = {'email': 'user@example.com',
                'password': "invalid_password"}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 400)

        data = {'email': 'user@example.com',
                'password': 'bobbob'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.user.email, 'user@example.com')

    def test_update_first_last_name_password_not_affected(self):
        data = {'first_name': 'update_first',
                'last_name': 'update_last'}
        request = self.factory.patch(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request, user=self.user.username)

        self.assertEqual(response.status_code, 200)

        view = ConnectViewSet.as_view(
            {'get': 'list'},
            authentication_classes=(DigestAuthentication,))

        auth = DigestAuth('bob@columbia.edu', 'bobbob')
        request = self._get_request_session_with_auth(view, auth)

        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_partial_update_unique_email_api(self):
        data = {'email': 'example@gmail.com',
                'password': 'bobbob'}
        request = self.factory.patch(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request, user=self.user.username)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data['email'], data['email'])
        # create User
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(_profile_data()),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='deno')
        # Update email
        request = self.factory.patch(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request, user=user.username)

        self.assertEqual(response.status_code, 400)

    def test_profile_create_fails_with_long_first_and_last_names(self):
        data = {
            'username': u'machicimo',
            'email': u'mike@columbia.edu',
            'city': u'Denoville',
            'country': u'US',
            'last_name':
                u'undeomnisistenatuserrorsitvoluptatem',
            'first_name':
                u'quirationevoluptatemsequinesciunt'
        }
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.data['first_name'][0],
                         u'Ensure this field has no more than 30 characters.')
        self.assertEqual(response.data['last_name'][0],
                         u'Ensure this field has no more than 30 characters.')
        self.assertEqual(response.status_code, 400)

    @all_requests
    def grant_perms_form_builder(self, url, request):

        assert 'Authorization' in request.headers
        assert request.headers.get('Authorization').startswith('Token')

        response = requests.Response()
        response.status_code = 201
        response._content = \
            {
                "detail": "Successfully granted default model level perms to"
                          " user."
            }
        return response

    def test_create_user_with_given_name(self):
        with HTTMock(self.grant_perms_form_builder):
            with self.settings(KPI_FORMBUILDER_URL='http://test_formbuilder$'):
                extra_data = {"username": "rust"}
                self._login_user_and_profile(extra_post_data=extra_data)
