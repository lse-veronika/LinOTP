# -*- coding: utf-8 -*-
#
#    LinOTP - the open source solution for two factor authentication
#    Copyright (C) 2010 - 2019 KeyIdentity GmbH
#
#    This file is part of LinOTP server.
#
#    This program is free software: you can redistribute it and/or
#    modify it under the terms of the GNU Affero General Public
#    License, version 3, as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the
#               GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#    E-mail: linotp@keyidentity.com
#    Contact: www.linotp.org
#    Support: www.keyidentity.com
#
#

"""
test the helpdesk enrollment api
- list users
- enroll token
- list tokens of user
- user might be in one or more realms
"""

import json
import re
import os

from . import MockedSMTP

from linotp.tests import TestController

from . import enable_helpdesk_controller
import pylons.test

class TestHelpdeskEnrollment(TestController):

    @classmethod
    def setup_class(cls):
        """add the helpdesk route to the test pylons app"""

        enable_helpdesk_controller(pylons.test.pylonsapp.config)

    def setUp(self):
        """ setup for std resolver / realms"""

        TestController.setUp(self)
        self.create_common_resolvers()
        self.create_common_realms()

    def tearDown(self):
        """ clean up for all token and resolver / realms """

        self.delete_all_realms()
        self.delete_all_resolvers()
        self.delete_all_token()
        self.delete_all_policies()

        TestController.tearDown(self)

    def test_list_users(self):
        """ verify 'api/helpdesk/users' endpoint honores admin policies """

        # define admin policy for helpdesk user 'helpdesk'

        policy = {
            'name': 'admin',
            'action': '*',
            'scope': 'admin',
            'active': True,
            'realm': '*',
            'user': 'superadmin, admin',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        policy = {
            'name': 'helpdesk',
            'action': 'show, userlist',
            'scope': 'admin',
            'active': True,
            'realm': 'mydefrealm',
            'user': 'helpdesk,',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        # ------------------------------------------------------------------ --

        # verify that the helpdesk user can see only users for the
        # specified realm

        params = {}

        response = self.make_helpdesk_request(
            'users', params=params)

        assert 'false' not in response

        jresp = json.loads(response.body)
        for user in jresp['result']['value']['rows']:
            user_parts = user['cell']
            realms = user_parts[8]
            assert 'mydefrealm' in realms
            assert len(realms) <= 1

        # ------------------------------------------------------------------ --

        # now we adjust the helpdesk user policy to have access to more than
        # one realm

        policy = {
            'name': 'helpdesk',
            'action': 'show, userlist',
            'scope': 'admin',
            'active': True,
            'realm': 'mydefrealm, mymixrealm',
            'user': 'helpdesk,',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        # verify that the helpdesk user can see only users for the
        # specified realm

        params = {}

        response = self.make_helpdesk_request(
            'users', params=params)

        assert 'false' not in response

        realm_set = set()

        jresp = json.loads(response.body)
        for user in jresp['result']['value']['rows']:
            user_parts = user['cell']
            realms = user_parts[8]
            realm_set.update(realms)

        assert 'mydefrealm' in realm_set
        assert 'mymixrealm' in realm_set

        assert len(realm_set) == 2

        # ------------------------------------------------------------------ --

        # now we adjust the helpdesk user policy to have access to more than
        # one realm

        policy = {
            'name': 'helpdesk',
            'action': 'show, userlist',
            'scope': 'admin',
            'active': True,
            'realm': '*',
            'user': 'helpdesk,',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        # verify that the helpdesk user can see only users for the
        # specified realm

        params = {}

        response = self.make_helpdesk_request(
            'users', params=params)

        assert 'false' not in response

        realm_set = set()

        jresp = json.loads(response.body)
        for user in jresp['result']['value']['rows']:
            user_parts = user['cell']
            realms = user_parts[8]
            realm_set.update(realms)

        assert 'mydefrealm' in realm_set
        assert 'mymixrealm' in realm_set
        assert 'myotherrealm' in realm_set

        assert len(realm_set) == 3

        return

    def test_users_with_params(self):
        """verify that the users search parameter work"""

        user_query = r'ha*'
        user_search = re.compile(user_query)

        params = {'qtype': 'username', 'query': user_query}

        response = self.make_helpdesk_request(
            'users', params=params)

        assert 'false' not in response

        jresp = json.loads(response.body)
        for user in jresp['result']['value']['rows']:
            user_parts = user['cell']
            username = user_parts[0]
            res = re.match(user_search, username)
            assert res

        params = {'qtype': 'email', 'query': user_query}

        response = self.make_helpdesk_request(
            'users', params=params)

        assert 'false' not in response

        jresp = json.loads(response.body)
        for user in jresp['result']['value']['rows']:
            user_parts = user['cell']
            email = user_parts[4]
            res = re.match(user_search, email)
            assert res

    def test_enrollment(self):
        """verify that an email token will be enrolled"""

        # ------------------------------------------------------------------ --

        # define the email provider

        email_config = {
            "SMTP_SERVER": "mail.example.com",
            "SMTP_USER": "secret_user",
            "SMTP_PASSWORD": "secret_pasword",
            "EMAIL_FROM": "linotp@example.com",
            "EMAIL_SUBJECT": "New Token <PIN>"
        }

        params = {
            'name': 'enrollmentProvider',
            'class': 'linotp.provider.emailprovider.SMTPEmailProvider',
            'timeout': '120',
            'type': 'email',
            'config': json.dumps(email_config)
        }

        self.make_system_request('setProvider', params=params)

        # ------------------------------------------------------------------ --

        # define the notification provider policy

        policy = {
            'name': 'notify_enrollement',
            'action': 'enrollment=email::enrollmentProvider ',
            'scope': 'notification',
            'active': True,
            'realm': '*',
            'user': '*',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        # ------------------------------------------------------------------ --

        # enroll email token for hans with given pin
        # verify that message contains given pin

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email', 'pin': 'test123!'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'false' not in response, response

            call_args = mock_smtp_instance.sendmail.call_args
            _email_from, email_to, email_message = call_args[0]

            assert email_to == 'hans@example.com'
            assert 'Subject: New email token enrolled' in email_message
            assert "with pin 'test123!" in email_message

        # ------------------------------------------------------------------ --

        # enroll email token for hans with given pin and random pin policy
        # verify that message does not contain the given pin

        policy = {
            'name': 'enrollment_pin_policy',
            'action': 'otp_pin_random=12, otp_pin_random_content=n',
            'scope': 'enrollment',
            'active': True,
            'realm': '*',
            'user': '*',
            'client': '*',
        }

        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email', 'pin': 'test123!'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'false' not in response, response

            call_args = mock_smtp_instance.sendmail.call_args
            _email_from, email_to, email_message = call_args[0]

            assert email_to == 'hans@example.com'
            assert 'Subject: New email token enrolled' in email_message
            assert "with pin 'test123!" not in email_message

            # now verify that there are only digits in the pin, as we defined
            # the random pin contents

            parts = email_message.split("'")
            assert int(parts[1]), email_message
            assert len(parts[1]) == 12, email_message

        return

    def test_enrollment_with_template(self):
        """verify that an email token will be enrolled"""

        # ------------------------------------------------------------------ --

        # define the email provider

        filename = os.path.join(self.fixture_path, 'enrollment_email.eml')
        with open(filename, "rb") as f:
            content = f.read()
        inline_template = json.dumps(content)

        email_config = {
            "SMTP_SERVER": "mail.example.com",
            "SMTP_USER": "secret_user",
            "SMTP_PASSWORD": "secret_pasword",
            "EMAIL_FROM": "linotp@example.com",
            "TEMPLATE": inline_template,
        }

        params = {
            'name': 'enrollmentTemplateProvider',
            'class': 'linotp.provider.emailprovider.SMTPEmailProvider',
            'timeout': '120',
            'type': 'email',
            'config': json.dumps(email_config)
        }

        self.make_system_request('setProvider', params=params)

        # ------------------------------------------------------------------ --

        # define the notification provider policy

        policy = {
            'name': 'notify_enrollement',
            'action': 'enrollment=email::enrollmentTemplateProvider ',
            'scope': 'notification',
            'active': True,
            'realm': '*',
            'user': '*',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        # ------------------------------------------------------------------ --

        # enroll email token for hans with given pin and random pin policy
        # verify that message does not contain the given pin

        policy = {
            'name': 'enrollment_pin_policy',
            'action': 'otp_pin_random=12, otp_pin_random_content=n',
            'scope': 'enrollment',
            'active': True,
            'realm': '*',
            'user': '*',
            'client': '*',
        }

        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not in response

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'false' not in response, response

            call_args = mock_smtp_instance.sendmail.call_args
            _email_from, email_to, email_message = call_args[0]

            assert email_to == 'hans@example.com'
            message_parts = email_message.split('\\n')

            assert 'Subject: New email token enrolled' in message_parts[3]
            assert "with pin 'test123!" not in message_parts[13]

            # now verify that there are only digits in the pin, as we defined
            # the random pin contents

            pin_message = message_parts[40].split(":")[1].split("<")
            assert int(pin_message[0]), message_parts[40]
            assert len(pin_message[0].strip()) == 12, message_parts[40]

        return

    def test_enrollment_admin_right(self):
        """verify that an email token will be enrolled adhering to the admin right """

        # ------------------------------------------------------------------ --

        # define the email provider

        email_config = {
            "SMTP_SERVER":"mail.example.com",
            "SMTP_USER":"secret_user",
            "SMTP_PASSWORD":"secret_pasword",
            "EMAIL_FROM":"linotp@example.com",
            "EMAIL_SUBJECT":"New Token enrolled"
        }

        params = {
            'name': 'enrollmentProvider',
            'class': 'linotp.provider.emailprovider.SMTPEmailProvider',
            'timeout': '120',
            'type': 'email',
            'config': json.dumps(email_config)
        }

        self.make_system_request('setProvider', params=params)

        # ------------------------------------------------------------------ --

        # define the notification provider policy

        policy = {
            'name': 'notify_enrollement',
            'action': 'enrollment=email::enrollmentProvider ',
            'scope': 'notification',
            'active': True,
            'realm': '*',
            'user': '*',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not  in response

        # ------------------------------------------------------------------ --

        # define admin policy which denies the enrollemt for the helpdesk user

        policy = {
            'name': 'admin',
            'action': '*',
            'scope': 'admin',
            'active': True,
            'realm': '*',
            'user': 'superadmin, admin',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not  in response

        # define the restricted admin policy for helpdesk user 'helpdesk'

        policy = {
            'name': 'helpdesk',
            'scope': 'admin',
            'active': True,
            'user': 'helpdesk,',
            'action': 'initEMAIL',
            'realm': 'myotherrealm',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not  in response

        # ------------------------------------------------------------------ --

        # enroll email token for hans has to fail as the helpdesk is not
        # allowed to enroll email token in the realm for hans

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'not have the administrative right' in response, response

        # ------------------------------------------------------------------ --

        # now adjust the admin policy so that the helpdesk is allowed to enroll
        # email tokens in the realm mydefrealm as well

        policy = {
            'name': 'helpdesk',
            'scope': 'admin',
            'active': True,
            'user': 'helpdesk,',
            'action': 'initEMAIL',
            'realm': 'myotherrealm, mydefrealm',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not  in response

        # ------------------------------------------------------------------ --

        # verify that the enrollment now is allowed

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'have the administrative right' not in response, response
            assert '"value": true' in response, response

        return

    def test_enrollment_maxtoken(self):
        """verify that only one email token will be enrolled"""

        # ------------------------------------------------------------------ --

        # define the email provider

        email_config = {
            "SMTP_SERVER":"mail.example.com",
            "SMTP_USER":"secret_user",
            "SMTP_PASSWORD":"secret_pasword",
            "EMAIL_FROM":"linotp@example.com",
            "EMAIL_SUBJECT":"New Token enrolled"
        }

        params = {
            'name': 'enrollmentProvider',
            'class': 'linotp.provider.emailprovider.SMTPEmailProvider',
            'timeout': '120',
            'type': 'email',
            'config': json.dumps(email_config)
        }

        self.make_system_request('setProvider', params=params)

        # ------------------------------------------------------------------ --

        # define the notification provider policy

        policy = {
            'name': 'notify_enrollement',
            'action': 'enrollment=email::enrollmentProvider ',
            'scope': 'notification',
            'active': True,
            'realm': '*',
            'user': '*',
            'client': '*',
        }
        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not  in response

        # ------------------------------------------------------------------ --

        # enroll email token for hans with given pin and random pin policy
        # verify that message does not contain the given pin

        policy = {
            'name': 'maxtoken',
            'action': 'maxtoken=1',
            'scope': 'enrollment',
            'active': True,
            'realm': 'mydefrealm',
            'user': '*',
            'client': '*',
        }

        response = self.make_system_request('setPolicy', params=policy)
        assert 'false' not  in response

        # ------------------------------------------------------------------ --

        # enroll email token for hans with given pin
        # verify that message contains given pin

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email', 'pin': 'test123!'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'false' not in response, response

            call_args = mock_smtp_instance.sendmail.call_args
            _email_from, email_to, email_message = call_args[0]

            assert email_to == 'hans@example.com'
            assert 'Subject: New email token enrolled' in email_message
            assert "with pin 'test123!" in email_message

        # ------------------------------------------------------------------ --

        # enroll email token for hans with given pin
        # verify that message contains given pin

        with MockedSMTP() as mock_smtp_instance:

            mock_smtp_instance.sendmail.return_value = []

            params = {'user': 'hans', 'type': 'email', 'pin': 'test123!'}

            response = self.make_helpdesk_request(
                'enroll', params=params)

            assert 'maximum number of allowed' in response, response

        # ------------------------------------------------------------------ --

        # verify that user has only one token
        params = {
            'qtype': 'loginname',
            'query': 'hans'
            }

        response = self.make_helpdesk_request('tokens', params=params)
        assert 'false' not in response
        assert 'hans' in response
        assert '"total": 1' in response

        return

# eof #
