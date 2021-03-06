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
"""
provider notification handling
"""
import logging

from linotp.provider import loadProvider

from linotp.lib.context import request_context

from linotp.lib.policy import get_client_policy
from linotp.lib.policy import getPolicyActionValue

log = logging.getLogger(__name__)

class NotificationException(Exception):
    pass

def notify_user(user, action, info, required=False):
    """
    notify user via email, sms or other method (http/whatsapp...)

    :param user: the user who should be notified
    :param action: action is currently the notification action like
                   enrollment, setPin, which are defined in the
                   notification policies
    :param info: generic dict which is action specific
    :param required: if True an exception is raised if no notification could
                     be send eg if no provider is defined or could be found
    """

    policies = get_client_policy(
        request_context['Client'], scope='notification',
        action=action, realm=user.realm, user=user.login)

    provider_specs = getPolicyActionValue(policies, action, is_string=True)
    if not isinstance(provider_specs, list):
        provider_specs=[provider_specs]

    # TODO: use the ResouceSchduler to handle failover

    for provider_spec in provider_specs:

        provider_type, _sep, provider_name = provider_spec.partition('::')

        if provider_type == 'email':
            notify_user_by_email(provider_name, user, action, info)
            return

        # elif provider_type == 'sms':
        #    notify_user_by_email(provider_name, user, action, info)

    log.info('Failed to notify user %r', user)

    if required:
        raise NotificationException(
            'No notification has been sent - %r provider defined?' % action)


def notify_user_by_email(provider_name, user, action, info):
    """
    notify user via email

    :param provider_name: the name of the provider that should be used
    :param user: the user who should be notified
    :param action: action is currently the notification action like
                   enrollment, setPin, which are defined in the
                   notification policies
    :param info: generic dict which is action specific
    """
    user_detail = user.getUserInfo()
    if 'cryptpass' in user_detail:
        del user_detail['cryptpass']

    user_email = user_detail.get('email')
    if not user_email:
        raise NotificationException(
            'Unable to notify user via email - user has no email address')

    replacements = {}
    replacements.update(info)
    replacements.update(user_detail)

    try:

        provider = loadProvider('email', provider_name=provider_name)
        provider.submitMessage(
            email_to=user_email,
            message=info.get('message',''),
            subject=info.get('Subject',''),
            replacements=replacements)

    except Exception as exx:
        log.error('Failed to notify user %r by email' % user_email)
        raise NotificationException(
            'Failed to notify user %r by email:%r' % (user_email, exx))

# eof #